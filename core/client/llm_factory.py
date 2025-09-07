from enum import Enum
from typing import Union
from autogen_ext.models.ollama import OllamaChatCompletionClient
from autogen_ext.models.openai import OpenAIChatCompletionClient
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Annotated


from core.client.ollama_model_info import ollama_model_info


# 1. 环境配置
class LLMEnv(BaseSettings):
    LLM_TYPE: str = Annotated[str, Field(..., env="LLM_TYPE")]  # type: ignore[reportGeneralTypeIssues]
    # Qwen / DeepSeek 在线配置
    QWEN_BASE_URL: str = Annotated[str, Field(..., env="QWEN_BASE_URL")]  # type: ignore[reportGeneralTypeIssues]
    QWEN_API_KEY: str = Annotated[str, Field(..., env="QWEN_API_KEY")]  # type: ignore[reportGeneralTypeIssues]
    QWEN_MODEL_NAME: str = Annotated[str, Field(..., env="QWEN_MODEL_NAME")]  # type: ignore[reportGeneralTypeIssues]
    QWEN_CODER_NAME: str = Annotated[str, Field(..., env="QWEN_CODER_NAME")]  # type: ignore[reportGeneralTypeIssues]

    OPENAI_BASE_URL: str = Annotated[str, Field(..., env="OPENAI_BASE_URL")]  # type: ignore[reportGeneralTypeIssues]
    OPENAI_API_KEY: str = Annotated[str, Field(..., env="OPENAI_API_KEY")]  # type: ignore[reportGeneralTypeIssues]
    OPENAI_MODEL_NAME: str = Annotated[str, Field(..., env="OPENAI_MODEL_NAME")]  # type: ignore[reportGeneralTypeIssues]

    DEEPSEEK_BASE_URL: str = Annotated[str, Field(..., env="DEEPSEEK_BASE_URL")]  # type: ignore[reportGeneralTypeIssues]
    DEEPSEEK_API_KEY: str = Annotated[str, Field(..., env="DEEPSEEK_API_KEY")]  # type: ignore[reportGeneralTypeIssues]
    DEEPSEEK_MODEL_NAME: str = Annotated[str, Field(..., env="DEEPSEEK_MODEL_NAME")]  # type: ignore[reportGeneralTypeIssues]
    # Ollama 本地配置
    OLLAMA_HOST: str = Annotated[str, Field(..., env="OLLAMA_HOST")]  # type: ignore[reportGeneralTypeIssues]
    OLLAMA_MODEL_NAME: str = Annotated[str, Field(..., env="OLLAMA_MODEL_NAME")]  # type: ignore[reportGeneralTypeIssues]
    OLLAMA_CODER_NAME: str = Annotated[str, Field(..., env="OLLAMA_CODER_NAME")]  # type: ignore[reportGeneralTypeIssues]

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


LLM_ENV = LLMEnv()


# 2. 枚举类型
class ProviderType(str, Enum):
    QWEN = "qwen"
    DEEPSEEK = "deepseek"
    OPENAI = "openai"


class DutyType(str, Enum):
    BASE = "base"
    CODER = "coder"


# 3. 单一工厂
class LLMFactory:
    """Client Factory"""

    @staticmethod
    def client(
        provider: ProviderType, duty: DutyType
    ) -> Union[OpenAIChatCompletionClient, OllamaChatCompletionClient]:
        mode = LLM_ENV.LLM_TYPE.lower()
        # —— 在线模式 ——
        if mode == "online":
            # 拼 ENV 属性名
            base_url = getattr(LLM_ENV, f"{provider.name}_BASE_URL")
            api_key = getattr(LLM_ENV, f"{provider.name}_API_KEY")

            suffix = "MODEL" if duty == DutyType.BASE else "CODER"
            model = getattr(LLM_ENV, f"{provider.name}_{suffix}_NAME")

            # 构造 OpenAI 客户端
            return OpenAIChatCompletionClient(
                model=model, api_key=api_key, base_url=base_url
            )
        # —— Ollama 本地模式 ——
        elif mode == "ollama":
            host = LLM_ENV.OLLAMA_HOST
            model_name = getattr(LLM_ENV, f"OLLAMA_{duty.name.upper()}_NAME")
            # 从全局字典取 ModelInfo
            model_info = ollama_model_info.get(model_name)
            if model_info is None:
                raise ValueError(
                    f"ModelInfo required for Ollama model '{model_name}' "
                    f"(not found in ollama_model_info)"  # turn0search5
                )
            return OllamaChatCompletionClient(
                model=model_name,
                host=host,
                model_info=model_info,  # 必填，否则会抛警告turn0search3
            )
        else:
            raise ValueError(f"Unsupported LLM_TYPE: {mode}")
