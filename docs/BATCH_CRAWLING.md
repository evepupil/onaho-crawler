# 批次爬取和断点续爬功能

## 功能概述

两阶段爬取器（`two_stage_crawler.py`）现已支持批次爬取和断点续爬功能，特别适合大型网站的分批处理。

## 核心特性

### 1. 任务输出目录管理
- 每个任务有独立的输出目录：`output/任务名称/`
- 便于管理多个爬取任务

### 2. 链接状态跟踪
链接列表现在包含爬取状态信息：

```json
{
  "url": "https://example.com/product/1",
  "crawled": false,          // 是否已爬取
  "discovered_at": "2025-11-24T...",
  "depth": 2,
  "crawled_at": "2025-11-24T..."  // 爬取完成时间（如果已爬取）
}
```

### 3. 阶段1完成标记
- 阶段1完成后会创建 `.stage1_completed` 标志文件
- 再次运行时自动检测并跳过阶段1
- 如需重新爬取，删除该文件或使用 `force=True` 参数

### 4. 批次处理
- 使用 `batch_size` 参数控制每次爬取的链接数量
- 支持分批次逐步完成大网站的爬取

### 5. 进度自动保存
- 每爬取N个链接自动保存一次（默认5个）
- 即使中断也不会丢失已爬取的数据
- 再次运行时自动跳过已爬取的链接

### 6. 产品数据累积
- 产品数据文件会累积保存
- 再次运行时加载已有数据并追加新数据

## 使用方式

### 完整运行（一键执行）

```python
from src.two_stage_crawler import TwoStageCrawler
import asyncio

async def main():
    crawler = TwoStageCrawler(
        task_name="my_task",  # 任务名称，用于创建输出目录
        start_url="https://example.com",
        template_path="templates/my_template.json",
        llm_config_key="deepseek"
    )

    # 一键运行（自动检测断点）
    await crawler.run(
        url_patterns=["/product/", "/item/"],  # URL过滤模式
        stage1_max_depth=3,       # 阶段1最大深度
        stage1_max_pages=100,     # 阶段1最大页面数
        stage2_batch_size=10,     # 阶段2批次大小（每次爬10个）
        force_stage1=False        # 是否强制重新执行阶段1
    )

asyncio.run(main())
```

### 分步运行（更灵活的控制）

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
    max_pages=100,
    force=False  # 如果已完成则跳过
)

# 阶段2: 分批爬取
# 第一次：爬取前10个
await crawler.stage2_extract_products(
    url_patterns=["/product/"],
    batch_size=10,
    save_interval=5
)

# 第二次：再爬取10个（自动跳过已爬取的）
await crawler.stage2_extract_products(
    url_patterns=["/product/"],
    batch_size=10
)

# 继续运行直到全部完成...
```

## 文件结构

```
output/
└── 任务名称/
    ├── .stage1_completed       # 阶段1完成标志（空文件）
    ├── collected_links.json    # 收集的所有链接（带状态）
    └── products.json           # 提取的产品数据（累积保存）
```

### collected_links.json 格式

```json
{
  "task_name": "my_task",
  "start_url": "https://example.com",
  "collected_at": "2025-11-24T16:59:29",
  "total_links": 62,
  "crawled_count": 10,  // 已爬取数量
  "links": [
    {
      "url": "https://example.com/product/1",
      "crawled": true,
      "discovered_at": "2025-11-24T16:59:30",
      "depth": 2,
      "crawled_at": "2025-11-24T17:00:17"
    },
    {
      "url": "https://example.com/product/2",
      "crawled": false,  // 未爬取
      "discovered_at": "2025-11-24T16:59:30",
      "depth": 2
    }
  ]
}
```

## 实际应用场景

### 场景1: 大型网站分批爬取

```python
# 假设网站有500个产品页，分5批完成

crawler = TwoStageCrawler(
    task_name="large_site",
    start_url="https://example.com",
    template_path="templates/product.json",
    llm_config_key="deepseek"
)

# 第1天：阶段1收集链接
await crawler.stage1_collect_links(max_depth=5, max_pages=1000)

# 第2天：爬取前100个
await crawler.stage2_extract_products(
    url_patterns=["/product/"],
    batch_size=100
)

# 第3天：再爬100个（自动跳过已爬取的）
await crawler.stage2_extract_products(
    url_patterns=["/product/"],
    batch_size=100
)

# ... 继续分批爬取
```

### 场景2: 意外中断恢复

```python
# 假设爬取过程中断了（网络问题、程序崩溃等）

crawler = TwoStageCrawler(
    task_name="interrupted_task",
    start_url="https://example.com",
    template_path="templates/product.json",
    llm_config_key="deepseek"
)

# 直接运行 - 自动从断点恢复
await crawler.run(
    url_patterns=["/product/"],
    stage1_max_depth=3,
    stage1_max_pages=100
)

# 输出日志会显示：
# - 阶段1已完成，跳过
# - 从文件加载了 62 个链接
# - 其中已爬取: 15 个，未爬取: 47 个
# - 待爬取（本次）: 47
```

### 场景3: 测试和调试

```python
# 先小批量测试，确认模板和过滤规则正确

crawler = TwoStageCrawler(
    task_name="test_task",
    start_url="https://example.com",
    template_path="templates/product.json",
    llm_config_key="deepseek"
)

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

## 统计信息

运行完成后会显示摘要：

```
============================================================
爬取摘要
============================================================
任务名称: my_task
起始URL: https://example.com
输出目录: output/my_task

链接统计:
  收集总数: 62
  已爬取: 10
  未爬取: 52

产品统计:
  提取产品数: 2

最近提取的产品:
【产品 1】
...

文件位置:
  链接文件: output/my_task/collected_links.json
  产品文件: output/my_task/products.json
============================================================
```

## 重置和重新开始

如果需要完全重新爬取：

```bash
# 删除整个任务目录
rm -rf output/任务名称/

# 或只删除阶段1标志文件（保留已收集的链接）
rm output/任务名称/.stage1_completed

# 或在代码中使用 force=True
await crawler.stage1_collect_links(force=True)
```

## 优势总结

✅ **容错性强**: 意外中断后可以继续
✅ **灵活控制**: 可以控制每次爬取的数量
✅ **节省成本**: 避免重复调用LLM
✅ **进度可见**: 清晰显示已爬取和未爬取的数量
✅ **易于管理**: 每个任务独立目录，互不干扰
✅ **调试友好**: 可以小批量测试后再大规模爬取
