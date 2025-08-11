from autogen_core.models import ModelFamily, ModelInfo

ollama_model_info: dict[str, ModelInfo] = {
    "qwq:latest": ModelInfo(
        vision=False,
        function_calling=True,
        json_output=True,
        family=ModelFamily.UNKNOWN,
        structured_output=True,
        multiple_system_messages=True,
    ),
    "qwen3:30b-a3b": ModelInfo(
        vision=False,
        function_calling=True,
        json_output=True,
        family=ModelFamily.UNKNOWN,
        structured_output=True,
        multiple_system_messages=True,
    ),
    "qwen3:32b-fp16": ModelInfo(
        vision=False,
        function_calling=True,
        json_output=True,
        family=ModelFamily.UNKNOWN,
        structured_output=True,
        multiple_system_messages=True,
    ),
    "qwen2.5-coder:32b": ModelInfo(
        vision=False,
        function_calling=True,
        json_output=True,
        family=ModelFamily.UNKNOWN,
        structured_output=False,
        multiple_system_messages=True,
    ),
}
