from typing import Dict, Tuple
from autogen_core.models import ModelFamily, ModelInfo
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .llm_factory import ProviderType

MODEL_INFO: Dict[Tuple[str, str], ModelInfo] = {
    ("ollama", "qwen3:32b-fp16"): ModelInfo(
        vision=False,
        function_calling=True,
        json_output=True,
        family=ModelFamily.UNKNOWN,
        structured_output=True,
        multiple_system_messages=True,
    ),
    ("openai", "gpt-5"): ModelInfo(
        vision=False,
        function_calling=True,
        json_output=True,
        family=ModelFamily.GPT_5,
        structured_output=True,
        multiple_system_messages=True,
    ),
    ("gemini", "gemini-2.5-pro"): ModelInfo(
        vision=False,
        function_calling=True,
        json_output=True,
        family=ModelFamily.GEMINI_2_5_PRO,
        structured_output=True,
        multiple_system_messages=True,
    ),
    ("deepseek", "deepseek-chat"): ModelInfo(
        vision=False,
        function_calling=True,
        json_output=True,
        family=ModelFamily.UNKNOWN,
        structured_output=True,
        multiple_system_messages=True,
    ),
    ("deepseek", "deepseek-reasoner"): ModelInfo(
        vision=False,
        function_calling=False,
        json_output=True,
        family=ModelFamily.UNKNOWN,
        structured_output=False,
        multiple_system_messages=True,
    ),
    ("qwen", "qwen-max-latest"): ModelInfo(
        vision=False,
        function_calling=True,
        json_output=True,
        family=ModelFamily.UNKNOWN,
        structured_output=True,
        multiple_system_messages=True,
    ),
    # "qwq:latest": ModelInfo(
    #     vision=False,
    #     function_calling=True,
    #     json_output=True,
    #     family=ModelFamily.UNKNOWN,
    #     structured_output=True,
    #     multiple_system_messages=True,
    # ),
    # "qwen3:30b-a3b": ModelInfo(
    #     vision=False,
    #     function_calling=True,
    #     json_output=True,
    #     family=ModelFamily.UNKNOWN,
    #     structured_output=True,
    #     multiple_system_messages=True,
    # ),
    # "qwen3:32b-fp16": ModelInfo(
    #     vision=False,
    #     function_calling=True,
    #     json_output=True,
    #     family=ModelFamily.UNKNOWN,
    #     structured_output=True,
    #     multiple_system_messages=True,
    # ),
    # "qwen2.5-coder:32b": ModelInfo(
    #     vision=False,
    #     function_calling=True,
    #     json_output=True,
    #     family=ModelFamily.UNKNOWN,
    #     structured_output=False,
    #     multiple_system_messages=True,
    # ),
}
# --------------------------------------------------------------------------
# 模型的扩展元数据 (用于存储自定义属性)
# --------------------------------------------------------------------------
_MODEL_METADATA: Dict[Tuple[str, str], Dict[str, bool]] = {
    # 在这里标记哪些模型是专用的推理模型
    ("deepseek", "deepseek-reasoner"): {"is_reasoning": True},
}


def is_reasoning_model(provider: "ProviderType", model_name: str) -> bool:
    """
    检查一个模型是否被标记为推理模型。
    这个函数是纯粹的，只依赖于传入的参数和自身的元数据。
    """
    metadata = _MODEL_METADATA.get((provider.value, model_name), {})
    return metadata.get("is_reasoning", False)


def supports_structured_output(provider: "ProviderType", model_name: str) -> bool:
    """
    检查一个模型是否支持结构化输出。
    """
    info = MODEL_INFO.get((provider.value, model_name))
    return bool(info and getattr(info, "structured_output", False))
