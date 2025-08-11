from typing import List, Optional


class PMCAAgentMetadata:
    """Agent Base Metadata"""

    name: Optional[str] = None
    description: str = ""
    system_message: str = ""

    chinese_name: str = ""
    duty: str = ""

    required_mcp_keys: List[str] = []
