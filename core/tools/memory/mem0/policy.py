class PMCAMem0OpsPolicy:
    """
    统一的策略开关（全局）。智能体可通过 memory_contract.infer_default 覆盖。
    """

    CONTRACT_SCOPE: str = "target"
    DEFAULT_ADD_INFER: bool = True  # 抽取失败是否不落库（更干净）
    MAX_LIST_BATCH: int = 1000
    HTTP_TIMEOUT_S: int = 8
    DEFAULT_QDRANT_DISTANCE: str = "Cosine"  # 与嵌入一致（bge-m3）
