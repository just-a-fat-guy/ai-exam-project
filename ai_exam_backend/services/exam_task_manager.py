"""AI 组卷异步任务管理。

当前阶段先使用进程内内存任务表，目标是：
1. 把长耗时的组卷请求从同步 HTTP 中拆出去
2. 给前端提供可轮询的进度和事件日志
3. 为后续接 WebSocket / Redis / 持久任务队列预留统一接口
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from schemas import (
    ExamGenerationTaskEvent,
    ExamGenerationTaskProgress,
    ExamGenerationTaskSnapshot,
    ExamPaperRequest,
)

from .exam_draft import generate_exam_preview_paper


logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _estimate_total_slots(exam_request: ExamPaperRequest) -> int:
    computed = 0
    for section in exam_request.sections:
        for requirement in section.question_requirements:
            computed += int(requirement.question_count or 0)
    if computed > 0:
        return computed
    return int(exam_request.target_question_count or 0)


class ExamGenerationTaskManager:
    """进程内异步组卷任务管理器。"""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._tasks: dict[str, ExamGenerationTaskSnapshot] = {}

    async def create_task(
        self,
        exam_request: ExamPaperRequest,
        validation_result: dict[str, Any],
        *,
        task_summary: str | None = None,
    ) -> ExamGenerationTaskSnapshot:
        now = _now_iso()
        task_id = uuid4().hex
        snapshot = ExamGenerationTaskSnapshot(
            task_id=task_id,
            status="queued",
            task_summary=task_summary or exam_request.paper_title,
            created_at=now,
            updated_at=now,
            progress=ExamGenerationTaskProgress(
                total_slots=_estimate_total_slots(exam_request),
                latest_message="任务已创建，等待后台开始组卷。",
            ),
            events=[
                ExamGenerationTaskEvent(
                    event_id=f"{task_id}-queued",
                    timestamp=now,
                    level="info",
                    stage="queued",
                    message="已提交组卷任务，准备进入后台生成。",
                    metadata={},
                )
            ],
            validation=validation_result,
            paper=None,
            error=None,
        )
        async with self._lock:
            self._tasks[task_id] = snapshot

        asyncio.create_task(self._run_task(task_id, exam_request, validation_result))
        return snapshot.model_copy(deep=True)

    async def get_task(self, task_id: str) -> ExamGenerationTaskSnapshot | None:
        async with self._lock:
            snapshot = self._tasks.get(task_id)
            return snapshot.model_copy(deep=True) if snapshot else None

    async def _append_event(
        self,
        task_id: str,
        *,
        level: str,
        stage: str,
        message: str,
        metadata: dict[str, Any] | None = None,
        progress_update: dict[str, Any] | None = None,
    ) -> None:
        now = _now_iso()
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return

            if progress_update:
                for key, value in progress_update.items():
                    if hasattr(task.progress, key):
                        setattr(task.progress, key, value)
            task.progress.latest_message = message
            task.updated_at = now
            task.events.append(
                ExamGenerationTaskEvent(
                    event_id=f"{task_id}-{len(task.events) + 1}",
                    timestamp=now,
                    level=level,  # type: ignore[arg-type]
                    stage=stage,
                    message=message,
                    metadata=metadata or {},
                )
            )

    async def _set_status(
        self,
        task_id: str,
        *,
        status: str,
        error: str | None = None,
        paper=None,
    ) -> None:
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return
            task.status = status  # type: ignore[assignment]
            task.updated_at = _now_iso()
            task.error = error
            if paper is not None:
                task.paper = paper

    async def _handle_progress(self, task_id: str, event: dict[str, Any]) -> None:
        await self._append_event(
            task_id,
            level=str(event.get("level") or "info"),
            stage=str(event.get("stage") or "progress"),
            message=str(event.get("message") or "任务进度更新。"),
            metadata=event.get("metadata") if isinstance(event.get("metadata"), dict) else {},
            progress_update=event.get("progress") if isinstance(event.get("progress"), dict) else None,
        )

    async def _run_task(
        self,
        task_id: str,
        exam_request: ExamPaperRequest,
        validation_result: dict[str, Any],
    ) -> None:
        await self._set_status(task_id, status="running")
        await self._append_event(
            task_id,
            level="info",
            stage="started",
            message="后台组卷任务已启动，正在构建试卷蓝图并生成题目。",
        )

        try:
            paper = await generate_exam_preview_paper(
                exam_request,
                validation_result,
                progress_callback=lambda event: self._handle_progress(task_id, event),
            )
            await self._set_status(task_id, status="completed", paper=paper)
            await self._append_event(
                task_id,
                level="success",
                stage="completed",
                message="试卷草案生成完成。",
                progress_update={
                    "latest_message": "试卷草案生成完成。",
                },
            )
        except Exception as exc:
            message = str(exc).strip() or f"{exc.__class__.__name__}: {exc!r}"
            logger.exception("Exam generation task %s failed", task_id)
            await self._set_status(task_id, status="failed", error=message)
            await self._append_event(
                task_id,
                level="error",
                stage="failed",
                message=f"试卷草案生成失败：{message}",
            )


exam_generation_task_manager = ExamGenerationTaskManager()
