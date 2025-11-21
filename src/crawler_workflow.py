#!/usr/bin/env python3
"""
完整的爬虫工作流系统
提供任务管理、调度、结果存储等完整功能
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import logging
import sys

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.smart_crawler import SmartCrawler
from configs.config import LLM_CONFIG, CRAWLER_CONFIG

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CrawlerTask:
    """爬虫任务"""

    def __init__(
        self,
        task_id: str,
        name: str,
        start_url: str,
        template_path: str,
        config: Dict = None
    ):
        """
        初始化爬虫任务

        Args:
            task_id: 任务ID
            name: 任务名称
            start_url: 起始URL
            template_path: 模板文件路径
            config: 任务配置（可选，默认使用CRAWLER_CONFIG）
        """
        self.task_id = task_id
        self.name = name
        self.start_url = start_url
        self.template_path = template_path
        self.config = config or CRAWLER_CONFIG.copy()

        # 任务状态
        self.status = "pending"  # pending, running, completed, failed
        self.created_at = datetime.now().isoformat()
        self.started_at = None
        self.completed_at = None
        self.error = None

        # 结果
        self.result_file = None
        self.pages_visited = 0
        self.products_found = 0

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "start_url": self.start_url,
            "template_path": self.template_path,
            "config": self.config,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "result_file": str(self.result_file) if self.result_file else None,
            "pages_visited": self.pages_visited,
            "products_found": self.products_found
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'CrawlerTask':
        """从字典创建任务"""
        task = cls(
            task_id=data["task_id"],
            name=data["name"],
            start_url=data["start_url"],
            template_path=data["template_path"],
            config=data.get("config")
        )
        task.status = data.get("status", "pending")
        task.created_at = data.get("created_at")
        task.started_at = data.get("started_at")
        task.completed_at = data.get("completed_at")
        task.error = data.get("error")
        task.result_file = Path(data["result_file"]) if data.get("result_file") else None
        task.pages_visited = data.get("pages_visited", 0)
        task.products_found = data.get("products_found", 0)
        return task


class TaskQueue:
    """任务队列管理"""

    def __init__(self, storage_path: str = None):
        """
        初始化任务队列

        Args:
            storage_path: 任务存储文件路径（默认: data/tasks.json）
        """
        if storage_path is None:
            # 默认存储在 data 目录
            project_root = Path(__file__).parent.parent
            storage_path = project_root / "data" / "tasks.json"

        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.tasks: Dict[str, CrawlerTask] = {}
        self.load()

    def add_task(self, task: CrawlerTask):
        """添加任务"""
        self.tasks[task.task_id] = task
        self.save()
        logger.info(f"添加任务: {task.task_id} - {task.name}")

    def get_task(self, task_id: str) -> Optional[CrawlerTask]:
        """获取任务"""
        return self.tasks.get(task_id)

    def get_pending_tasks(self) -> List[CrawlerTask]:
        """获取待执行任务"""
        return [t for t in self.tasks.values() if t.status == "pending"]

    def update_task(self, task: CrawlerTask):
        """更新任务"""
        self.tasks[task.task_id] = task
        self.save()

    def save(self):
        """保存任务队列到文件"""
        data = {
            task_id: task.to_dict()
            for task_id, task in self.tasks.items()
        }
        with open(self.storage_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self):
        """从文件加载任务队列"""
        if not self.storage_path.exists():
            return

        with open(self.storage_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.tasks = {
            task_id: CrawlerTask.from_dict(task_data)
            for task_id, task_data in data.items()
        }
        logger.info(f"加载了 {len(self.tasks)} 个任务")

    def get_summary(self) -> Dict:
        """获取任务队列摘要"""
        return {
            "total": len(self.tasks),
            "pending": len([t for t in self.tasks.values() if t.status == "pending"]),
            "running": len([t for t in self.tasks.values() if t.status == "running"]),
            "completed": len([t for t in self.tasks.values() if t.status == "completed"]),
            "failed": len([t for t in self.tasks.values() if t.status == "failed"])
        }


class CrawlerWorkflow:
    """爬虫工作流系统"""

    def __init__(
        self,
        task_queue: TaskQueue = None,
        llm_config_key: str = "deepseek",
        max_concurrent: int = 1
    ):
        """
        初始化工作流系统

        Args:
            task_queue: 任务队列（可选）
            llm_config_key: LLM配置键
            max_concurrent: 最大并发任务数
        """
        self.task_queue = task_queue or TaskQueue()
        self.llm_config_key = llm_config_key
        self.max_concurrent = max_concurrent
        self.running_tasks = set()

    async def execute_task(self, task: CrawlerTask) -> bool:
        """
        执行单个任务

        Args:
            task: 爬虫任务

        Returns:
            是否执行成功
        """
        try:
            # 更新任务状态
            task.status = "running"
            task.started_at = datetime.now().isoformat()
            self.task_queue.update_task(task)
            self.running_tasks.add(task.task_id)

            logger.info(f"开始执行任务: {task.task_id} - {task.name}")

            # 创建爬虫实例
            crawler = SmartCrawler(
                template_path=task.template_path,
                output_dir=task.config.get("output_dir", "output"),
                llm_config_key=self.llm_config_key
            )

            # 执行爬取
            enable_recursive = task.config.get("enable_recursive", False)

            if enable_recursive:
                max_depth = task.config.get("max_depth", 2)
                max_pages = task.config.get("max_pages", 20)
                await crawler.crawl_recursive(
                    task.start_url,
                    max_depth=max_depth,
                    max_pages=max_pages
                )
            else:
                await crawler.crawl_page(task.start_url, depth=0)

            # 保存结果
            result_file = crawler.save_results()

            # 更新任务状态
            task.status = "completed"
            task.completed_at = datetime.now().isoformat()
            task.result_file = result_file
            task.pages_visited = len(crawler.visited_urls)
            task.products_found = len(crawler.products)

            logger.info(f"任务完成: {task.task_id} - 访问{task.pages_visited}页，提取{task.products_found}个产品")

            return True

        except Exception as e:
            logger.error(f"任务执行失败: {task.task_id} - {e}", exc_info=True)
            task.status = "failed"
            task.completed_at = datetime.now().isoformat()
            task.error = str(e)
            return False

        finally:
            self.task_queue.update_task(task)
            self.running_tasks.discard(task.task_id)

    async def run_pending_tasks(self):
        """运行所有待执行任务"""
        pending_tasks = self.task_queue.get_pending_tasks()

        if not pending_tasks:
            logger.info("没有待执行的任务")
            return

        logger.info(f"开始执行 {len(pending_tasks)} 个待执行任务")

        # 根据max_concurrent控制并发
        if self.max_concurrent == 1:
            # 串行执行
            for task in pending_tasks:
                await self.execute_task(task)
        else:
            # 并发执行
            semaphore = asyncio.Semaphore(self.max_concurrent)

            async def execute_with_semaphore(task):
                async with semaphore:
                    await self.execute_task(task)

            await asyncio.gather(*[
                execute_with_semaphore(task)
                for task in pending_tasks
            ])

        logger.info("所有任务执行完成")

    def create_task_from_config(
        self,
        task_id: str,
        name: str,
        start_url: str = None,
        template_path: str = None,
        **kwargs
    ) -> CrawlerTask:
        """
        从配置创建任务

        Args:
            task_id: 任务ID
            name: 任务名称
            start_url: 起始URL（可选，默认从CRAWLER_CONFIG读取）
            template_path: 模板路径（可选，默认从CRAWLER_CONFIG读取）
            **kwargs: 其他配置覆盖

        Returns:
            创建的任务
        """
        config = CRAWLER_CONFIG.copy()
        config.update(kwargs)

        task = CrawlerTask(
            task_id=task_id,
            name=name,
            start_url=start_url or config.get("start_url"),
            template_path=template_path or config.get("template_path"),
            config=config
        )

        self.task_queue.add_task(task)
        return task

    def print_summary(self):
        """打印工作流摘要"""
        summary = self.task_queue.get_summary()

        print("\n" + "="*60)
        print("爬虫工作流摘要")
        print("="*60)
        print(f"总任务数: {summary['total']}")
        print(f"  待执行: {summary['pending']}")
        print(f"  执行中: {summary['running']}")
        print(f"  已完成: {summary['completed']}")
        print(f"  失败: {summary['failed']}")

        print("\n任务列表:")
        for task in self.task_queue.tasks.values():
            status_icon = {
                "pending": "⏳",
                "running": "🔄",
                "completed": "✅",
                "failed": "❌"
            }.get(task.status, "❓")

            print(f"\n{status_icon} [{task.task_id}] {task.name}")
            print(f"   URL: {task.start_url}")
            print(f"   状态: {task.status}")
            if task.status == "completed":
                print(f"   结果: {task.pages_visited}页, {task.products_found}个产品")
                print(f"   文件: {task.result_file}")
            elif task.status == "failed":
                print(f"   错误: {task.error}")

        print("\n" + "="*60)


async def main():
    """主函数 - 演示工作流使用"""
    print("\n🤖 爬虫工作流系统")
    print("="*60)

    # 创建工作流
    workflow = CrawlerWorkflow(
        llm_config_key="deepseek",
        max_concurrent=1  # 串行执行
    )

    # 方案1: 创建多个任务
    print("\n创建示例任务...")

    # 任务1: DeepSeek定价（递归爬取）
    workflow.create_task_from_config(
        task_id="task_001",
        name="DeepSeek定价信息",
        start_url="https://api-docs.deepseek.com/zh-cn/",
        template_path="template_deepseek_pricing.json",
        enable_recursive=True,
        max_depth=2,
        max_pages=10
    )

    # 任务2: DeepSeek定价（单页爬取）
    workflow.create_task_from_config(
        task_id="task_002",
        name="DeepSeek定价信息（单页）",
        start_url="https://api-docs.deepseek.com/zh-cn/quick_start/pricing",
        template_path="template_deepseek_pricing.json",
        enable_recursive=False
    )

    # 打印摘要
    workflow.print_summary()

    # 执行所有待执行任务
    print("\n开始执行任务...")
    await workflow.run_pending_tasks()

    # 打印最终摘要
    workflow.print_summary()

    print("\n🎉 工作流执行完成！\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n🛑 用户中断")
    except Exception as e:
        logger.error(f"🚨 程序异常: {e}", exc_info=True)
