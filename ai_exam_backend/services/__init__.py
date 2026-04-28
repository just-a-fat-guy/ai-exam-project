"""AI 组卷后端服务层导出入口。

这一层放“业务规则”而不是 HTTP 路由本身。这样做的目的是：

1. `server/app.py` 保持接口编排职责，避免业务判断越写越厚
2. 后面无论是 WebSocket、HTTP 还是批处理任务，都可以复用同一套校验逻辑
3. 前端联调时，能拿到稳定统一的验证结果结构
"""

from .exam_validation import (
    build_exam_paper_schema_error_result,
    validate_exam_paper_request_model,
)
from .exam_preview import build_exam_paper_preview
from .exam_draft import generate_exam_preview_paper
from .exam_quality import validate_exam_draft_quality
from .exam_review import apply_exam_review_actions

__all__ = [
    "apply_exam_review_actions",
    "generate_exam_preview_paper",
    "build_exam_paper_schema_error_result",
    "build_exam_paper_preview",
    "validate_exam_draft_quality",
    "validate_exam_paper_request_model",
]
