from typing import Dict, Any, List
from base.agents.abstract import PMCAAgentFactory


class PMCATeamInitialize:
    """Initialize Team Compoment"""

    def __init__(self) -> None:
        self._exclude_names = [
            "PMCAPlanner",
            "PMCATeamDecision",
            "PMCATeamDecisionCritic",
        ]
        self._partners_infos: Dict[str, Dict[str, Any]] = self._get_partners_infos(
            exclude_names=self._exclude_names
        )
        self._partners_infos_text: str = self._get_partners_description()

    def _get_partners_infos(
        self, exclude_names: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """获取agents列表信息"""
        agents_infos: Dict[str, Dict[str, Any]] = (
            PMCAAgentFactory.list_registered_agents()
        )

        return {
            key: value
            for key, value in agents_infos.items()
            if key not in exclude_names
        }

    def _get_partners_description(self) -> str:
        """获取智能体描述列表"""
        lines: List[str] = []
        for partner, info in self._partners_infos.items():
            duty = info.get("duty", "")
            lines.append(f"- {partner}: {duty}")

        return "\n".join(lines)
