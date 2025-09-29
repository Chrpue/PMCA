import asyncio
from loguru import logger
import sys
from pathlib import Path

# --- 动态路径设置 ---
try:
    project_root = Path(__file__).resolve().parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
except NameError:
    project_root = Path.cwd()
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

# --- 核心导入 ---
from dotenv import load_dotenv

load_dotenv()

from core.memory.factory.mem0 import PMCAMem0LocalService
from autogen_core.memory import MemoryContent


async def run_final_diagnostic():
    """
    一个独立的、最小化的诊断脚本，用于“审问” Mem0Memory 实例的内部状态。
    """
    AGENT_NAME = "FinalDiagnosticTester"
    logger.info(f"开始为智能体 '{AGENT_NAME}' 进行 mem0 最终诊断...")

    mem_instance = None
    try:
        # 1. 获取 mem0 实例
        logger.info("正在获取 Mem0Memory 实例...")
        mem_instance = PMCAMem0LocalService.memory(AGENT_NAME)
        logger.success("成功获取 Mem0Memory 实例对象。")

        # --- 核心诊断步骤 ---
        logger.info("----------- 开始内部状态诊断 -----------")

        # 审问 _client 属性
        internal_client = getattr(mem_instance, "_client", "!!! NOT FOUND !!!")
        logger.info(f"实例的 '_client' 属性是: {internal_client}")
        logger.info(f"'_client' 属性的类型是: {type(internal_client)}")

        # 审问 _client 是否有 close 方法
        if internal_client != "!!! NOT FOUND !!!":
            has_close_method = hasattr(internal_client, "close") and callable(
                internal_client.close
            )
            logger.info(f"'_client' 是否拥有可调用的 'close' 方法: {has_close_method}")

        logger.info("----------- 诊断结束 -----------")

        # 2. 尝试添加一条简单的记忆
        logger.info("继续尝试调用 add_memory 方法...")
        await PMCAMem0LocalService.add_memory(
            AGENT_NAME, "这是一条用于诊断的记录。", {"source": "final_diagnostic"}
        )
        logger.success("add_memory 方法调用完成（但这不代表写入成功）。")

    except Exception as e:
        logger.error("在诊断过程中捕获到异常！")
        logger.exception(e)

    finally:
        # 即使之前的 shutdown 不完美，我们依然调用它以保持流程完整
        if mem_instance:
            await PMCAMem0LocalService.shutdown()
        logger.info("诊断脚本执行完毕。请检查上面的诊断日志。")


if __name__ == "__main__":
    asyncio.run(run_final_diagnostic())
