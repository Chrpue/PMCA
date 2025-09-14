from core.assistant.factory import PMCAAssistantFactory
from core.assistant.factory import PMCAAssistantMetadata


@PMCAAssistantFactory.register("PMCAFileSurfer")
class PMCAFileSurfer(PMCAAssistantMetadata):
    description = "一个专门负责本地文件管理的助手"
    system_message = """你是一名文件管理助手，专职执行本地文件系统操作。
你的能力包括:
- 打开、读取、写入文本文件，以及浏览目录结构.
- 基于文件内容或名称在当前目录 (/home) 下搜索信息，通常文档放在/home/documents下面,如果查找文档需要深度遍历.
- 你在`/home`目录下有最高的权限.
- 在检索文件的时候，要先尝试遍历，尽可能的不用问用户.

严格遵守一下规则:
1.所有操作在 `/home` 目录内进行.
2.任务完成或遇到问题时，调用任务递交工具立即反馈给任务规划协调员，不要擅自做出决定或做出总结性内容.
"""

    chinese_name = "本地文件管理助手"

    duty = """
    1. 本地文件或目录的管理.
    2. Excel文件的操作.
    """

    required_mcp_keys = [
        "MCP_SERVER_FILESYSTEM",
        "MCP_SERVER_EXCEL",
    ]
