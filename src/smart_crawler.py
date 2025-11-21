#!/usr/bin/env python3
"""
产品信息爬虫 - 基于模板提取结构化数据
根据crawl4ai官方文档实现

使用方法:
    python smart_crawler.py

需要设置环境变量:
    export OPENAI_API_KEY='your-key'
    或
    export DEEPSEEK_API_KEY='your-key'
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, LLMConfig
from crawl4ai.extraction_strategy import LLMExtractionStrategy

# 导入配置
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from configs.config import LLM_CONFIG, CRAWLER_CONFIG

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 启用litellm调试
try:
    import litellm
    # 使用新的环境变量方式
    os.environ['LITELLM_LOG'] = 'DEBUG'
    litellm.set_verbose = True
    logger.info("已启用 litellm 详细日志")
except:
    pass


class SmartCrawler:
    """智能产品信息爬虫 - 使用LLM提取结构化数据"""

    def __init__(
        self,
        template_path: str,
        output_dir: str = None,
        provider: str = None,
        api_token: str = None,
        llm_config_key: str = "deepseek"  # 默认使用deepseek配置
    ):
        """
        初始化爬虫

        Args:
            template_path: JSON模板文件路径（键值对格式）
            output_dir: 输出目录（可选，默认从config读取）
            provider: LLM provider（可选，默认从config读取）
            api_token: API token（可选，默认从config读取）
            llm_config_key: config.py中LLM_CONFIG的键名（默认"deepseek"）
        """
        self.template_path = template_path

        # 从config读取LLM配置
        llm_cfg = LLM_CONFIG.get(llm_config_key, {})

        self.output_dir = Path(output_dir or CRAWLER_CONFIG.get("output_dir", "output"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 加载模板
        with open(template_path, 'r', encoding='utf-8') as f:
            self.template = json.load(f)

        # LLM配置 - 优先使用传入的参数，否则从config读取
        self.provider = provider or llm_cfg.get("provider", "openai/gpt-4o-mini")
        self.api_token = api_token or llm_cfg.get("api_token")

        logger.info(f"从config.py读取配置: provider={self.provider}, api_token={'已设置' if self.api_token else '未设置'}")

        # 爬取结果
        self.visited_urls = set()
        self.products = []

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
            return parsed.scheme in ['http', 'https'] and parsed.netloc == base_domain
        except:
            return False

    async def crawl_page(self, url: str, depth: int = 0):
        """
        爬取单个页面并使用LLM提取数据

        Args:
            url: 目标URL
            depth: 当前递归深度

        Returns:
            提取的数据字典或None
        """
        normalized_url = self._normalize_url(url)

        if normalized_url in self.visited_urls:
            return None

        self.visited_urls.add(normalized_url)
        logger.info(f"[深度{depth}] 爬取: {normalized_url}")

        # 创建LLM提取策略 - 根据crawl4ai最新文档
        llm_config = LLMConfig(
            provider=self.provider,
            api_token=self.api_token
        )

        extraction_instruction = self._create_extraction_instruction()

        # 打印调试信息
        logger.info("="*60)
        logger.info("LLM调用配置:")
        logger.info(f"  Provider: {self.provider}")
        logger.info(f"  API Token: {'已设置' if self.api_token else '未设置'}")
        logger.info(f"  Token前缀: {self.api_token[:10] if self.api_token else 'N/A'}...")
        logger.info(f"  指令长度: {len(extraction_instruction)} 字符")
        logger.info(f"  指令预览: {extraction_instruction[:200]}...")
        logger.info("="*60)

        extraction_strategy = LLMExtractionStrategy(
            llm_config=llm_config,
            instruction=extraction_instruction,
            verbose=True  # 开启verbose看更多调试信息
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

        try:
            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(
                    url=normalized_url,
                    config=run_config
                )

                if result.success and result.extracted_content:
                    try:
                        # 打印原始返回内容用于调试
                        logger.info(f"LLM返回内容: {result.extracted_content[:500]}")

                        # 解析LLM返回的JSON
                        extracted = json.loads(result.extracted_content)

                        # 检查返回格式并提取正确的数据
                        if isinstance(extracted, list):
                            # 如果是列表，检查是否是blocks格式
                            if len(extracted) > 0:
                                first_item = extracted[0] if isinstance(extracted[0], dict) else {}

                                # 检查是否是blocks格式（有index/tags/content字段）
                                if 'index' in first_item and 'content' in first_item:
                                    logger.warning("⚠️ LLM返回了blocks格式，而不是模板格式，跳过此结果")
                                    return None

                                # 检查是否是错误信息
                                if first_item.get('error') is True or 'error' in first_item.get('tags', []):
                                    error_msg = first_item.get('content', '未知错误')
                                    logger.error(f"❌ LLM调用失败: {error_msg}")
                                    return None

                                data = first_item
                            else:
                                data = {}
                        elif isinstance(extracted, dict):
                            # 检查是否是blocks格式
                            if 'index' in extracted and 'content' in extracted:
                                logger.warning("⚠️ LLM返回了blocks格式，而不是模板格式，跳过此结果")
                                return None

                            # 检查字典是否包含错误
                            if extracted.get('error') is True:
                                error_msg = extracted.get('content', extracted.get('message', '未知错误'))
                                logger.error(f"❌ LLM调用失败: {error_msg}")
                                return None
                            data = extracted
                        else:
                            logger.error(f"❌ 意外的返回格式: {type(extracted)}")
                            return None

                        # 验证返回的数据是否包含模板字段
                        template_keys = set(self.template.keys())
                        data_keys = set(k for k in data.keys() if not k.startswith('_'))

                        # 如果返回的字段和模板字段完全不匹配，说明格式不对
                        if not template_keys.intersection(data_keys):
                            logger.warning(f"⚠️ 返回的字段与模板不匹配。模板字段: {template_keys}, 返回字段: {data_keys}")
                            return None

                        # 添加元数据
                        data['_source_url'] = normalized_url
                        data['_crawled_at'] = datetime.now().isoformat()

                        # 检查是否有有效数据
                        has_valid_data = any(
                            v is not None and str(v).strip() != ""
                            for k, v in data.items()
                            if not k.startswith('_')
                        )

                        if has_valid_data:
                            self.products.append(data)
                            logger.info(f"✅ 成功提取数据")
                        else:
                            logger.warning(f"⚠️  未找到有效数据")

                        # 无论是否找到有效数据，都返回result以便继续递归
                        return {
                            'data': data if has_valid_data else None,
                            'result': result,
                            'url': normalized_url
                        }

                    except json.JSONDecodeError as e:
                        logger.error(f"❌ JSON解析失败: {e}")
                        logger.error(f"返回内容: {result.extracted_content[:500]}")
                        return None
                    except Exception as e:
                        logger.error(f"❌ 处理数据异常: {e}")
                        logger.error(f"返回内容: {result.extracted_content[:500]}")
                        return None
                else:
                    logger.error(f"❌ 爬取失败: {result.error_message if not result.success else '无提取内容'}")
                    return None

        except Exception as e:
            logger.error(f"🚨 异常: {e}")
            return None

    async def crawl_recursive(
        self,
        start_url: str,
        max_depth: int = 2,
        max_pages: int = 10
    ):
        """
        递归爬取

        Args:
            start_url: 起始URL
            max_depth: 最大递归深度
            max_pages: 最大爬取页面数

        Returns:
            提取的产品数据列表
        """
        logger.info(f"开始递归爬取: {start_url}")
        logger.info(f"最大深度: {max_depth}, 最大页面数: {max_pages}")

        await self._crawl_recursive_helper(start_url, 0, max_depth, max_pages)

        logger.info(f"爬取完成: 访问{len(self.visited_urls)}页, 提取{len(self.products)}个产品")
        return self.products

    async def _crawl_recursive_helper(
        self,
        url: str,
        current_depth: int,
        max_depth: int,
        max_pages: int
    ):
        """递归爬取辅助函数"""
        if current_depth > max_depth or len(self.visited_urls) >= max_pages:
            return

        # 爬取当前页面
        page_result = await self.crawl_page(url, current_depth)
        if not page_result:
            return

        # 延迟
        await asyncio.sleep(1)

        # 递归爬取链接
        if current_depth < max_depth:
            result = page_result.get('result')
            if result and hasattr(result, 'links') and result.links:
                base_domain = urlparse(url).netloc
                internal_links = result.links.get('internal', [])

                # 提取URL
                urls = []
                for link in internal_links:
                    if isinstance(link, dict):
                        link_url = link.get('href', '')
                    else:
                        link_url = str(link)

                    if link_url:
                        full_url = urljoin(url, link_url)
                        normalized = self._normalize_url(full_url)

                        if normalized not in self.visited_urls and self._is_valid_url(normalized, base_domain):
                            urls.append(full_url)

                # 限制链接数
                for link_url in urls[:5]:
                    if len(self.visited_urls) >= max_pages:
                        break
                    await self._crawl_recursive_helper(link_url, current_depth + 1, max_depth, max_pages)

    def save_results(self):
        """保存结果到JSON文件"""
        if not self.products:
            logger.warning("没有数据可保存")
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.output_dir / f"products_{timestamp}.json"

        output = {
            "template": self.template,
            "crawl_info": {
                "pages_visited": len(self.visited_urls),
                "products_found": len(self.products),
                "crawled_at": datetime.now().isoformat()
            },
            "products": self.products
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        logger.info(f"💾 已保存到: {filename}")
        return filename

    def print_summary(self):
        """打印摘要"""
        print("\n" + "="*60)
        print("爬取摘要")
        print("="*60)
        print(f"访问页面: {len(self.visited_urls)}")
        print(f"提取产品: {len(self.products)}")

        if self.products:
            print(f"\n提取的数据:")
            for i, product in enumerate(self.products, 1):
                print(f"\n【产品 {i}】")
                print(f"来源: {product.get('_source_url', 'Unknown')}")
                for key, value in product.items():
                    if not key.startswith('_'):
                        print(f"  {key}: {value}")

        print("\n" + "="*60)


async def main():
    """主函数 - 从config.py读取配置爬取"""
    print("\n🤖 智能产品信息爬虫")
    print("="*60)

    # 创建爬虫 - 自动从config.py读取配置
    crawler = SmartCrawler(
        template_path=CRAWLER_CONFIG.get("template_path"),
        llm_config_key="deepseek"  # 使用config.py中的deepseek配置
    )

    # 从config读取配置
    url = CRAWLER_CONFIG.get("start_url", "https://api-docs.deepseek.com/zh-cn/quick_start/pricing")
    enable_recursive = CRAWLER_CONFIG.get("enable_recursive", False)
    max_depth = CRAWLER_CONFIG.get("max_depth", 2)
    max_pages = CRAWLER_CONFIG.get("max_pages", 20)

    print(f"\n目标URL: {url}")
    print(f"模板文件: {crawler.template_path}")
    print(f"LLM Provider: {crawler.provider}")
    print(f"递归爬取: {'启用' if enable_recursive else '禁用'}")
    if enable_recursive:
        print(f"最大深度: {max_depth}, 最大页面数: {max_pages}")
    print()

    # 根据配置决定是否递归爬取
    if enable_recursive:
        await crawler.crawl_recursive(url, max_depth=max_depth, max_pages=max_pages)
    else:
        await crawler.crawl_page(url, depth=0)

    # 保存结果
    crawler.save_results()

    # 打印摘要
    crawler.print_summary()

    print("\n🎉 完成！\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n🛑 用户中断")
    except Exception as e:
        logger.error(f"🚨 程序异常: {e}", exc_info=True)
