#!/usr/bin/env python3
"""
两阶段爬取策略（支持断点续爬）
阶段1: 快速递归爬取所有链接（不使用LLM，节省token）
阶段2: 根据URL模式过滤产品页，详细爬取并LLM分析

特性：
- 链接列表带爬取状态标记
- 支持断点续爬
- 批次爬取大网站
"""

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from typing import List, Set, Dict, Optional
import logging

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, LLMConfig
from crawl4ai.extraction_strategy import LLMExtractionStrategy

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from configs.config import LLM_CONFIG, CRAWLER_CONFIG

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TwoStageCrawler:
    """两阶段爬取器（支持断点续爬）"""

    def __init__(
        self,
        task_name: str,
        start_url: str,
        template_path: str = None,
        output_dir: str = "output",
        llm_config_key: str = "deepseek"
    ):
        """
        初始化爬虫

        Args:
            task_name: 任务名称（用于创建输出目录）
            start_url: 起始URL
            template_path: 模板文件路径（阶段2使用）
            output_dir: 输出根目录
            llm_config_key: LLM配置键
        """
        self.task_name = task_name
        self.start_url = start_url
        self.template_path = template_path

        # 任务输出目录：output/任务名称/
        self.task_output_dir = Path(output_dir) / task_name
        self.task_output_dir.mkdir(parents=True, exist_ok=True)

        # LLM配置
        llm_cfg = LLM_CONFIG.get(llm_config_key, {})
        self.provider = llm_cfg.get("provider")
        self.api_token = llm_cfg.get("api_token")

        # 加载模板
        self.template = None
        if template_path:
            with open(template_path, 'r', encoding='utf-8') as f:
                self.template = json.load(f)

        # 数据存储
        self.all_links: List[Dict] = []  # 链接列表（带状态）
        self.visited_urls: Set[str] = set()  # 已访问的URL
        self.products = []  # 提取的产品数据

        # 文件路径
        self.links_file = self.task_output_dir / "collected_links.json"
        self.products_file = self.task_output_dir / "products.json"
        self.stage1_flag = self.task_output_dir / ".stage1_completed"

        logger.info(f"任务输出目录: {self.task_output_dir}")

    def _normalize_url(self, url: str) -> str:
        """标准化URL"""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    def _is_same_domain(self, url: str, base_url: str) -> bool:
        """检查是否同域名"""
        try:
            url_domain = urlparse(url).netloc
            base_domain = urlparse(base_url).netloc
            return url_domain == base_domain
        except:
            return False

    def is_stage1_completed(self) -> bool:
        """检查阶段1是否已完成"""
        return self.stage1_flag.exists() and self.links_file.exists()

    def load_links(self) -> List[Dict]:
        """从文件加载链接列表"""
        if not self.links_file.exists():
            logger.warning(f"链接文件不存在: {self.links_file}")
            return []

        with open(self.links_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        links = data.get("links", [])
        logger.info(f"从文件加载了 {len(links)} 个链接")

        # 统计已爬取数量
        crawled_count = sum(1 for link in links if link.get("crawled", False))
        logger.info(f"其中已爬取: {crawled_count} 个，未爬取: {len(links) - crawled_count} 个")

        return links

    def _save_links(self, mark_stage1_complete: bool = True):
        """
        保存链接列表

        Args:
            mark_stage1_complete: 是否标记阶段1完成
        """
        data = {
            "task_name": self.task_name,
            "start_url": self.start_url,
            "collected_at": datetime.now().isoformat(),
            "total_links": len(self.all_links),
            "crawled_count": sum(1 for link in self.all_links if link.get("crawled", False)),
            "links": self.all_links
        }

        with open(self.links_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"💾 链接已保存到: {self.links_file}")

        # 标记阶段1完成
        if mark_stage1_complete:
            self.stage1_flag.touch()
            logger.info("✅ 阶段1已标记为完成")

    async def stage1_collect_links(
        self,
        max_depth: int = 3,
        max_pages: int = 100,
        force: bool = False
    ) -> List[Dict]:
        """
        阶段1: 快速递归爬取，收集所有链接

        Args:
            max_depth: 最大递归深度
            max_pages: 最大爬取页面数
            force: 是否强制重新爬取（即使阶段1已完成）

        Returns:
            收集到的所有链接（带状态）
        """
        # 检查是否已完成阶段1
        if not force and self.is_stage1_completed():
            logger.info("="*60)
            logger.info("⚠️  阶段1已完成，跳过")
            logger.info(f"如需重新爬取，请删除文件: {self.stage1_flag}")
            logger.info("或使用 force=True 参数")
            logger.info("="*60)
            self.all_links = self.load_links()
            return self.all_links

        logger.info("="*60)
        logger.info("阶段1: 收集所有链接（不使用LLM）")
        logger.info(f"任务名称: {self.task_name}")
        logger.info(f"起始URL: {self.start_url}")
        logger.info(f"最大深度: {max_depth}, 最大页面数: {max_pages}")
        logger.info("="*60)

        await self._collect_links_recursive(
            self.start_url,
            current_depth=0,
            max_depth=max_depth,
            max_pages=max_pages
        )

        logger.info(f"阶段1完成: 访问了 {len(self.visited_urls)} 个页面，收集到 {len(self.all_links)} 个链接")

        # 保存收集到的链接并标记阶段1完成
        self._save_links(mark_stage1_complete=True)

        return self.all_links

    async def _collect_links_recursive(
        self,
        url: str,
        current_depth: int,
        max_depth: int,
        max_pages: int
    ):
        """递归收集链接"""
        if current_depth > max_depth or len(self.visited_urls) >= max_pages:
            return

        normalized_url = self._normalize_url(url)

        if normalized_url in self.visited_urls:
            return

        self.visited_urls.add(normalized_url)
        logger.info(f"[深度{current_depth}] 访问: {normalized_url}")

        # 爬取页面（不使用LLM）
        browser_config = BrowserConfig(headless=True, verbose=False)
        run_config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)

        try:
            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=normalized_url, config=run_config)

                if result.success and hasattr(result, 'links') and result.links:
                    internal_links = result.links.get('internal', [])

                    # 提取链接
                    new_links = []
                    for link in internal_links:
                        if isinstance(link, dict):
                            link_url = link.get('href', '')
                        else:
                            link_url = str(link)

                        if link_url:
                            full_url = urljoin(url, link_url)
                            normalized = self._normalize_url(full_url)

                            # 只收集同域名的链接
                            if self._is_same_domain(normalized, self.start_url):
                                # 检查是否已添加
                                if not any(l['url'] == normalized for l in self.all_links):
                                    self.all_links.append({
                                        "url": normalized,
                                        "crawled": False,
                                        "discovered_at": datetime.now().isoformat(),
                                        "depth": current_depth + 1
                                    })

                                if normalized not in self.visited_urls:
                                    new_links.append(normalized)

                    # 延迟
                    await asyncio.sleep(0.5)

                    # 递归爬取（限制数量）
                    if current_depth < max_depth:
                        for link_url in new_links[:5]:  # 每页最多爬5个子链接
                            if len(self.visited_urls) >= max_pages:
                                break
                            await self._collect_links_recursive(
                                link_url,
                                current_depth + 1,
                                max_depth,
                                max_pages
                            )
                else:
                    logger.warning(f"爬取失败或无链接: {normalized_url}")

        except Exception as e:
            logger.error(f"爬取异常: {normalized_url} - {e}")

    def filter_product_links(
        self,
        url_patterns: List[str] = None,
        only_uncrawled: bool = True
    ) -> List[Dict]:
        """
        过滤出产品链接

        Args:
            url_patterns: URL匹配模式列表，支持两种格式：
                         1. 字符串包含匹配：如 "/product/", "/item/"
                         2. 正则表达式（以regex:开头）：如 "regex:/\\d+\\.html$"
            only_uncrawled: 是否只返回未爬取的链接

        Returns:
            过滤后的产品链接列表

        示例:
            # 匹配 /product/ 路径
            filter_product_links(["/product/", "/item/"])

            # 匹配数字ID.html格式（如 /34435.html）
            filter_product_links(["regex:/\\d+\\.html$"])

            # 混合使用
            filter_product_links(["/product/", "regex:/\\d+\\.html$"])
        """
        # 从文件加载（如果all_links为空）
        if not self.all_links:
            self.all_links = self.load_links()

        if not self.all_links:
            logger.warning("没有可用的链接")
            return []

        # 编译正则表达式模式
        compiled_patterns = []
        string_patterns = []

        if url_patterns:
            for pattern in url_patterns:
                if pattern.startswith("regex:"):
                    # 正则表达式模式
                    regex_str = pattern[6:]  # 移除 "regex:" 前缀
                    try:
                        compiled_patterns.append(re.compile(regex_str))
                        logger.info(f"  使用正则: {regex_str}")
                    except re.error as e:
                        logger.warning(f"  正则表达式错误: {regex_str} - {e}")
                else:
                    # 字符串包含模式
                    string_patterns.append(pattern)
                    logger.info(f"  使用字符串匹配: {pattern}")

        # 应用URL模式过滤
        filtered_links = []
        for link in self.all_links:
            url = link['url']

            # URL模式匹配
            if url_patterns:
                matched = False

                # 检查字符串包含匹配
                if string_patterns and any(pattern in url for pattern in string_patterns):
                    matched = True

                # 检查正则表达式匹配
                if compiled_patterns and any(pattern.search(url) for pattern in compiled_patterns):
                    matched = True

                if not matched:
                    continue

            # 爬取状态过滤
            if only_uncrawled and link.get('crawled', False):
                continue

            filtered_links.append(link)

        # 统计信息
        total_matched = 0
        if url_patterns:
            for link in self.all_links:
                url = link['url']
                if string_patterns and any(p in url for p in string_patterns):
                    total_matched += 1
                elif compiled_patterns and any(p.search(url) for p in compiled_patterns):
                    total_matched += 1

        crawled_count = sum(1 for l in self.all_links if l.get('crawled', False))

        logger.info(f"链接过滤结果:")
        logger.info(f"  总链接数: {len(self.all_links)}")
        if url_patterns:
            logger.info(f"  匹配模式的: {total_matched}")
        logger.info(f"  已爬取: {crawled_count}")
        logger.info(f"  待爬取（本次）: {len(filtered_links)}")

        return filtered_links

    def _create_extraction_instruction(self) -> str:
        """创建LLM提取指令"""
        if not self.template:
            raise ValueError("未设置模板")

        template_str = json.dumps(self.template, ensure_ascii=False, indent=2)

        instruction = f"""
从网页内容中提取产品信息，严格按照以下JSON格式返回。

模板定义（键是字段名，值是字段说明）：
{template_str}

**重要要求**：
1. 直接返回一个JSON对象，不要返回数组或其他格式
2. JSON对象的键必须完全匹配模板中的键名
3. 每个键的值是从网页中提取的实际数据
4. 如果某个字段在网页中找不到，设置为 null
5. 不要添加 index, tags, content, error 等额外字段
6. 不要使用 blocks 格式
7. 只返回纯JSON对象，不要任何其他内容

再次强调：直接返回一个JSON对象，包含模板中定义的所有字段。
"""
        return instruction

    def _mark_link_crawled(self, url: str):
        """标记链接为已爬取"""
        for link in self.all_links:
            if link['url'] == url:
                link['crawled'] = True
                link['crawled_at'] = datetime.now().isoformat()
                break

        # 更新文件
        self._save_links(mark_stage1_complete=False)

    async def stage2_extract_products(
        self,
        product_links: List[Dict] = None,
        url_patterns: List[str] = None,
        batch_size: int = None,
        save_interval: int = 5
    ) -> List[Dict]:
        """
        阶段2: 详细爬取产品页并用LLM提取数据

        Args:
            product_links: 产品链接列表（如果为None，自动根据url_patterns过滤）
            url_patterns: URL匹配模式（如果product_links为None时使用）
            batch_size: 批次大小（每次爬取多少个链接，None表示全部）
            save_interval: 每爬取多少个保存一次

        Returns:
            提取的产品数据列表
        """
        logger.info("="*60)
        logger.info("阶段2: 详细爬取产品页并LLM分析")
        logger.info(f"任务名称: {self.task_name}")
        logger.info("="*60)

        # 自动过滤产品链接
        if product_links is None:
            if url_patterns is None:
                raise ValueError("必须提供 product_links 或 url_patterns")
            product_links = self.filter_product_links(url_patterns=url_patterns, only_uncrawled=True)

        if not product_links:
            logger.warning("没有待爬取的产品链接")
            return self.products

        # 批次限制
        if batch_size:
            product_links = product_links[:batch_size]
            logger.info(f"批次大小限制: {batch_size} 个链接")

        logger.info(f"待爬取产品数: {len(product_links)}")

        if not self.template:
            raise ValueError("未设置模板，无法进行LLM提取")

        # 加载已有产品数据（断点续爬）
        if self.products_file.exists():
            with open(self.products_file, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
                self.products = existing_data.get("products", [])
            logger.info(f"已加载 {len(self.products)} 个已提取的产品")

        # 创建LLM提取策略
        llm_config = LLMConfig(
            provider=self.provider,
            api_token=self.api_token
        )

        extraction_strategy = LLMExtractionStrategy(
            llm_config=llm_config,
            instruction=self._create_extraction_instruction(),
            verbose=True
        )

        browser_config = BrowserConfig(headless=True, verbose=False)
        run_config = CrawlerRunConfig(
            extraction_strategy=extraction_strategy,
            cache_mode=CacheMode.BYPASS
        )

        async with AsyncWebCrawler(config=browser_config) as crawler:
            for i, link_info in enumerate(product_links, 1):
                url = link_info['url']
                logger.info(f"[{i}/{len(product_links)}] 爬取: {url}")

                try:
                    result = await crawler.arun(url=url, config=run_config)

                    if result.success and result.extracted_content:
                        extracted = json.loads(result.extracted_content)

                        # 处理返回格式
                        if isinstance(extracted, list) and len(extracted) > 0:
                            data = extracted[0]
                        elif isinstance(extracted, dict):
                            data = extracted
                        else:
                            logger.warning(f"意外的返回格式: {type(extracted)}")
                            self._mark_link_crawled(url)
                            continue

                        # 检查是否是blocks格式
                        if 'index' in data and 'content' in data:
                            logger.warning(f"返回了blocks格式，跳过")
                            self._mark_link_crawled(url)
                            continue

                        # 添加元数据
                        data['_source_url'] = url
                        data['_crawled_at'] = datetime.now().isoformat()

                        # 检查是否有有效数据
                        has_data = any(
                            v is not None and str(v).strip() != ""
                            for k, v in data.items()
                            if not k.startswith('_')
                        )

                        if has_data:
                            self.products.append(data)
                            logger.info(f"✅ 成功提取数据")
                        else:
                            logger.warning(f"未找到有效数据")

                        # 标记为已爬取
                        self._mark_link_crawled(url)

                    else:
                        logger.error(f"爬取失败: {result.error_message if not result.success else '无提取内容'}")
                        # 即使失败也标记为已爬取，避免重复
                        self._mark_link_crawled(url)

                except Exception as e:
                    logger.error(f"处理异常: {url} - {e}")
                    # 即使异常也标记为已爬取
                    self._mark_link_crawled(url)

                # 定期保存
                if i % save_interval == 0:
                    self._save_products()
                    logger.info(f"💾 已保存进度 ({i}/{len(product_links)})")

                # 延迟
                await asyncio.sleep(1)

        # 最终保存
        self._save_products()

        logger.info(f"阶段2完成: 成功提取 {len(self.products)} 个产品")
        return self.products

    def _save_products(self):
        """保存产品数据"""
        if not self.products:
            return

        output = {
            "task_name": self.task_name,
            "template": self.template,
            "crawl_info": {
                "start_url": self.start_url,
                "total_links_collected": len(self.all_links),
                "products_extracted": len(self.products),
                "last_updated": datetime.now().isoformat()
            },
            "products": self.products
        }

        with open(self.products_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        logger.info(f"💾 产品数据已保存到: {self.products_file}")

    def save_products(self) -> Path:
        """保存产品数据（对外接口）"""
        self._save_products()
        return self.products_file

    def print_summary(self):
        """打印摘要"""
        # 统计信息
        total_links = len(self.all_links)
        crawled_links = sum(1 for link in self.all_links if link.get('crawled', False))
        uncrawled_links = total_links - crawled_links

        print("\n" + "="*60)
        print("爬取摘要")
        print("="*60)
        print(f"任务名称: {self.task_name}")
        print(f"起始URL: {self.start_url}")
        print(f"输出目录: {self.task_output_dir}")
        print()
        print(f"链接统计:")
        print(f"  收集总数: {total_links}")
        print(f"  已爬取: {crawled_links}")
        print(f"  未爬取: {uncrawled_links}")
        print()
        print(f"产品统计:")
        print(f"  提取产品数: {len(self.products)}")

        if self.products:
            print(f"\n最近提取的产品:")
            for i, product in enumerate(self.products[-3:], 1):
                print(f"\n【产品 {i}】")
                print(f"来源: {product.get('_source_url', 'Unknown')}")
                for key, value in product.items():
                    if not key.startswith('_'):
                        print(f"  {key}: {value}")

            if len(self.products) > 3:
                print(f"\n... 还有 {len(self.products) - 3} 个产品")

        print("\n文件位置:")
        print(f"  链接文件: {self.links_file}")
        print(f"  产品文件: {self.products_file}")
        print("="*60)

    async def run(
        self,
        url_patterns: List[str],
        stage1_max_depth: int = 3,
        stage1_max_pages: int = 100,
        stage2_batch_size: int = None,
        force_stage1: bool = False
    ):
        """
        完整运行两阶段爬取（自动断点续爬）

        Args:
            url_patterns: URL匹配模式
            stage1_max_depth: 阶段1最大深度
            stage1_max_pages: 阶段1最大页面数
            stage2_batch_size: 阶段2批次大小
            force_stage1: 是否强制重新执行阶段1
        """
        # 阶段1: 收集链接（如果未完成）
        await self.stage1_collect_links(
            max_depth=stage1_max_depth,
            max_pages=stage1_max_pages,
            force=force_stage1
        )

        # 阶段2: 提取产品
        await self.stage2_extract_products(
            url_patterns=url_patterns,
            batch_size=stage2_batch_size
        )

        # 打印摘要
        self.print_summary()


async def main():
    """主函数 - 演示两阶段爬取（支持断点续爬）"""
    print("\n🤖 两阶段智能爬虫（支持断点续爬）")
    print("="*60)

    # 创建爬虫
    crawler = TwoStageCrawler(
        task_name="deepseek_pricing",  # 任务名称
        start_url="https://api-docs.deepseek.com/zh-cn/",
        template_path="templates/template_deepseek_pricing.json",
        llm_config_key="deepseek"
    )

    # 一键运行（自动检测断点）
    await crawler.run(
        url_patterns=["/pricing", "/quick_start"],
        stage1_max_depth=3,
        stage1_max_pages=50,
        stage2_batch_size=10  # 每次最多爬10个产品页
    )

    print("\n🎉 完成！\n")


def load_tasks_from_config(config_path: str) -> List[Dict]:
    """
    从配置文件加载任务列表

    Args:
        config_path: 配置文件路径

    Returns:
        任务配置列表
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    return config.get("tasks", [])


async def run_from_config(config_path: str, task_id: str = None):
    """
    从配置文件运行任务

    Args:
        config_path: 配置文件路径
        task_id: 指定任务ID，为None则运行所有任务
    """
    print("\n🤖 两阶段智能爬虫（从配置文件加载）")
    print("="*60)
    print(f"配置文件: {config_path}")
    print("="*60)

    # 加载任务配置
    tasks = load_tasks_from_config(config_path)

    if not tasks:
        logger.error("配置文件中没有任务")
        return

    # 过滤指定任务
    if task_id:
        tasks = [t for t in tasks if t.get("task_id") == task_id]
        if not tasks:
            logger.error(f"未找到任务: {task_id}")
            return

    logger.info(f"待运行任务数: {len(tasks)}")

    # 运行每个任务
    for i, task_config in enumerate(tasks, 1):
        tid = task_config.get("task_id", f"task_{i}")
        task_name = task_config.get("task_name", tid)
        start_url = task_config.get("start_url")
        template_path = task_config.get("template_path")

        # 阶段1配置
        stage1 = task_config.get("stage1", {})
        max_depth = stage1.get("max_depth", 3)
        max_pages = stage1.get("max_pages", 100)

        # 阶段2配置
        stage2 = task_config.get("stage2", {})
        url_patterns = stage2.get("url_patterns", [])
        batch_size = stage2.get("batch_size", None)

        print(f"\n[{i}/{len(tasks)}] 运行任务: {task_name}")
        print(f"  起始URL: {start_url}")
        print(f"  模板: {template_path}")
        print(f"  阶段1: 深度={max_depth}, 最大页面={max_pages}")
        print(f"  阶段2: 模式={url_patterns}, 批次={batch_size}")

        # 创建爬虫
        crawler = TwoStageCrawler(
            task_name=task_name,
            start_url=start_url,
            template_path=template_path,
            llm_config_key="deepseek"
        )

        # 运行
        await crawler.run(
            url_patterns=url_patterns,
            stage1_max_depth=max_depth,
            stage1_max_pages=max_pages,
            stage2_batch_size=batch_size
        )

        print(f"\n✅ 任务 {task_name} 完成")

    print("\n🎉 所有任务完成！\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='两阶段智能爬虫')
    parser.add_argument('--config', '-f', nargs='?', help='配置文件路径')
    parser.add_argument('--task', '-t', help='指定任务ID')

    args = parser.parse_args()

    try:
        if args.config:
            # 从配置文件运行
            asyncio.run(run_from_config(args.config, args.task))
        else:
            # 运行默认演示
            asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n🛑 用户中断")
    except Exception as e:
        logger.error(f"🚨 程序异常: {e}", exc_info=True)

