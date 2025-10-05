from enum import StrEnum
from typing import List


class PMCACoreAssistants(StrEnum):
    TRIAGE = "PMCATriage"
    TRIAGE_REVIEWER = "PMCATriageReviewer"
    TRIAGE_STRUCTURED = "PMCATriageStructured"
    ORCHESTRATOR = "PMCAOrchestrator"
    SWARM_SUPERVISOR = "PMCASwarmSupervisor"
    USER_PROXY = "PMCAUserProxy"

    @classmethod
    def is_core_assistant(cls, name: str) -> bool:
        """
        给定一个assistant名字判断它是否是PMCACoreAssistants中的一员
        """
        return name in [member.value for member in cls]

    @classmethod
    def get_core_assistants(cls) -> List[str]:
        """
        获取所有PMCACoreAssistants的成员
        """
        return [member.value for member in cls]
