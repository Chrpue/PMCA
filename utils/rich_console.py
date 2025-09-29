from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.theme import Theme

# 自定义主题，用于统一颜色风格
custom_theme = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "danger": "bold red",
        "success": "green",
        "title": "bold magenta",
    }
)

# 创建一个全局的 Console 实例
console = Console(theme=custom_theme)


def PMCAPanel(content: str, title: str = "信息", style: str = "info"):
    """
    使用 PMCA 风格的 Panel 打印信息.
    """
    panel_content = Text(content, justify="left")
    console.print(
        Panel(
            panel_content,
            title=f"[{style}]{title}[/{style}]",
            border_style=style,
            expand=False,
        )
    )


def PMCAInfo(message: str):
    """打印 PMCA 风格的普通信息."""
    console.print(f"[info]信息:[/] {message}")


def PMCAWarning(message: str):
    """打印 PMCA 风格的警告信息."""
    console.print(f"[warning]警告:[/] {message}")


def PMCADanger(message: str):
    """打印 PMCA 风格的危险/错误信息."""
    console.print(f"[danger]错误:[/] {message}")


def PMCASuccess(message: str):
    """打印 PMCA 风格的成功信息."""
    console.print(f"[success]成功:[/] {message}")


def PMCATitle(message: str):
    """打印 PMCA 风格的大标题."""
    console.rule(f"[title]{message}", style="title")

