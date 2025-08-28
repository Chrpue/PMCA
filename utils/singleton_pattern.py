import threading


class Singleton:
    """
    一个线程安全的、可继承的单例基类。
    任何继承自这个类的子类都将自动成为单例。
    """

    _instances = {}
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        # 使用线程锁来确保在多线程环境下的原子性操作
        with cls._lock:
            # 检查该类是否已经有实例存在
            if cls not in cls._instances:
                # 如果不存在，则创建一个新实例
                instance = super().__new__(cls)
                cls._instances[cls] = instance
        # 返回已存在的或新创建的实例
        return cls._instances[cls]
