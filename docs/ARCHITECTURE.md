# 爬虫工作流系统架构

## 系统概述

这是一个基于 `crawl4ai` 和 LLM 的智能爬虫工作流系统，支持任务管理、调度、并发执行、结果存储等完整功能。

## 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                     爬虫工作流系统                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐      ┌──────────────┐                    │
│  │  CLI工具      │      │  工作流API   │                    │
│  │  cli.py      │      │ (未来扩展)   │                    │
│  └──────┬───────┘      └──────┬───────┘                    │
│         │                     │                             │
│         └─────────┬───────────┘                             │
│                   │                                         │
│         ┌─────────▼──────────┐                              │
│         │  CrawlerWorkflow   │  工作流核心                   │
│         │  crawler_workflow  │  - 任务调度                   │
│         │                    │  - 并发控制                   │
│         └─────────┬──────────┘  - 状态管理                   │
│                   │                                         │
│         ┌─────────▼──────────┐                              │
│         │    TaskQueue       │  任务队列                     │
│         │                    │  - 任务存储                   │
│         └─────────┬──────────┘  - 持久化                     │
│                   │                                         │
│         ┌─────────▼──────────┐                              │
│         │   CrawlerTask      │  任务对象                     │
│         │                    │  - 任务配置                   │
│         └─────────┬──────────┘  - 状态跟踪                   │
│                   │                                         │
│         ┌─────────▼──────────┐                              │
│         │  SmartCrawler      │  爬虫引擎                     │
│         │  smart_crawler.py  │  - 递归爬取                   │
│         └─────────┬──────────┘  - LLM提取                    │
│                   │                                         │
│         ┌─────────▼──────────┐                              │
│         │     crawl4ai       │  底层框架                     │
│         │   + LLM (DeepSeek) │  - 浏览器自动化               │
│         └────────────────────┘  - 内容提取                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘

        ┌───────────────┐          ┌───────────────┐
        │  配置文件      │          │  数据存储      │
        ├───────────────┤          ├───────────────┤
        │ config.py     │          │ tasks.json    │
        │ tasks_config  │          │ output/       │
        │ templates/    │          │               │
        └───────────────┘          └───────────────┘
```

## 核心组件

### 1. SmartCrawler（爬虫引擎）
**文件**: `smart_crawler.py`

**功能**:
- 单页爬取
- 递归爬取（自动发现子链接）
- LLM智能提取（根据模板提取结构化数据）
- 结果保存

**关键方法**:
- `crawl_page()`: 爬取单个页面
- `crawl_recursive()`: 递归爬取
- `save_results()`: 保存结果

**配置来源**: `config.py`

---

### 2. CrawlerTask（任务对象）
**文件**: `crawler_workflow.py`

**属性**:
- `task_id`: 任务唯一标识
- `name`: 任务名称
- `start_url`: 起始URL
- `template_path`: 模板文件路径
- `config`: 任务配置
- `status`: 任务状态（pending/running/completed/failed）
- `result_file`: 结果文件路径
- `pages_visited`: 访问页面数
- `products_found`: 提取产品数

**方法**:
- `to_dict()`: 序列化为字典
- `from_dict()`: 从字典反序列化

---

### 3. TaskQueue（任务队列）
**文件**: `crawler_workflow.py`

**功能**:
- 任务存储和管理
- 持久化到JSON文件
- 任务状态查询

**关键方法**:
- `add_task()`: 添加任务
- `get_task()`: 获取任务
- `get_pending_tasks()`: 获取待执行任务
- `save()` / `load()`: 持久化

**存储文件**: `tasks.json`

---

### 4. CrawlerWorkflow（工作流系统）
**文件**: `crawler_workflow.py`

**功能**:
- 任务调度和执行
- 并发控制
- 状态管理
- 结果汇总

**关键方法**:
- `execute_task()`: 执行单个任务
- `run_pending_tasks()`: 执行所有待执行任务
- `create_task_from_config()`: 从配置创建任务
- `print_summary()`: 打印摘要

**配置**:
- `llm_config_key`: 使用的LLM配置
- `max_concurrent`: 最大并发任务数

---

### 5. CLI工具
**文件**: `cli.py`

**功能**:
- 交互式命令行界面
- 任务管理（增删查改）
- 批量加载任务
- 执行任务

**可用命令**:
```bash
add <task_id> <name> <url> [template]  # 添加任务
load <config.json>                     # 从文件加载任务
list                                   # 列出所有任务
show <task_id>                         # 显示任务详情
run [task_id]                          # 执行任务
delete <task_id>                       # 删除任务
clear                                  # 清空所有任务
help                                   # 显示帮助
exit                                   # 退出
```

---

## 配置文件

### config.py（系统配置）
```python
LLM_CONFIG = {
    "deepseek": {
        "provider": "deepseek/deepseek-chat",
        "api_token": "your-api-key",
        "base_url": "https://api.deepseek.com"
    }
}

CRAWLER_CONFIG = {
    "max_depth": 2,              # 最大递归深度
    "max_pages": 20,             # 最大爬取页面数
    "output_dir": "output",      # 输出目录
    "enable_recursive": True,    # 启用递归爬取
    "template_path": "template_deepseek_pricing.json",
    "start_url": "https://example.com"
}
```

### tasks_config.json（任务配置）
批量定义多个爬取任务:
```json
{
  "tasks": [
    {
      "task_id": "task_001",
      "name": "任务名称",
      "start_url": "https://example.com",
      "template_path": "template.json",
      "config": {
        "enable_recursive": true,
        "max_depth": 2,
        "max_pages": 10
      }
    }
  ]
}
```

### 模板文件（template_*.json）
定义要提取的数据字段:
```json
{
  "字段名1": "字段说明1",
  "字段名2": "字段说明2",
  "字段名3": "字段说明3"
}
```

---

## 数据流

```
1. 用户定义任务
   ↓
