import re
import keyword
import unicodedata


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


def make_valid_identifier(name: str, *, prefix: str = "agent") -> str:
    # 1) 统一化
    s = unicodedata.normalize("NFKC", name).strip()
    # 2) 非 [A-Za-z0-9_] 全部替换成下划线
    s = re.sub(r"\W", "_", s)
    # 3) 不允许以数字开头
    if not s or s[0].isdigit():
        s = f"{prefix}_{s}"
    # 4) 关键字与保留词
    if keyword.iskeyword(s) or s in {"async", "await", "None"}:
        s = f"{s}_agent"
    # 5) 连续下划线压缩，首尾去下划线
    s = re.sub(r"_+", "_", s).strip("_")
    # 6) 兜底
    if not s or not s.isidentifier():
        s = f"{prefix}_agent"
    return s
