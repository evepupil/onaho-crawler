# 智能爬虫 - 两阶段爬取系统

基于 crawl4ai 和 LLM 的智能爬虫，采用两阶段爬取策略，节省token成本，支持批次爬取和断点续爬。

## 核心特性

✅ **两阶段爬取策略**（省80%+ token）
- 阶段1: 快速递归爬取所有链接（不使用LLM，不花钱）
- 阶段2: 根据URL模式过滤产品页，详细爬取并LLM分析

✅ **批次爬取和断点续爬**
- 链接状态跟踪（已爬取/未爬取）
- 支持中断后继续
- 批次处理大型网站
- 进度自动保存

✅ **智能数据提取**
- 基于模板的结构化输出
- LLM 驱动的数据提取
- 自动去重和验证

## 目录结构

```
crawl4ai_data_crawl/
├── src/
│   └── two_stage_crawler.py    # 两阶段爬虫核心 ⭐
│
├── configs/
│   ├── config.py                # 系统配置（LLM、爬虫参数）⚙️
│   └── two_stage_tasks.json     # 任务配置示例
│
├── templates/                   # 数据提取模板 📋
│   └── template_*.json
│
├── docs/                        # 文档 📚
│   ├── BATCH_CRAWLING.md        # 批次爬取和断点续爬详细说明
│   ├── STRATEGY_COMPARISON.md   # 策略对比
│   └── DIRECTORY.md             # 目录结构说明
│
├── output/                      # 爬取结果（按任务名称组织）📊
│   └── task_name/
│       ├── .stage1_completed    # 阶段1完成标志
│       ├── collected_links.json # 收集的所有链接（带状态）
│       └── products.json        # 提取的产品数据
│
└── requirements.txt
```

## 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置 API Key
编辑 `configs/config.py`，设置你的 LLM API Key:
```python
LLM_CONFIG = {
    "deepseek": {
        "provider": "deepseek/deepseek-chat",
        "api_token": "your-api-key-here",  # 修改这里
        "base_url": "https://api.deepseek.com"
    }
}
```

### 3. 创建数据提取模板
创建 `templates/my_template.json`:
```json
{
  "产品名称": "产品的完整名称",
  "价格": "产品价格，包含货币单位",
  "描述": "产品描述或简介"
}
```

### 4. 运行爬虫

#### 方式1: 一键运行（推荐）

```python
from src.two_stage_crawler import TwoStageCrawler
import asyncio

async def main():
    crawler = TwoStageCrawler(
        task_name="my_task",              # 任务名称（输出目录名）
        start_url="https://example.com",  # 起始URL
        template_path="templates/my_template.json",
        llm_config_key="deepseek"
    )

    # 一键运行（自动检测断点续爬）
    await crawler.run(
        url_patterns=["/product/", "/item/"],  # URL过滤模式
        stage1_max_depth=3,        # 阶段1最大深度
        stage1_max_pages=100,      # 阶段1最大页面数
        stage2_batch_size=10       # 阶段2批次大小（每次爬10个）
    )

asyncio.run(main())
```

#### 方式2: 分步运行（更灵活）

```python
crawler = TwoStageCrawler(
    task_name="my_task",
    start_url="https://example.com",
    template_path="templates/my_template.json",
    llm_config_key="deepseek"
)

# 阶段1: 收集链接（只需运行一次）
await crawler.stage1_collect_links(
    max_depth=3,
    max_pages=100
)

# 阶段2: 分批爬取（可以多次运行，自动跳过已爬取的）
await crawler.stage2_extract_products(
    url_patterns=["/product/"],
    batch_size=10,       # 每次爬10个
    save_interval=5      # 每5个保存一次
)

# 查看摘要
crawler.print_summary()

# 保存结果
crawler.save_products()
```

### 5. 查看结果

结果保存在 `output/任务名称/` 目录：

**collected_links.json** - 收集的所有链接
```json
{
  "task_name": "my_task",
  "total_links": 62,
  "crawled_count": 10,
  "links": [
    {
      "url": "https://example.com/product/1",
      "crawled": true,
      "discovered_at": "2025-11-24T16:59:30",
      "crawled_at": "2025-11-24T17:00:17"
    }
  ]
}
```