2. 添加到任务队列（TaskQueue）
   ↓
3. 持久化到 tasks.json
   ↓
4. 工作流调度执行（CrawlerWorkflow）
   ↓
5. 创建爬虫实例（SmartCrawler）
   ↓
6. 爬取网页（crawl4ai）
   ↓
7. LLM提取数据（根据模板）
   ↓
8. 保存结果到 output/
   ↓
9. 更新任务状态
   ↓
10. 持久化到 tasks.json
```

---

## 使用场景

### 场景1: 单个任务执行
```python
from crawler_workflow import CrawlerWorkflow

workflow = CrawlerWorkflow()

# 创建任务
task = workflow.create_task_from_config(
    task_id="task_001",
    name="DeepSeek定价",
    start_url="https://api-docs.deepseek.com/zh-cn/",
    template_path="template_deepseek_pricing.json",
    enable_recursive=True
)

# 执行任务
await workflow.execute_task(task)
```

### 场景2: 批量任务管理
```python
from crawler_workflow import CrawlerWorkflow
import json

workflow = CrawlerWorkflow()

# 从文件加载任务
with open("tasks_config.json") as f:
    data = json.load(f)
    for task_data in data["tasks"]:
        task = CrawlerTask.from_dict(task_data)
        workflow.task_queue.add_task(task)

# 执行所有任务
await workflow.run_pending_tasks()

# 查看结果
workflow.print_summary()
```

### 场景3: CLI交互式使用
```bash
# 启动交互式界面
python cli.py

# 或者命令行模式
python cli.py load tasks_config.json
python cli.py run
python cli.py list
```

---

## 扩展方向

### 1. 定时调度
集成 `APScheduler` 或 `Celery`，实现定时爬取:
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()
scheduler.add_job(
    workflow.run_pending_tasks,
    'cron',
    hour=2,  # 每天凌晨2点执行
    id='daily_crawl'
)
```

### 2. Web API
添加 FastAPI 接口:
```python
from fastapi import FastAPI

app = FastAPI()

@app.post("/tasks")
async def create_task(task: TaskCreate):
    ...

@app.get("/tasks/{task_id}")
async def get_task(task_id: str):
    ...

@app.post("/tasks/{task_id}/run")
async def run_task(task_id: str):
    ...
```

### 3. 数据库存储
替换JSON文件，使用SQLite/PostgreSQL:
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 任务持久化到数据库
# 支持更复杂的查询和统计
```

### 4. 结果后处理
添加结果处理管道:
```python
class ResultProcessor:
    def process(self, result):
        # 数据清洗
        # 格式转换
        # 入库
        # 通知
        pass
```

### 5. 监控和告警
添加监控指标:
```python
# 任务执行时间
# 成功率
# 错误日志
# 告警通知（邮件/钉钉/企业微信）
```

### 6. 分布式执行
使用 Celery 实现分布式任务队列:
```python
from celery import Celery

app = Celery('crawler')

@app.task
def execute_crawler_task(task_id):
    ...
```

---

## 目录结构

```
crawl4ai_data_crawl/
├── config.py                    # 系统配置
├── smart_crawler.py             # 爬虫引擎
├── product_crawler.py           # 爬虫引擎（备用）
├── crawler_workflow.py          # 工作流系统
├── cli.py                       # 命令行工具
├── tasks_config.json            # 任务配置文件
├── tasks.json                   # 任务队列存储（自动生成）
├── template_deepseek_pricing.json   # 模板示例
├── output/                      # 结果输出目录
│   ├── products_*.json
│   └── deepseek/
└── logs/                        # 日志目录（可选）
    └── crawler.log
```

---

## 最佳实践

1. **任务粒度**: 每个任务针对一个网站的一类数据
2. **模板复用**: 相同结构的数据使用相同模板
3. **并发控制**: 根据目标网站限流要求设置 `max_concurrent`
4. **错误处理**: 定期查看失败任务，分析原因
5. **结果备份**: 定期备份 `output/` 和 `tasks.json`
6. **配置版本**: 使用 git 管理配置文件
7. **监控日志**: 关注爬取效率和成功率

---

## 性能优化

1. **缓存策略**: 使用 `CacheMode.ENABLED` 缓存已访问页面
2. **并发调优**: 根据机器性能调整 `max_concurrent`
3. **深度限制**: 合理设置 `max_depth` 避免过度爬取
4. **选择性爬取**: 通过URL过滤只爬取目标页面
5. **LLM调优**: 使用更快的模型或批量处理

---

## 总结

这是一个完整的、生产级的爬虫工作流系统，具有以下特点:

✅ **模块化**: 清晰的分层架构
✅ **可扩展**: 易于添加新功能
✅ **持久化**: 任务和结果自动保存
✅ **易用性**: CLI工具和配置文件
✅ **智能化**: LLM驱动的数据提取
✅ **灵活性**: 支持单页和递归爬取

可以直接用于生产环境，也可以作为基础继续扩展。
