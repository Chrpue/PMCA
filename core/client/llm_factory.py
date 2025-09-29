from enum import Enum
from loguru import logger
from typing import Union, Optional, Tuple

from autogen_ext.models.ollama import OllamaChatCompletionClient
from autogen_ext.models.openai import OpenAIChatCompletionClient

# 导入单例配置实例
from base.configs import PMCASystemEnvConfig
from core.client.model_info import MODEL_INFO


class ProviderType(str, Enum):
    QWEN = "qwen"
    DEEPSEEK = "deepseek"
    OPENAI = "openai"
    OLLAMA = "ollama"
    GEMINI = "gemini"


class AbilityType(str, Enum):
    """定义Agent的核心能力类型，用于映射到.env中的模型配置。"""

    DEFAULT = "default"
    CODER = "coder"
    REASONING = "reasoning"


class LLMFactory:
    """
    该工厂的逻辑核心是：根据能力（Ability）确定模型和提供商，再根据全局服务模式（LLM_TYPE）创建对应的客户端实例。
    """

    @staticmethod
    def get_config_for_ability(ability: AbilityType) -> Tuple[ProviderType, str]:
        """从环境变量配置中，为指定的模型能力获取Provider和ModelName。"""

        provider_key = f"{ability.name.upper()}_PROVIDER"
        model_key = f"{ability.name.upper()}_MODEL"

        provider_str = getattr(PMCASystemEnvConfig, provider_key).lower()
        model_name = getattr(PMCASystemEnvConfig, model_key)

        return ProviderType(provider_str), model_name

    @staticmethod
    def client(
        ability: AbilityType = AbilityType.DEFAULT,
        provider_override: Optional[ProviderType] = None,
        model_name_override: Optional[str] = None,
    ) -> Union[OpenAIChatCompletionClient, OllamaChatCompletionClient]:
        """
        创建并返回一个配置好的LLM客户端实例。

        Args:
            ability (AbilityType): Agent的能力类型，用于从.env选择默认模型。
            provider_override (Optional[ProviderType]): (可选) 强制指定Provider，覆盖.env配置。
            model_name_override (Optional[str]): (可选) 强制指定模型名称，覆盖.env配置。

        Returns:
            LLM客户端实例。
        """
        # 步骤 1: 确定最终要使用的模型和提供商
        if provider_override and model_name_override:
            final_provider, final_model_name = provider_override, model_name_override
        else:
            # 从.env配置中根据能力获取
            final_provider, final_model_name = LLMFactory.get_config_for_ability(
                ability
            )

        # 步骤 2: 根据全局LLM_TYPE，决定实例化哪种客户端
        service_mode = PMCASystemEnvConfig.LLM_TYPE.lower()

        # --- 使用Ollama本地服务 ---
        if service_mode == "ollama":
            if final_provider != ProviderType.OLLAMA:
                raise ValueError(
                    f"LLM_TYPE配置为'ollama'，但能力'{ability.name}'的PROVIDER被错误地设置为'{final_provider.value}'。"
                    f"请在.env文件中将其修正为'ollama'。"
                )

            # --- 【核心修正】---
            # 严格检查 model_info 是否存在，如果不存在，则抛出清晰的配置错误。
            info = MODEL_INFO.get((final_provider.value, final_model_name))

            if not info:
                # 快速失败，并提供明确的修复指导
                raise ValueError(
                    f"\n\n[配置错误] Ollama模型 '{final_model_name}' 的 ModelInfo 未定义！\n"
                    f"请在 `core/client/model_info.py` 文件中的 `MODEL_INFO` 字典里为它添加配置。\n"
                    f"示例：\n"
                    f'    ("{final_provider.value}", "{final_model_name}"): ModelInfo(\n'
                    f"        vision=False, function_calling=True, ...\n"
                    f"    ),\n"
                )

            return OllamaChatCompletionClient(
                model=final_model_name,
                host=PMCASystemEnvConfig.OLLAMA_HOST,
                model_info=info,
            )  # --- 使用在线服务 (OpenAI协议) ---
        elif service_mode == "openai":
            provider_name_upper = final_provider.name.upper()
            base_url_key = f"{provider_name_upper}_BASE_URL"
            api_key_key = f"{provider_name_upper}_API_KEY"
            if not hasattr(PMCASystemEnvConfig, base_url_key) or not hasattr(
                PMCASystemEnvConfig, api_key_key
            ):
                raise ValueError(
                    f"在.env文件中找不到'{base_url_key}'或'{api_key_key}'的配置。"
                )
            base_url = getattr(PMCASystemEnvConfig, base_url_key)
            api_key = getattr(PMCASystemEnvConfig, api_key_key)
            return OpenAIChatCompletionClient(
                model=final_model_name, api_key=api_key, base_url=base_url
            )

        # --- 异常处理 ---
        else:
            raise ValueError(
                f"不支持的 LLM_TYPE: '{service_mode}'。请在.env中配置为 'openai' 或 'ollama'。"
            )
