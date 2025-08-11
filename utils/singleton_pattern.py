def singleton(cls, *args, **kwargs):
    """
    定义一个单例装饰器
    """

    instance = {}

    def wrapperSingleton(*args, **kwargs):
        if cls not in instance:
            instance[cls] = cls(*args, **kwargs)
        return instance[cls]

    return wrapperSingleton
