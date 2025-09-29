import importlib
import pkgutil
import inspect
from loguru import logger

# 关键改动：首先从 factory 导入所需的核心类
from core.assistant.factory import PMCAAssistantFactory, PMCAAssistantMetadata

PACKAGE_NAME = __name__
PACKAGE_PATH = __path__

logger.info(f"开始在包 '{PACKAGE_NAME}' 中自动发现和注册智能体...")

# 遍历包内的所有模块
for _, module_name, _ in pkgutil.walk_packages(PACKAGE_PATH, PACKAGE_NAME + "."):
    try:
        # 动态导入模块
        module = importlib.import_module(module_name)

        # 在模块中查找所有继承自 PMCAAssistantMetadata 的类
        for name, obj in inspect.getmembers(module):
            if (
                inspect.isclass(obj)
                and issubclass(obj, PMCAAssistantMetadata)
                and obj is not PMCAAssistantMetadata
            ):
                # 从类定义中获取业务类型 (biz_type)，通常是类名
                # 或者您可以约定一个类属性来存储它，例如 a.biz_type
                biz_type = obj.__name__

                # 直接调用注册方法，而不是在类定义上使用装饰器
                PMCAAssistantFactory.register(biz_type)

    except Exception as e:
        # 错误日志保持不变
        logger.error(f"处理模块 {module_name} 时失败: {e}")

logger.success("智能体自动发现和注册完成。")
