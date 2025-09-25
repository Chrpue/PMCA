import importlib
import pkgutil
from loguru import logger

# --- 魔法开始的地方 ---

# 1. 定义包名和路径
PACKAGE_NAME = __name__
PACKAGE_PATH = __path__

logger.info(f"开始在包 '{PACKAGE_NAME}' 中自动发现和注册智能体...")

# 2. 遍历包内的所有模块
# pkgutil.walk_packages 会递归地找到所有子包和子模块
module_count = 0
for _, module_name, _ in pkgutil.walk_packages(PACKAGE_PATH, PACKAGE_NAME + "."):
    try:
        # 3. 动态导入每个找到的模块
        # 这个导入动作会执行模块顶层的代码，特别是我们的 @register 装饰器
        importlib.import_module(module_name)
        logger.debug(f"成功从模块 '{module_name}' 导入并注册智能体。")
        module_count += 1
    except Exception as e:
        logger.error(f"导入模块 {module_name} 时失败: {e}")

if module_count > 0:
    logger.success(
        f"智能体自动发现完成。在 '{PACKAGE_NAME}' 中共加载了 {module_count} 个模块。"
    )
else:
    logger.warning(f"在 '{PACKAGE_NAME}' 中没有发现任何可加载的智能体模块。")
