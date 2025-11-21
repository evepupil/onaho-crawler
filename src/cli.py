#!/usr/bin/env python3
"""
爬虫工作流命令行工具
提供任务管理、执行、查询等命令
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.crawler_workflow import CrawlerWorkflow, CrawlerTask


def load_tasks_from_file(file_path: str, workflow: CrawlerWorkflow):
    """从配置文件加载任务"""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    tasks = data.get("tasks", [])
    for task_data in tasks:
        task = CrawlerTask(
            task_id=task_data["task_id"],
            name=task_data["name"],
            start_url=task_data["start_url"],
            template_path=task_data["template_path"],
            config=task_data.get("config")
        )
        workflow.task_queue.add_task(task)

    print(f"✅ 从 {file_path} 加载了 {len(tasks)} 个任务")


def cmd_add_task(workflow: CrawlerWorkflow, args):
    """添加单个任务"""
    if len(args) < 3:
        print("用法: add <task_id> <name> <start_url> [template_path]")
        return

    task_id = args[0]
    name = args[1]
    start_url = args[2]
    template_path = args[3] if len(args) > 3 else "template_deepseek_pricing.json"

    task = workflow.create_task_from_config(
        task_id=task_id,
        name=name,
        start_url=start_url,
        template_path=template_path
    )

    print(f"✅ 已添加任务: {task.task_id} - {task.name}")


def cmd_load_tasks(workflow: CrawlerWorkflow, args):
    """从文件加载任务"""
    if len(args) < 1:
        print("用法: load <tasks_config.json>")
        return

    file_path = args[0]
    if not Path(file_path).exists():
        print(f"❌ 文件不存在: {file_path}")
        return

    load_tasks_from_file(file_path, workflow)


async def cmd_run(workflow: CrawlerWorkflow, args):
    """执行任务"""
    if len(args) == 0:
        # 执行所有待执行任务
        print("执行所有待执行任务...")
        await workflow.run_pending_tasks()
    else:
        # 执行指定任务
        task_id = args[0]
        task = workflow.task_queue.get_task(task_id)
        if not task:
            print(f"❌ 任务不存在: {task_id}")
            return

        print(f"执行任务: {task_id}")
        await workflow.execute_task(task)


def cmd_list(workflow: CrawlerWorkflow, args):
    """列出所有任务"""
    workflow.print_summary()


def cmd_show(workflow: CrawlerWorkflow, args):
    """显示任务详情"""
    if len(args) < 1:
        print("用法: show <task_id>")
        return

    task_id = args[0]
    task = workflow.task_queue.get_task(task_id)

    if not task:
        print(f"❌ 任务不存在: {task_id}")
        return

    print("\n" + "="*60)
    print(f"任务详情: {task.task_id}")
    print("="*60)
    print(f"名称: {task.name}")
    print(f"URL: {task.start_url}")
    print(f"模板: {task.template_path}")
    print(f"状态: {task.status}")
    print(f"创建时间: {task.created_at}")

    if task.started_at:
        print(f"开始时间: {task.started_at}")
    if task.completed_at:
        print(f"完成时间: {task.completed_at}")

    if task.status == "completed":
        print(f"\n结果:")
        print(f"  访问页面: {task.pages_visited}")
        print(f"  提取产品: {task.products_found}")
        print(f"  结果文件: {task.result_file}")

        # 显示提取的数据
        if task.result_file and Path(task.result_file).exists():
            with open(task.result_file, 'r', encoding='utf-8') as f:
                result = json.load(f)
                products = result.get("products", [])

                if products:
                    print(f"\n提取的产品:")
                    for i, product in enumerate(products[:3], 1):
                        print(f"\n  产品 {i}:")
                        for key, value in product.items():
                            if not key.startswith('_'):
                                print(f"    {key}: {value}")

                    if len(products) > 3:
                        print(f"\n  ... 还有 {len(products) - 3} 个产品")

    elif task.status == "failed":
        print(f"\n错误: {task.error}")

    print("\n配置:")
    for key, value in task.config.items():
        print(f"  {key}: {value}")

    print("="*60)


def cmd_delete(workflow: CrawlerWorkflow, args):
    """删除任务"""
    if len(args) < 1:
        print("用法: delete <task_id>")
        return

    task_id = args[0]
    if task_id not in workflow.task_queue.tasks:
        print(f"❌ 任务不存在: {task_id}")
        return

    del workflow.task_queue.tasks[task_id]
    workflow.task_queue.save()
    print(f"✅ 已删除任务: {task_id}")


def cmd_clear(workflow: CrawlerWorkflow, args):
    """清空所有任务"""
    confirm = input("确认清空所有任务？(y/N): ")
    if confirm.lower() == 'y':
        workflow.task_queue.tasks.clear()
        workflow.task_queue.save()
        print("✅ 已清空所有任务")
    else:
        print("已取消")


def cmd_help(workflow: CrawlerWorkflow, args):
    """显示帮助"""
    print("\n爬虫工作流命令行工具")
    print("="*60)
    print("\n可用命令:")
    print("  add <task_id> <name> <url> [template]  - 添加任务")
    print("  load <config.json>                     - 从文件加载任务")
    print("  list                                   - 列出所有任务")
    print("  show <task_id>                         - 显示任务详情")
    print("  run [task_id]                          - 执行任务（不指定则执行所有）")
    print("  delete <task_id>                       - 删除任务")
    print("  clear                                  - 清空所有任务")
    print("  help                                   - 显示帮助")
    print("  exit                                   - 退出")
    print("\n示例:")
    print("  load tasks_config.json")
    print("  list")
    print("  run")
    print("  show task_001")
    print("="*60)


async def interactive_mode():
    """交互式命令行模式"""
    print("\n🤖 爬虫工作流命令行工具")
    print("输入 'help' 查看帮助，'exit' 退出\n")

    workflow = CrawlerWorkflow(
        llm_config_key="deepseek",
        max_concurrent=1
    )

    commands = {
        "add": cmd_add_task,
        "load": cmd_load_tasks,
        "run": cmd_run,
        "list": cmd_list,
        "show": cmd_show,
        "delete": cmd_delete,
        "clear": cmd_clear,
        "help": cmd_help
    }

    while True:
        try:
            user_input = input("crawler> ").strip()

            if not user_input:
                continue

            if user_input == "exit":
                print("再见！")
                break

            parts = user_input.split()
            cmd = parts[0]
            args = parts[1:]

            if cmd not in commands:
                print(f"❌ 未知命令: {cmd}，输入 'help' 查看帮助")
                continue

            # 执行命令
            if asyncio.iscoroutinefunction(commands[cmd]):
                await commands[cmd](workflow, args)
            else:
                commands[cmd](workflow, args)

        except KeyboardInterrupt:
            print("\n使用 'exit' 退出")
        except Exception as e:
            print(f"❌ 错误: {e}")


async def main():
    """主函数"""
    if len(sys.argv) > 1:
        # 命令行模式
        workflow = CrawlerWorkflow(
            llm_config_key="deepseek",
            max_concurrent=1
        )

        cmd = sys.argv[1]

        if cmd == "load" and len(sys.argv) > 2:
            load_tasks_from_file(sys.argv[2], workflow)
        elif cmd == "run":
            await workflow.run_pending_tasks()
        elif cmd == "list":
            workflow.print_summary()
        else:
            print(f"未知命令: {cmd}")
            print("用法: python cli.py [load <file> | run | list]")
    else:
        # 交互式模式
        await interactive_mode()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n🛑 用户中断")
