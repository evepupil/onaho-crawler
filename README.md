# 智能爬虫工作流系统

基于 crawl4ai 和 LLM 的智能爬虫工作流系统，支持任务管理、调度、并发执行、结果存储等完整功能。

## 目录结构

```
crawl4ai_data_crawl/
├── src/                         # 源代码
│   ├── smart_crawler.py         # 智能爬虫引擎 ⭐
│   ├── crawler_workflow.py      # 工作流系统核心 ⭐
│   ├── cli.py                   # 命令行工具 ⭐
│   └── product_crawler.py       # 产品爬虫（备用）
│
├── configs/                     # 配置文件
│   ├── config.py                # 系统配置（LLM、爬虫参数）⚙️
│   ├── config.example.py        # 配置示例
│   └── tasks_config.json        # 任务配置示例
│
├── templates/                   # 数据提取模板 📋
│   └── template_*.json
│
├── docs/                        # 文档 📚
│   ├── QUICKSTART.md            # 快速开始
│   ├── ARCHITECTURE.md          # 系统架构
│   └── DIRECTORY.md             # 目录结构说明
│
├── data/                        # 数据存储 💾
│   └── tasks.json               # 任务队列（自动生成）
│
├── output/                      # 爬取结果 📊
│   └── products_*.json
│
├── logs/                        # 日志文件 📝
│
├── run.py                       # 主入口 🚀
├── requirements.txt
└── README.md
```

详细说明见 [docs/DIRECTORY.md](docs/DIRECTORY.md)

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
        ...
    }
}
```

### 3. 运行爬虫

#### 方式1: 交互式命令行（推荐）
```bash
python run.py
```

进入交互界面后：
```
crawler> load configs/tasks_config.json   # 加载任务
crawler> list                             # 查看任务列表
crawler> run                              # 执行所有任务
crawler> show task_001                    # 查看任务详情
crawler> exit                             # 退出
```

#### 方式2: 直接命令
```bash
# 加载并执行任务
python run.py load configs/tasks_config.json
python run.py run

# 查看任务列表
python run.py list
```

#### 方式3: 编程方式
```python
import asyncio
from src.crawler_workflow import CrawlerWorkflow

async def main():
    workflow = CrawlerWorkflow()

    # 创建任务
    workflow.create_task_from_config(
        task_id="my_task",
        name="我的爬取任务",
        start_url="https://example.com",
        template_path="templates/my_template.json",
        enable_recursive=True,
        max_depth=2
    )

    # 执行
    await workflow.run_pending_tasks()
    workflow.print_summary()

asyncio.run(main())
```

## 核心功能

✅ **智能爬取**
- 单页爬取
- 递归爬取（自动发现子页面）
- LLM 驱动的数据提取
- 基于模板的结构化输出

✅ **任务管理**
- 创建、删除、查询任务
- 持久化存储
- 状态追踪

✅ **工作流调度**
- 串行/并发执行
- 任务队列管理
- 结果自动保存

✅ **易用性**
- 交互式 CLI
- 批量任务配置
- 配置文件管理

## 使用示例

### 创建模板
创建 `templates/my_template.json`:
```json
{
  "产品名称": "产品的完整名称",
  "价格": "产品价格，包含货币单位",
  "描述": "产品描述或简介"
}
```

### 创建任务配置
创建 `configs/my_tasks.json`:
```json
{
  "tasks": [
    {
      "task_id": "task_001",
      "name": "爬取产品信息",
      "start_url": "https://example.com",
      "template_path": "templates/my_template.json",
      "config": {
        "enable_recursive": true,
        "max_depth": 2,
        "max_pages": 10
      }
    }
  ]
}
```

### 执行爬取
```bash
python run.py
crawler> load configs/my_tasks.json
crawler> run
crawler> list
```

### 查看结果
结果保存在 `output/products_*.json`:
```json
{
  "template": { ... },
  "crawl_info": {
    "pages_visited": 7,
    "products_found": 2,
    "crawled_at": "2025-11-21T14:25:26"
  },
  "products": [
    {
      "产品名称": "实际提取的名称",
      "价格": "实际提取的价格",
      "_source_url": "https://example.com/page",
      "_crawled_at": "2025-11-21T14:25:26"
    }
  ]
}
```

## CLI 命令

```
add <task_id> <name> <url> [template]  - 添加任务
load <config.json>                     - 从文件加载任务
list                                   - 列出所有任务
show <task_id>                         - 显示任务详情
run [task_id]                          - 执行任务（不指定则执行所有）
delete <task_id>                       - 删除任务
clear                                  - 清空所有任务
help                                   - 显示帮助
exit                                   - 退出
```

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

### 爬虫配置 (`configs/config.py`)
```python
CRAWLER_CONFIG = {
    "max_depth": 2,              # 最大递归深度
    "max_pages": 20,             # 最大爬取页面数
    "output_dir": "output",      # 输出目录
    "enable_recursive": True,    # 启用递归爬取
    "template_path": "templates/template_deepseek_pricing.json",
    "start_url": "https://example.com"
}
```

## 文档

- **快速开始**: `docs/QUICKSTART.md`
- **系统架构**: `docs/ARCHITECTURE.md`

## 扩展方向

- 定时调度（APScheduler）
- Web API（FastAPI）
- 数据库存储（SQLite/PostgreSQL）
- 监控告警
- 分布式执行（Celery）

## License

MIT
