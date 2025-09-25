from __future__ import annotations
from typing import TYPE_CHECKING, Any, Dict


from base.prompts.task_triage import (
    PMCATRIAGE_SYSTEM_MESSAGE,
    PMCATRIAGE_REVIEWER_SYSTEM_MESSAGE,
    PMCATRIAGE_STRUCTURED_SYSTEM_MESSAGE,
)

if TYPE_CHECKING:
    from .assistant_factory import PMCAAssistantFactory
    from core.team.core_assistants import PMCACoreAssistants


class PMCAAssistantFilter:
    """
    一个专门负责构建核心智能体运行时参数的类。
    它将所有与核心智能体相关的特殊逻辑（如动态提示词构建）集中管理，
    使 AssistantFactory 保持通用和纯粹。
    """

    def __init__(self, factory_instance):
        """
        初始化过滤器。

        Args:
            factory_instance: 对 AssistantFactory 的引用，用于访问其辅助方法。
        """
        self._factory = factory_instance

    def build_params(
        self, biz_type: str, base_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        根据核心智能体的业务类型，调用相应的构建方法来生成并合并专属参数。
        """
        from core.team.core_assistants import PMCACoreAssistants

        builder_map = {
            PMCACoreAssistants.TRIAGE.value: self._build_triage_params,
            PMCACoreAssistants.TRIAGE_REVIEWER.value: self._build_triage_reviewer_params,
            PMCACoreAssistants.TRIAGE_STRUCTURED.value: self._build_triage_structured_params,
        }

        builder = builder_map.get(biz_type)
        if builder:
            return builder(base_params)

        # 如果不是核心智能体，则直接返回原始参数
        return base_params

    def _build_triage_params(self, base_params: Dict[str, Any]) -> Dict[str, Any]:
        """为 PMCATriage 动态构建提示词。"""
        final_system_message = PMCATRIAGE_SYSTEM_MESSAGE.format(
            available_assistants=self._factory.professional_assistants_description()
        )

        base_params["system_message"] = final_system_message
        return base_params

    def _build_triage_reviewer_params(
        self, base_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """为 PMCATriageReviewer 动态构建提示词。"""
        final_system_message = PMCATRIAGE_REVIEWER_SYSTEM_MESSAGE.format(
            available_assistants=self._factory.professional_assistants_description()
        )
        base_params["system_message"] = final_system_message
        return base_params

    def _build_triage_structured_params(
        self, base_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """为 PMCATriageStructured 设置静态提示词。"""
        base_params["system_message"] = PMCATRIAGE_STRUCTURED_SYSTEM_MESSAGE
        # 还可以添加如此智能体专用的llm_config等
        # from core.client.llm_factory import PMCALLMFactory
        # base_params["llm_config"] = PMCALLMFactory.create_llm_config(temperature=0.0)
        return base_params
