CONTRACT_OF_MASTEROFMEMORY = {
    "name": "PMCAMasterOfMemory",
    "memory_contract": {
        "schema": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "PMCAMasterOfMemory metadata",
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "source": {
                    "type": "string",
                    "description": "记忆来源，如：知识蒸馏/对话提取/脚本导入",
                },
                "business": {
                    "type": "string",
                    "description": "业务域：钻完井/测井/录井/...",
                },
                "type": {
                    "type": "string",
                    "description": "载体类型：知识库/本地文件/对话提取/...",
                },
            },
            "required": ["business", "type"],
        },
        "vocab": {
            "business": {
                "allowed": ["钻完井", "测井", "录井"],
                "aliases": {"完井": "钻完井", "钻井完工": "钻完井"},
            },
            "type": {
                "allowed": ["知识库", "本地文件", "对话提取"],
                "aliases": {
                    "kb": "知识库",
                    "local_file": "本地文件",
                    "conversation": "对话提取",
                },
            },
        },
        "index_fields": [
            "business",
            "type",
            "run_id",
        ],  # 只索引常用过滤字段（官方建议）
        "infer_default": True,  # 可选覆盖全局 add 策略（未提供则走全局）
    },
}
