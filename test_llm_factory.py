# test_llm_factory.py

import os
import sys
import asyncio
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.spinner import Spinner

# --- 确保脚本可以找到您的核心模块 ---
sys.path.append(os.getcwd())
# ------------------------------------

# 核心模块导入
from core.client.llm_factory import LLMFactory, AbilityType
from core.client.model_info import is_reasoning_model, supports_structured_output

# 【修正】确保从您最新的代码路径导入配置
from base.configs import PMCASystemEnvConfig as EnvConfig
from autogen_agentchat.messages import UserMessage


def run_static_tests(console: Console):
    """
    执行静态配置检查，验证工厂实例化和元数据函数。
    """
    console.rule(f"[bold cyan]PMCA LLM工厂 & 元数据 测试套件[/bold cyan]", style="cyan")
    console.print(
        Panel(
            f"[bold]LLM服务模式 (LLM_TYPE):[/bold] [yellow]{EnvConfig.LLM_TYPE}[/yellow]",
            title="[bold green]全局配置信息[/bold green]",
            border_style="green",
        )
    )

    # --- 测试1: 客户端实例化 ---
    table = Table(title="[bold magenta]1. 静态测试: LLM 客户端实例化[/bold magenta]")
    table.add_column("能力类型", justify="right", style="cyan", no_wrap=True)
    table.add_column("预期厂商", style="yellow")
    table.add_column("预期模型", style="yellow")
    table.add_column("实例化客户端类型", style="green")
    table.add_column("状态", justify="center")

    abilities_to_test = [AbilityType.DEFAULT, AbilityType.CODER, AbilityType.REASONING]

    for ability in abilities_to_test:
        try:
            expected_provider, expected_model = LLMFactory.get_config_for_ability(
                ability
            )
            client = LLMFactory.client(ability)
            client_type_name = type(client).__name__
            status = "✅ 通过"
            table.add_row(
                ability.name,
                expected_provider.value,
                expected_model,
                client_type_name,
                status,
            )
        except Exception as e:
            table.add_row(
                ability.name, "N/A", "N/A", f"[bold red]异常[/bold red]", "❌ 失败"
            )
            console.print(f"[red]错误详情 ({ability.name}): {e}[/red]")
    console.print(table)

    # --- 测试2: 元数据函数 ---
    metadata_table = Table(
        title="[bold magenta]2. 静态测试: 模型元数据函数[/bold magenta]"
    )
    metadata_table.add_column("能力类型", justify="right", style="cyan", no_wrap=True)
    metadata_table.add_column("是否为推理模型?", justify="center")
    metadata_table.add_column("是否支持结构化输出?", justify="center")

    for ability in abilities_to_test:
        try:
            provider, model_name = LLMFactory.get_config_for_ability(ability)
            is_reasoning = is_reasoning_model(provider, model_name)
            supports_structured = supports_structured_output(provider, model_name)
            reasoning_str = (
                f"[green]是[/green]" if is_reasoning else "[grey50]否[/grey50]"
            )
            structured_str = (
                f"[green]是[/green]" if supports_structured else "[red]否[/red]"
            )
            metadata_table.add_row(ability.name, reasoning_str, structured_str)
        except Exception as e:
            metadata_table.add_row(
                ability.name, f"[bold red]异常[/bold red]", f"[bold red]异常[/bold red]"
            )
            console.print(f"[red]错误详情 ({ability.name}): {e}[/red]")
    console.print(metadata_table)


async def run_live_tests(console: Console):
    """
    执行实时API调用测试，并以流式方式处理和显示模型的回答。
    """
    live_table = Table(
        title="[bold magenta]3. 实时测试: 模型问答 (流式)[/bold magenta]"
    )
    live_table.add_column("能力类型", justify="right", style="cyan", no_wrap=True)
    live_table.add_column("测试模型", style="yellow")
    live_table.add_column("状态", justify="center")
    live_table.add_column("模型回答 (片段)", style="green")

    abilities_to_test = [AbilityType.DEFAULT, AbilityType.CODER, AbilityType.REASONING]

    with Live(
        live_table, console=console, screen=False, vertical_overflow="visible"
    ) as live:
        for ability in abilities_to_test:
            provider, model_name = LLMFactory.get_config_for_ability(ability)
            spinner = Spinner("dots", text=f" 正在向 {model_name} 发送问题...")
            live.update(spinner)

            full_reply = ""
            try:
                client = LLMFactory.client(ability)
                messages = [
                    UserMessage(content="你好！请用一句话介绍你自己。", source="user")
                ]

                # --- 【核心修正】完全按照您提供的参考代码逻辑处理流式响应 ---
                response_stream = client.create_stream(messages=messages)

                # 异步遍历流，每次迭代得到的是一个字符串块
                async for chunk in response_stream:
                    if isinstance(chunk, str):
                        full_reply += chunk

                if not full_reply.strip():
                    raise ValueError("模型返回了空内容。")

                snippet = (
                    (full_reply[:70] + "...") if len(full_reply) > 70 else full_reply
                )
                live_table.add_row(
                    ability.name,
                    model_name,
                    "✅ 通信成功",
                    snippet.replace("\n", " "),
                )
            except Exception as e:
                error_snippet = (str(e)[:100] + "...") if len(str(e)) > 100 else str(e)
                live_table.add_row(
                    ability.name,
                    model_name,
                    "[bold red]❌ 通信失败[/bold red]",
                    error_snippet,
                )
            live.update(live_table)
        live.update(live_table)


async def main():
    """主函数，依次执行静态和动态测试。"""
    console = Console()
    run_static_tests(console)
    await run_live_tests(console)
    console.rule("[bold]测试完成[/bold]", style="cyan")


if __name__ == "__main__":
    # 温馨提示：为了获得最佳的命令行输出效果，请先安装 rich 库: pip install rich
    asyncio.run(main())

