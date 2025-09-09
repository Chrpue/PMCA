import asyncio
from loguru import logger
import sys
from pathlib import Path

# --- 动态添加项目根目录到Python路径 ---
# 这确保了无论您在哪个目录下运行此脚本，它都能找到核心模块
try:
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
except IndexError:
    print("Error: 请确保此脚本位于您项目根目录的 'scripts' 子目录下。")
    sys.exit(1)

# --- 核心模块导入 ---
try:
    from autogen_core.models import UserMessage
    from core.client.llm_factory import LLMFactory, ProviderType, DutyType
    from utils.rich_console import PMCATitle, PMCASuccess, PMCADanger, PMCAInfo
except ImportError as e:
    print(f"Error: 无法导入项目模块。请确保您的项目结构正确且依赖已安装。")
    print(f"Details: {e}")
    sys.exit(1)


async def test_client(provider: ProviderType, duty: DutyType):
    """
    测试单个客户端的创建和API调用。
    """
    PMCATitle(f"开始测试 Provider: {provider.name}, Duty: {duty.name}")

    try:
        # 1. 使用工厂创建客户端
        PMCAInfo("1. 正在使用 LLMFactory 创建客户端...")
        client = LLMFactory.client(provider, duty)
        PMCASuccess(f"✅ 客户端创建成功！类型: {client.__class__.__name__}")
        # PMCAInfo(f"   模型名称: {client.model}")

        # 2. 准备一条简单的测试消息
        if duty.value == "base":
            messages = [UserMessage(content="你是谁", source="user")]
        else:
            messages = [
                UserMessage(
                    content="给我生成一段生成随机数的代码，随便什么都可以",
                    source="user",
                )
            ]

        # 3. 发起一次流式API调用
        PMCAInfo("2. 正在发起流式 API 调用...")
        response_content = ""
        stream = client.create_stream(messages=messages)

        print("   模型响应: ", end="", flush=True)
        async for response in stream:
            if isinstance(response, str):
                print(response, end="", flush=True)
                response_content += response
        print("\n")  # 换行

        if not response_content.strip():
            raise ValueError("模型返回了空响应。")

        PMCASuccess("✅ API 调用成功并收到响应！")

    except Exception as e:
        PMCADanger(f"❌ 测试失败: {e}")
        PMCADanger(
            "   请检查您的 .env 文件中的相关配置 (API Key, Base URL, Model Name) 是否正确，并确保模型服务正在运行。"
        )
        return False

    return True


async def main():
    """
    主函数，执行所有测试。
    """
    # PMCATitle(f"LLMFactory & 统一配置 ({EnvConfig.LLM_PROVIDER.upper()}) 测试")

    # try:
    #     provider = ProviderType(EnvConfig.LLM_PROVIDER.lower())
    # except ValueError:
    #     PMCADanger(
    #         f"错误：.env 文件中配置的 LLM_PROVIDER '{EnvConfig.LLM_PROVIDER}' 是无效的。"
    #     )
    #     return

    # 测试基础职责模型
    base_success = await test_client(ProviderType.DEEPSEEK, DutyType.BASE)

    print("\n" + "=" * 50 + "\n")

    # 测试编码职责模型
    # coder_success = await test_client(ProviderType.QWEN, DutyType.CODER)

    # print("\n" + "=" * 50 + "\n")
    #
    # if base_success and coder_success:
    #     PMCASuccess("🎉 所有客户端测试均已成功通过！您的配置和 LLMFactory 工作正常。")
    # else:
    #     PMCADanger("🔥 部分或全部测试失败，请检查上面的错误日志。")


if __name__ == "__main__":
    # 运行异步主函数
    asyncio.run(main())
