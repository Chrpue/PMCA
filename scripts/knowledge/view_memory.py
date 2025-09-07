import os
import sys
import argparse
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional

from loguru import logger
from dotenv import load_dotenv

# --- 动态添加项目根目录到Python路径 ---
try:
    # 假定此脚本位于 project_root/scripts/knowledge/ 目录下
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from core.memory.factory import PMCAMirixMemoryManager
except ImportError as e:
    print(
        f"Error: 无法导入项目模块。请确保此脚本位于您项目根目录的 'scripts/knowledge' 子目录下。"
    )
    print(f"Details: {e}")
    sys.exit(1)


# --- Loguru Logger Setup ---
def setup_logger():
    """配置Loguru日志记录器。"""
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="<level>{message}</level>")


class MemoryViewer:
    """
    一个用于查看指定智能体在Mirix中所有类型记忆的工具。
    """

    def __init__(self):
        logger.info("Initializing Mirix Memory Manager...")
        self.mirix_manager = PMCAMirixMemoryManager()
        logger.success("Mirix Memory Manager initialized.")

    async def view_memory(self, agent_name: str):
        """
        获取并展示指定智能体的完整记忆档案。
        """
        target_user_id = self.mirix_manager.agent_to_user_id.get(agent_name)
        if not target_user_id:
            logger.error(
                f"Agent '{agent_name}' not found in Mirix. Please check the name or run the seeding script."
            )
            available_agents = list(self.mirix_manager.agent_to_user_id.keys())
            if available_agents:
                logger.info("Available agents are: " + ", ".join(available_agents))
            return

        logger.info(
            f"Fetching full memory profile for '{agent_name}' (User ID: {target_user_id})..."
        )

        # --- **修复：使用 asyncio.to_thread 并发执行同步的API调用** ---
        memory_types = {
            "Core Memory": self.mirix_manager.client.get_core_memory,
            "Episodic Memory": self.mirix_manager.client.get_episodic_memory,
            "Semantic Memory": self.mirix_manager.client.get_semantic_memory,
            "Procedural Memory": self.mirix_manager.client.get_procedural_memory,
        }

        # 为每个同步函数创建一个在线程中运行的协程
        tasks = [
            asyncio.to_thread(func, target_user_id) for func in memory_types.values()
        ]

        # 并发执行所有协程
        results = await asyncio.gather(*tasks)

        # 将结果与记忆类型重新组合成字典
        memory_profile = dict(zip(memory_types.keys(), results))
        # --- 修复结束 ---

        # 格式化输出
        try:
            from rich.console import Console
            from rich.panel import Panel
            from rich.json import JSON
            from rich.padding import Padding

            console = Console()
            console.rule(
                f"[bold cyan]Memory Profile for: {agent_name}[/bold cyan]", style="cyan"
            )

            for mem_type, content in memory_profile.items():
                if content:
                    json_str = json.dumps(content, indent=2, ensure_ascii=False)
                    console.print(
                        Panel(
                            JSON(json_str),
                            title=f"[bold yellow]{mem_type}[/bold yellow]",
                            border_style="yellow",
                        )
                    )
                else:
                    console.print(
                        Panel(
                            "[italic grey37]No content found.[/italic grey37]",
                            title=f"[bold grey37]{mem_type}[/bold grey37]",
                            border_style="grey37",
                        )
                    )

        except ImportError:
            logger.warning(
                "Rich library not installed. Falling back to plain text output."
            )
            logger.warning("For better visualization, run: pip install rich")
            print(json.dumps(memory_profile, indent=2, ensure_ascii=False))


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="A tool to view the complete memory profile of a specific agent from Mirix.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-a",
        "--agent",
        type=str,
        required=True,
        help="The name of the agent whose memory you want to view.",
    )
    args = parser.parse_args()

    load_dotenv()
    viewer = MemoryViewer()
    await viewer.view_memory(args.agent)


if __name__ == "__main__":
    setup_logger()
    asyncio.run(main())
