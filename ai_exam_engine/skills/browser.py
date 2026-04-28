"""网页抓取管理器。

这个文件在研究能力层里的位置很明确：

- retriever 负责找 URL
- BrowserManager 负责把 URL 变成正文、标题、图片等可用内容

所以它解决的是“拿到链接之后怎么办”，而不是“应该搜哪些链接”。
"""

from gpt_researcher.utils.workers import WorkerPool

from ..actions.utils import stream_output
from ..actions.web_scraping import scrape_urls
from ..scraper.utils import get_image_hash


class BrowserManager:
    """研究阶段的网页抓取控制器。

    它主要负责：
    - 并发抓取 URL
    - 收集抓取结果
    - 处理研究图片
    - 把抓取结果挂回 `researcher` 的状态中
    """

    def __init__(self, researcher):
        """初始化网页抓取控制器。

        参数说明：
            researcher:
                上层 `GPTResearcher` 实例。这里会用到其中的：
                - cfg.max_scraper_workers
                - cfg.scraper_rate_limit_delay
                - websocket
                - verbose
                - research_images / research_sources
        """
        self.researcher = researcher
        # WorkerPool 用来控制并发抓取数量和节流，避免对目标站点产生过大压力。
        self.worker_pool = WorkerPool(
            researcher.cfg.max_scraper_workers,
            researcher.cfg.scraper_rate_limit_delay
        )

    async def browse_urls(self, urls: list[str]) -> list[dict]:
        """批量抓取一组 URL。

        参数说明：
            urls:
                待抓取的 URL 列表。

        返回值：
            list[dict]:
                抓取结果列表。每项通常包含：
                - url
                - title
                - raw_content
                - images
                等信息

        这一步不仅会返回抓取结果，还会顺手更新：
        - `researcher.research_sources`
        - `researcher.research_images`
        """
        if self.researcher.verbose:
            await stream_output(
                "logs",
                "scraping_urls",
                f"🌐 Scraping content from {len(urls)} URLs...",
                self.researcher.websocket,
            )

        # 真正的抓取动作委托给 action 层的 `scrape_urls`。
        scraped_content, images = await scrape_urls(
            urls, self.researcher.cfg, self.worker_pool
        )

        # 把抓下来的正文来源加入研究来源池，后续可用于引用展示。
        self.researcher.add_research_sources(scraped_content)

        # 从候选图片里挑一批质量更高、重复更少的图，供前端或报告使用。
        new_images = self.select_top_images(images, k=4)
        self.researcher.add_research_images(new_images)

        if self.researcher.verbose:
            await stream_output(
                "logs",
                "scraping_content",
                f"📄 Scraped {len(scraped_content)} pages of content",
                self.researcher.websocket,
            )
            await stream_output(
                "logs",
                "scraping_images",
                f"🖼️ Selected {len(new_images)} new images from {len(images)} total images",
                self.researcher.websocket,
                True,
                new_images,
            )
            await stream_output(
                "logs",
                "scraping_complete",
                f"🌐 Scraping complete",
                self.researcher.websocket,
            )

        return scraped_content

    def select_top_images(self, images: list[dict], k: int = 2) -> list[str]:
        """从候选图片中挑选出质量更高且尽量不重复的图片。

        参数说明：
            images:
                图片候选列表。每项通常至少包含 `url` 和 `score`。
            k:
                最多保留多少张图片。

        返回值：
            list[str]:
                最终入选的图片 URL 列表。

        这一步会做两类筛选：
        1. 按 score 从高到低排序
        2. 根据图片 hash 去重，避免视觉上重复
        """
        unique_images = []
        seen_hashes = set()
        current_research_images = self.researcher.get_research_images()

        # 先按分数从高到低遍历，优先保留更高质量图片。
        for img in sorted(images, key=lambda im: im["score"], reverse=True):
            img_hash = get_image_hash(img['url'])
            if (
                img_hash
                and img_hash not in seen_hashes
                and img['url'] not in current_research_images
            ):
                # 通过 hash 去重，同时避免重复加入 researcher 已经持有的图片。
                seen_hashes.add(img_hash)
                unique_images.append(img["url"])

                if len(unique_images) == k:
                    break

        return unique_images
