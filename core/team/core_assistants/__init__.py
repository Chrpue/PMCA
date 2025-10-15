from .core_assistants import PMCACoreAssistants
from .orchestrator import PMCAOrchestrator
from .task_triage import PMCATriage
from .task_triage_reviewer import PMCATriageReviewer
from .task_triage_structured import PMCATriageStructured
from .user_proxy import PMCAUserProxy


__all__ = [
    "PMCACoreAssistants",
    "PMCAOrchestrator",
    "PMCAUserProxy",
    "PMCATriage",
    "PMCATriageReviewer",
    "PMCATriageStructured",
]


def __getattr__(name: str):
    if name == "PMCAOrchestrator":
        from .orchestrator import PMCAOrchestrator

        return PMCAOrchestrator
    if name == "PMCAUserProxy":
        from .user_proxy import PMCAUserProxy

        return PMCAUserProxy
    if name == "PMCATriage":
        from .task_triage import PMCATriage

        return PMCATriage
    if name == "PMCATriageReviewer":
        from .task_triage_reviewer import PMCATriageReviewer

        return PMCATriageReviewer
    if name == "PMCATriageStructured":
        from .task_triage_structured import PMCATriageStructured

        return PMCATriageStructured
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
