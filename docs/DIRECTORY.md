# 项目目录结构说明

```
crawl4ai_data_crawl/                 # 项目根目录
│
├── src/                             # 📦 源代码目录
│   ├── __init__.py                  # Python包初始化
│   ├── smart_crawler.py             # 智能爬虫引擎（主要使用）
│   ├── product_crawler.py           # 产品爬虫（备用实现）
│   ├── crawler_workflow.py          # 工作流系统核心
│   └── cli.py                       # 命令行工具
│
├── configs/                         # ⚙️  配置文件目录
│   ├── config.py                    # 系统配置（LLM API、爬虫参数）
│   ├── config.example.py            # 配置示例文件
│   └── tasks_config.json            # 批量任务配置示例
│
├── templates/                       # 📋 数据提取模板目录
│   └── template_deepseek_pricing.json  # DeepSeek定价模板示例
│
├── docs/                            # 📚 文档目录
│   ├── ARCHITECTURE.md              # 系统架构详细说明
│   └── QUICKSTART.md                # 快速开始指南
│
├── data/                            # 💾 数据存储目录
│   └── tasks.json                   # 任务队列持久化存储（自动生成）
│
├── output/                          # 📊 爬取结果输出目录
│   └── products_*.json              # 爬取结果文件（按时间戳命名）
│
├── logs/                            # 📝 日志文件目录
│   └── *.log                        # 各种日志文件
│
├── run.py                           # 🚀 主入口文件
├── README.md                        # 📖 项目说明文档
├── requirements.txt                 # 📦 依赖列表
└── .gitignore                       # 🚫 Git忽略文件配置

```

## 目录功能说明

### 📦 src/ - 源代码
所有核心代码都在这里：
- `smart_crawler.py`: 智能爬虫引擎，支持单页和递归爬取
- `crawler_workflow.py`: 工作流系统，包含任务管理、调度、队列
- `cli.py`: 命令行交互工具
- `product_crawler.py`: 备用爬虫实现

### ⚙️ configs/ - 配置文件
所有配置集中管理：
- `config.py`: 实际配置（**不要提交到Git**）
- `config.example.py`: 配置模板，供参考
- `tasks_config.json`: 批量任务定义

**首次使用**:
```bash
cp configs/config.example.py configs/config.py
# 然后编辑 config.py 填写你的 API Key
```

### 📋 templates/ - 提取模板
定义要从网页提取的数据字段：
- 键 = 字段名
- 值 = 字段说明（帮助LLM理解）

**示例**:
```json
{
  "字段名": "字段说明，告诉LLM要提取什么"
}
```

### 📚 docs/ - 文档
- `QUICKSTART.md`: 5分钟快速上手
- `ARCHITECTURE.md`: 深入理解系统架构

### 💾 data/ - 数据存储
- `tasks.json`: 任务队列的持久化存储
- 自动创建，无需手动编辑

### 📊 output/ - 爬取结果
所有爬取结果按时间戳保存：
- `products_20251121_142526.json`
- 包含模板、爬取信息、提取的产品数据

### 📝 logs/ - 日志
各种运行日志，用于调试和监控

### 🚀 run.py - 主入口
统一的启动入口：
```bash
python run.py              # 交互式CLI
python run.py list         # 查看任务列表
python run.py run          # 执行任务
```

## 文件命名规范

### 配置文件
- `config.py` - 实际配置
- `*.example.py` - 示例配置
- `*_config.json` - JSON格式配置

### 模板文件
- `template_*.json` - 数据提取模板
- 按用途命名，如 `template_deepseek_pricing.json`

### 结果文件
- `products_YYYYMMdd_HHmmss.json` - 自动按时间戳命名
- 格式：`products_年月日_时分秒.json`

### 日志文件
- `*.log` - 日志文件
- 按模块命名，如 `crawler.log`, `workflow.log`

## 路径说明

### 相对路径使用
代码中所有路径都相对于**项目根目录**：
```python
# ✅ 正确
template_path = "templates/my_template.json"
output_dir = "output"

# ❌ 错误（不要使用绝对路径）
template_path = "/home/user/project/templates/my_template.json"
```

### 自动路径处理
系统会自动处理路径：
- 配置文件路径: `configs/config.py`
- 模板路径: `templates/*.json`
- 输出路径: `output/`
- 数据路径: `data/tasks.json`

## 最佳实践

1. **配置管理**
   - 使用 `config.example.py` 作为模板
   - 实际的 `config.py` 不要提交到 Git
   - API Key 等敏感信息放在 `config.py`

2. **模板组织**
   - 按网站或数据类型创建模板
   - 使用清晰的命名: `template_网站_数据类型.json`
   - 复用相同结构的模板

3. **结果管理**
   - 定期清理 `output/` 目录
   - 重要结果及时备份
   - 可以按项目创建子目录

4. **任务配置**
   - 批量任务使用 `tasks_config.json`
   - 单次任务直接用 CLI 或代码
   - 复杂任务拆分成多个小任务

5. **日志查看**
   - 出错时查看 `logs/` 目录
   - 定期清理旧日志
   - 可配置日志级别

## 扩展目录

如需扩展功能，建议新增以下目录：

```
├── tests/              # 单元测试
├── scripts/            # 辅助脚本
├── plugins/            # 插件扩展
└── migrations/         # 数据迁移脚本
```

## Git 管理

### 提交到 Git
```
src/
docs/
templates/
configs/config.example.py
configs/tasks_config.json
README.md
requirements.txt
run.py
.gitignore
```

### 不提交（.gitignore）
```
configs/config.py       # 包含敏感信息
data/                   # 任务数据
output/                 # 爬取结果
logs/                   # 日志文件
__pycache__/           # Python缓存
```

## 快速导航

- 想修改配置？→ `configs/config.py`
- 想创建模板？→ `templates/`
- 想看结果？→ `output/`
- 想了解架构？→ `docs/ARCHITECTURE.md`
- 想快速上手？→ `docs/QUICKSTART.md`
- 想看日志？→ `logs/`
- 想运行爬虫？→ `python run.py`
