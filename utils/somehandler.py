import re


def swarm_name_to_snake(text: str) -> str:
    """
    将包含空格或连字符的字符串转换为小写下划线格式。

    该方法会执行以下操作：
    1. 将一个或多个连续的空格或连字符替换为单个下划线。
    2. 将整个字符串转换为小写。

    Args:
        text: 需要转换的原始字符串。

    Returns:
        转换后的小写下划线格式字符串。
    """
    s = re.sub(r"[\s-]+", "_", text)
    return s.lower()

