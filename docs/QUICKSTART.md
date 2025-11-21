# 爬虫工作流系统 - 快速开始

## 一、安装依赖

```bash
pip install crawl4ai litellm
```

## 二、配置系统

### 1. 配置 LLM API
编辑 `config.py`，设置你的 API Key:

```python
LLM_CONFIG = {
    "deepseek": {
        "provider": "deepseek/deepseek-chat",
        "api_token": "your-deepseek-api-key",  # 替换为你的API key
        "base_url": "https://api.deepseek.com"
    }
}
```

### 2. 配置默认参数（可选）
```python
CRAWLER_CONFIG = {
    "max_depth": 2,              # 最大递归深度
    "max_pages": 20,             # 最大爬取页面数
    "enable_recursive": True,    # 是否启用递归
    "output_dir": "output",      # 输出目录
}
```

## 三、使用方式

### 方式1: 使用命令行工具（推荐）

#### 交互式模式
```bash
python cli.py
```

进入交互式界面后：
```
# 从配置文件加载任务
crawler> load tasks_config.json

# 查看任务列表
crawler> list

# 执行所有任务
crawler> run

# 查看任务详情
crawler> show task_001

# 退出
crawler> exit
```

#### 命令行模式
```bash
# 加载任务
python cli.py load tasks_config.json

# 执行任务
python cli.py run

# 查看列表
python cli.py list
```

### 方式2: 使用工作流API

创建 `my_crawler.py`:
```python
import asyncio
from crawler_workflow import CrawlerWorkflow

async def main():
    # 创建工作流
    workflow = CrawlerWorkflow(
        llm_config_key="deepseek",
        max_concurrent=1  # 串行执行
    )

    # 方案1: 创建单个任务
    workflow.create_task_from_config(
        task_id="my_task",
        name="我的爬取任务",
        start_url="https://example.com",
        template_path="my_template.json",
        enable_recursive=True,
        max_depth=2,
        max_pages=10
    )

    # 执行任务
    await workflow.run_pending_tasks()

    # 查看结果
    workflow.print_summary()

if __name__ == "__main__":
    asyncio.run(main())
```

### 方式3: 直接使用爬虫引擎

创建 `simple_crawl.py`:
```python
import asyncio
from smart_crawler import SmartCrawler

async def main():
    # 创建爬虫
    crawler = SmartCrawler(
        template_path="my_template.json",
        llm_config_key="deepseek"
    )

    # 爬取（递归）
    await crawler.crawl_recursive(
        start_url="https://example.com",
        max_depth=2,
        max_pages=10
    )

    # 保存结果
    crawler.save_results()
    crawler.print_summary()

if __name__ == "__main__":
    asyncio.run(main())
```

## 四、创建模板

创建 `my_template.json`，定义要提取的字段:

```json
{
  "产品名称": "产品的完整名称",
  "价格": "产品价格，包含货币单位",
  "描述": "产品描述或简介",
  "规格": "产品规格参数"
}
```

**重要**:
- 键 = 字段名
- 值 = 字段说明（帮助LLM理解要提取什么）
- LLM会返回相同的键，但值是从网页提取的实际数据

## 五、批量任务配置

创建 `my_tasks.json`:

```json
{
  "tasks": [
    {
      "task_id": "task_001",
      "name": "爬取产品A",
      "start_url": "https://example.com/product-a",
      "template_path": "template_product.json",
      "config": {
        "enable_recursive": false
      }
    },
    {
      "task_id": "task_002",
      "name": "爬取产品B（递归）",
      "start_url": "https://example.com/catalog",
      "template_path": "template_product.json",
      "config": {
        "enable_recursive": true,
        "max_depth": 2,
        "max_pages": 20
      }
    }
  ]
}
```

然后加载执行:
```bash
python cli.py load my_tasks.json
python cli.py run
```

## 六、查看结果

### 1. 命令行查看
```bash
# 查看任务列表
python cli.py list

# 查看任务详情
python cli.py show task_001
```

### 2. 查看JSON文件
结果保存在 `output/products_*.json`:

```json
{
  "template": { ... },           // 使用的模板
  "crawl_info": {               // 爬取信息
    "pages_visited": 7,
    "products_found": 2,
    "crawled_at": "2025-11-21T14:25:26"
  },
  "products": [                 // 提取的产品
    {
      "产品名称": "实际提取的名称",
      "价格": "实际提取的价格",
      "_source_url": "来源URL",
      "_crawled_at": "爬取时间"
    }
  ]
}
```

## 七、常见场景

### 场景1: 爬取单个页面
```python
from smart_crawler import SmartCrawler

crawler = SmartCrawler(
    template_path="template.json",
    llm_config_key="deepseek"
)

# 禁用递归，只爬单页
await crawler.crawl_page("https://example.com/page", depth=0)
crawler.save_results()
```

### 场景2: 递归爬取整个网站
```python
from smart_crawler import SmartCrawler

crawler = SmartCrawler(
    template_path="template.json",
    llm_config_key="deepseek"
)

# 从首页开始递归爬取
await crawler.crawl_recursive(
    start_url="https://example.com",
    max_depth=3,      # 最多3层
    max_pages=50      # 最多50页
)
crawler.save_results()
```

### 场景3: 多个网站批量爬取
```json
// tasks_config.json
{
  "tasks": [
    {
      "task_id": "site_a",
      "name": "网站A",
      "start_url": "https://site-a.com",
      "template_path": "template_a.json",
      "config": {"enable_recursive": true}
    },
    {
      "task_id": "site_b",
      "name": "网站B",
      "start_url": "https://site-b.com",
      "template_path": "template_b.json",
      "config": {"enable_recursive": true}
    }
  ]
}
```

```bash
python cli.py load tasks_config.json
python cli.py run
```

### 场景4: 定期执行（配合cron）
```bash
# 每天凌晨2点执行
# crontab -e
0 2 * * * cd /path/to/crawler && python cli.py run >> logs/cron.log 2>&1
```

## 八、故障排查

### 问题1: API认证失败
**错误**: `Authentication Fails`
**解决**: 检查 `config.py` 中的 `api_token` 是否正确

### 问题2: 未提取到数据
**原因**: 模板字段与网页内容不匹配
**解决**:
1. 检查网页是否真的包含这些信息
2. 调整模板描述，更清楚地说明要提取什么
3. 查看日志中的 "LLM返回内容"

### 问题3: 递归爬取停止
**原因**: 达到了 `max_depth` 或 `max_pages` 限制
**解决**: 在配置中增加这些参数

### 问题4: 爬取速度慢
**原因**: LLM调用耗时
**解决**:
1. 使用更快的LLM模型
2. 减少 `max_pages` 限制
3. 禁用 `verbose` 日志

## 九、提示和技巧

1. **模板设计**: 字段描述越清楚，提取越准确
2. **URL选择**: 直接爬取目标页面比递归爬取更快
3. **并发控制**: 避免对目标网站造成压力
4. **结果验证**: 定期检查提取结果的准确性
5. **增量爬取**: 保存已访问URL，避免重复爬取

## 十、下一步

- 查看 `ARCHITECTURE.md` 了解系统架构
- 阅读 `smart_crawler.py` 源码了解实现细节
- 根据需求扩展功能（定时调度、Web API等）

---

**开始使用**:
```bash
# 1. 配置API key
vim config.py

# 2. 加载示例任务
python cli.py load tasks_config.json

# 3. 执行
python cli.py run

# 4. 查看结果
python cli.py list
python cli.py show task_001
```

祝爬取愉快！🎉