**products.json** - 提取的产品数据
```json
{
  "task_name": "my_task",
  "template": { ... },
  "crawl_info": {
    "products_extracted": 2,
    "last_updated": "2025-11-24T17:00:56"
  },
  "products": [
    {
      "产品名称": "实际提取的名称",
      "价格": "实际提取的价格",
      "_source_url": "https://example.com/product/1",
      "_crawled_at": "2025-11-24T17:00:17"
    }
  ]
}
```

## 使用场景

### 场景1: 大型网站分批爬取

```python
# 假设网站有500个产品页，分5批完成

crawler = TwoStageCrawler(
    task_name="large_site",
    start_url="https://example.com",
    template_path="templates/product.json",
    llm_config_key="deepseek"
)

# 第1天：收集所有链接
await crawler.stage1_collect_links(max_depth=5, max_pages=1000)

# 第2天：爬取前100个
await crawler.stage2_extract_products(
    url_patterns=["/product/"],
    batch_size=100
)

# 第3-6天：每天100个，自动跳过已爬取的
# 多次运行，直到全部完成
```

### 场景2: 意外中断恢复

```python
# 程序中断后，直接运行 - 自动从断点恢复
await crawler.run(
    url_patterns=["/product/"],
    stage1_max_depth=3,
    stage1_max_pages=100
)

# 输出会显示：
# - 阶段1已完成，跳过
# - 从文件加载了 62 个链接
# - 其中已爬取: 15 个，未爬取: 47 个
# - 继续爬取剩余的47个
```

### 场景3: 测试和调试

```python
# 先小批量测试，确认模板和过滤规则正确

# 阶段1收集链接
await crawler.stage1_collect_links(max_depth=2, max_pages=50)

# 先爬2个测试
await crawler.stage2_extract_products(
    url_patterns=["/product/"],
    batch_size=2
)

# 检查结果，确认无误后继续
await crawler.stage2_extract_products(
    url_patterns=["/product/"],
    batch_size=100  # 正式批量爬取
)
```

## 为什么选择两阶段爬取？

| 对比项 | 传统边爬边分析 | 两阶段爬取 ⭐ |
|-------|--------------|-------------|
| LLM调用次数 | 每个页面1次 | 只对产品页1次 |
| Token消耗 | 高（100%） | 低（约20%） |
| 覆盖范围 | 有限 | 全面 |
| 灵活性 | 低 | 高 |
| 断点续爬 | 不支持 | 支持 |
| 批次处理 | 不支持 | 支持 |

**详细对比见**: [docs/STRATEGY_COMPARISON.md](docs/STRATEGY_COMPARISON.md)

## 配置说明

### LLM 配置 (`configs/config.py`)
```python
LLM_CONFIG = {
    "deepseek": {
        "provider": "deepseek/deepseek-chat",
        "api_token": "your-api-key",
        "base_url": "https://api.deepseek.com"
    }
}
```

### 任务配置 (`configs/two_stage_tasks.json`)
```json
{
  "tasks": [
    {
      "task_id": "my_task_001",
      "task_name": "my_task",
      "start_url": "https://example.com",
      "template_path": "templates/my_template.json",
      "stage1": {
        "max_depth": 3,
        "max_pages": 100
      },
      "stage2": {
        "url_patterns": ["/product/", "/item/"],
        "batch_size": 10
      }
    }
  ]
}
```

## 重置和重新开始

```bash
# 删除整个任务目录（完全重新开始）
rm -rf output/任务名称/

# 只删除阶段1标志（重新收集链接，保留已爬取状态）
rm output/任务名称/.stage1_completed

# 或在代码中使用 force=True
await crawler.stage1_collect_links(force=True)
```

## 文档

- **批次爬取详细说明**: [docs/BATCH_CRAWLING.md](docs/BATCH_CRAWLING.md)
- **策略对比**: [docs/STRATEGY_COMPARISON.md](docs/STRATEGY_COMPARISON.md)
- **目录结构**: [docs/DIRECTORY.md](docs/DIRECTORY.md)

## 优势总结

✅ **成本低**: 只对产品页调用LLM，节省80%+ token
✅ **覆盖全**: 可以爬取更多页面，发现更多产品
✅ **容错强**: 意外中断后可以继续
✅ **灵活性**: 可以控制每次爬取的数量
✅ **易调试**: 可以小批量测试后再大规模爬取
✅ **无重复**: 自动去重，不会重复爬取

## License

MIT
