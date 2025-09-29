from typing import Iterable, Optional


class PMCATeamTerminationConfig:
    max_messages: int = 25
    text_mentions: Optional[Iterable[str]] = None
    use_external: bool = True
