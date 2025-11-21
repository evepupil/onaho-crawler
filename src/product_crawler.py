#!/usr/bin/env python3
"""
产品信息爬虫
使用LLM根据模板提取结构化数据
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

try:
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, LLMConfig
    from crawl4ai.extraction_strategy import LLMExtractionStrategy
except ImportError:
    print("请先安装crawl4ai: pip install crawl4ai")
    exit(1)

# 导入配置
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from configs.config import LLM_CONFIG, CRAWLER_CONFIG

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('product_crawler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ProductCrawler:
    """产品信息爬虫 - 使用LLM提取结构化数据"""

    def __init__(
        self,
        template_path: str = None,
        output_dir: str = None,
        api_token: str = None,
        provider: str = None,
        llm_config_key: str = "deepseek"
    ):
        """
        初始化爬虫

        Args:
            template_path: JSON模板文件路径（可选，默认从config读取）
            output_dir: 输出目录（可选，默认从config读取）
            api_token: LLM API token（可选，默认从config读取）
            provider: LLM provider（可选，默认从config读取）
            llm_config_key: config.py中LLM_CONFIG的键名（默认"deepseek"）
        """
        # 从config读取LLM配置
        llm_cfg = LLM_CONFIG.get(llm_config_key, {})

        self.template_path = template_path or CRAWLER_CONFIG.get("template_path", "template_deepseek_pricing.json")
        self.output_dir = Path(output_dir or CRAWLER_CONFIG.get("output_dir", "output"))
        self.output_dir.mkdir(exist_ok=True)

        # 加载模板
        with open(self.template_path, 'r', encoding='utf-8') as f:
            self.template = json.load(f)

        # LLM配置 - 优先使用传入的参数，否则从config读取
        self.api_token = api_token or llm_cfg.get("api_token")
        self.provider = provider or llm_cfg.get("provider", "openai/gpt-4o-mini")

        logger.info(f"从config.py读取配置: provider={self.provider}, api_token={'已设置' if self.api_token else '未设置'}")

        # 爬取统计
        self.visited_urls = set()
        self.products_data = []

    def _create_extraction_instruction(self) -> str:
        """根据模板创建LLM提取指令"""
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

必须严格遵守的返回格式示例：
{{
{chr(10).join([f'  "{k}": "实际提取的值"' for k in self.template.keys()])}
}}

再次强调：直接返回一个JSON对象，包含模板中定义的所有字段，不要任何包装或额外结构。
"""
        return instruction

    def _normalize_url(self, url: str) -> str:
        """标准化URL"""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    def _is_valid_url(self, url: str, base_domain: str) -> bool:
        """检查URL是否有效"""
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ['http', 'https']:
                return False
            return parsed.netloc == base_domain
        except:
            return False

    async def crawl_single_page(self, url: str, depth: int = 0):
        """爬取单个页面并使用LLM提取数据"""
        normalized_url = self._normalize_url(url)

        if normalized_url in self.visited_urls:
            return None

        self.visited_urls.add(normalized_url)
        logger.info(f"[深度{depth}] 正在爬取: {normalized_url}")

        # 创建LLM提取策略 - 使用新的API
        llm_config = LLMConfig(
            provider=self.provider,
            api_token=self.api_token
        )

        extraction_strategy = LLMExtractionStrategy(
            llm_config=llm_config,
            instruction=self._create_extraction_instruction(),
            verbose=True
        )

        # 浏览器配置
        browser_config = BrowserConfig(
            headless=True,
            verbose=False
        )

        # 爬取配置
        run_config = CrawlerRunConfig(
            extraction_strategy=extraction_strategy,
            cache_mode=CacheMode.BYPASS
        )

        async with AsyncWebCrawler(config=browser_config) as crawler:
            try:
                result = await crawler.arun(
                    url=normalized_url,
                    config=run_config
                )

                if result.success:
                    # 解析LLM提取的JSON
                    if result.extracted_content:
                        try:
                            logger.info(f"LLM返回内容: {result.extracted_content[:500]}")
                            extracted_data = json.loads(result.extracted_content)

                            # 检查返回格式并提取正确的数据
                            if isinstance(extracted_data, list):
                                # 如果是列表，检查是否是blocks格式
                                if len(extracted_data) > 0:
                                    first_item = extracted_data[0] if isinstance(extracted_data[0], dict) else {}

                                    # 检查是否是blocks格式（有index/tags/content字段）
                                    if 'index' in first_item and 'content' in first_item:
                                        logger.warning("⚠️ LLM返回了blocks格式，而不是模板格式，跳过此结果")
                                        return None

                                    # 检查是否是错误信息
                                    if first_item.get('error') is True or 'error' in first_item.get('tags', []):
                                        error_msg = first_item.get('content', '未知错误')
                                        logger.error(f"❌ LLM调用失败: {error_msg}")
                                        return None

                                    extracted_data = first_item
                                else:
                                    extracted_data = {}
                            elif isinstance(extracted_data, dict):
                                # 检查是否是blocks格式
                                if 'index' in extracted_data and 'content' in extracted_data:
                                    logger.warning("⚠️ LLM返回了blocks格式，而不是模板格式，跳过此结果")
                                    return None

                                # 检查字典是否包含错误
                                if extracted_data.get('error') is True:
                                    error_msg = extracted_data.get('content', extracted_data.get('message', '未知错误'))
                                    logger.error(f"❌ LLM调用失败: {error_msg}")
                                    return None
                            else:
                                logger.error(f"❌ 意外的返回格式: {type(extracted_data)}")
                                return None

                            # 验证返回的数据是否包含模板字段
                            template_keys = set(self.template.keys())
                            data_keys = set(k for k in extracted_data.keys() if not k.startswith('_'))

                            # 如果返回的字段和模板字段完全不匹配，说明格式不对
                            if not template_keys.intersection(data_keys):
                                logger.warning(f"⚠️ 返回的字段与模板不匹配。模板字段: {template_keys}, 返回字段: {data_keys}")
                                return None

                            # 添加源URL
                            extracted_data['_source_url'] = normalized_url
                            extracted_data['_crawled_at'] = datetime.now().isoformat()

                            # 检查是否有有效数据
                            has_data = any(
                                value is not None and value != ""
                                for key, value in extracted_data.items()
                                if not key.startswith('_')
                            )

                            if has_data:
                                self.products_data.append(extracted_data)
                                logger.info(f"✅ 成功提取数据: {normalized_url}")
                            else:
                                logger.warning(f"未找到有效数据: {normalized_url}")

                            # 无论是否找到有效数据，都返回result以便继续递归
                            return {
                                'data': extracted_data if has_data else None,
                                'result': result,
                                'url': normalized_url
                            }

                        except json.JSONDecodeError as e:
                            logger.error(f"JSON解析失败: {normalized_url} - {e}")
                            logger.error(f"返回内容: {result.extracted_content[:500]}")
                            return None
                    else:
                        logger.warning(f"LLM未返回内容: {normalized_url}")
                        return None
                else:
                    logger.error(f"❌ 爬取失败: {normalized_url} - {result.error_message}")
                    return None

            except Exception as e:
                logger.error(f"🚨 爬取异常: {normalized_url} - {e}")
                return None

    async def recursive_crawl(self, start_url: str, max_depth: int = 2, max_pages: int = 10):
        """递归爬取"""
        logger.info(f"开始递归爬取，起始URL: {start_url}, 最大深度: {max_depth}")

        await self._crawl_recursive_helper(start_url, 0, max_depth, max_pages)

        logger.info(f"递归爬取完成，共访问 {len(self.visited_urls)} 个页面，提取 {len(self.products_data)} 条数据")
        return self.products_data

    async def _crawl_recursive_helper(self, url: str, current_depth: int, max_depth: int, max_pages: int):
        """递归爬取辅助函数"""
        if current_depth > max_depth:
            return

        if len(self.visited_urls) >= max_pages:
            return

        # 爬取当前页面
        page_result = await self.crawl_single_page(url, current_depth)
        if not page_result:
            return

        # 延迟
        await asyncio.sleep(1)

        # 递归爬取链接
        if current_depth < max_depth and page_result.get('result'):
            result = page_result['result']
            if hasattr(result, 'links') and result.links:
                base_domain = urlparse(url).netloc
                all_links = []

                # 提取内部链接
                for link in result.links.get('internal', []):
                    if isinstance(link, dict):
                        link_url = link.get('href', '')
                    else:
                        link_url = str(link)

                    if link_url:
                        full_url = urljoin(url, link_url)
                        normalized_url = self._normalize_url(full_url)

                        if normalized_url not in self.visited_urls and self._is_valid_url(normalized_url, base_domain):
                            all_links.append(full_url)

                # 限制链接数量
                for link in all_links[:10]:
                    if len(self.visited_urls) >= max_pages:
                        break

                    await self._crawl_recursive_helper(link, current_depth + 1, max_depth, max_pages)

    def save_results(self):
        """保存结果"""
        if not self.products_data:
            logger.warning("没有数据可保存")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.output_dir / f"products_{timestamp}.json"

        output_data = {
            "template": self.template,
            "crawl_info": {
                "total_pages_visited": len(self.visited_urls),
                "total_products_found": len(self.products_data),
                "crawled_at": datetime.now().isoformat()
            },
            "products": self.products_data
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        logger.info(f"💾 数据已保存到: {filename}")
        return filename

    def print_summary(self):
        """打印摘要"""
        print("\n" + "="*60)
        print("爬取摘要")
        print("="*60)
        print(f"📄 访问页面数: {len(self.visited_urls)}")
        print(f"📊 提取产品数: {len(self.products_data)}")

        if self.products_data:
            print(f"\n提取的产品:")
            for i, product in enumerate(self.products_data, 1):
                print(f"\n{i}. 来源: {product.get('_source_url', 'Unknown')}")
                for key, value in product.items():
                    if not key.startswith('_'):
                        print(f"   {key}: {value}")

        print(f"\n💾 数据保存位置: {self.output_dir}")
        print("="*60)


async def main():
    """主函数 - 从config.py读取配置爬取"""
    print("🤖 开始爬取产品信息...")
    print("="*60)

    # 创建爬虫 - 自动从config.py读取所有配置
    crawler = ProductCrawler(
        llm_config_key="deepseek"  # 使用config.py中的deepseek配置
    )

    # 从config读取配置
    start_url = CRAWLER_CONFIG.get("start_url", "https://api-docs.deepseek.com/zh-cn/")
    enable_recursive = CRAWLER_CONFIG.get("enable_recursive", False)
    max_depth = CRAWLER_CONFIG.get("max_depth", 2)
    max_pages = CRAWLER_CONFIG.get("max_pages", 20)

    print(f"目标URL: {start_url}")
    print(f"模板文件: {crawler.template_path}")
    print(f"LLM Provider: {crawler.provider}")
    print(f"递归爬取: {'启用' if enable_recursive else '禁用'}")
    if enable_recursive:
        print(f"最大深度: {max_depth}, 最大页面数: {max_pages}")
    print()

    # 根据配置决定是否递归爬取
    if enable_recursive:
        await crawler.recursive_crawl(start_url, max_depth=max_depth, max_pages=max_pages)
    else:
        await crawler.crawl_single_page(start_url, depth=0)

    # 保存结果
    crawler.save_results()

    # 打印摘要
    crawler.print_summary()

    print(f"\n🎉 爬取完成！")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n🛑 爬取被用户中断")
    except Exception as e:
        logger.error(f"🚨 程序异常: {e}")
        print(f"🚨 程序异常: {e}")
