CONTRACT_OF_MASTEROFMEMORY = {
    "name": "PMCAMasterOfMemory",
    "memory_contract": {
        # ---- JSON Schema (2020-12)：极简 & 通用 ----
        "schema": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "PMCAMasterOfMemory memory metadata (minimal & general)",
            "type": "object",
            "additionalProperties": False,
            "properties": {
                # 可选：人类可读短标题（≤ 60 字符），如“卡钻事故”
                "title": {
                    "type": "string",
                    "maxLength": 10,
                    "description": "短标题（≤10汉字）。",
                },
                # 必填：通用资源类型（不绑定业务）
                "type": {
                    "type": "string",
                    "enum": ["observation", "rule", "procedure", "faq", "note"],
                    "description": "资源类型：observation|rule|procedure|faq|note。",
                },
                # 必填：主题标签（通用 slug 列表，不绑定任何行业词表）
                "subject": {
                    "type": "array",
                    "minItems": 1,
                    "uniqueItems": True,
                    "items": {
                        "type": "string",
                        "pattern": "^[a-z0-9][a-z0-9_-]{0,62}$",
                    },
                    "description": "主题/学科标签（slug），如 ['drilling','operations']；不限定具体领域。",
                },
                # 可选：来源定位（URL/路径），不强制 URI 校验
                "source_uri": {
                    "type": ["string", "null"],
                    "maxLength": 1024,
                    "description": "可选：来源链接或文件定位。",
                },
                # 可选溯源（W3C PROV 精简）：生成活动 & 责任主体
                "wasGeneratedBy": {
                    "type": "string",
                    "maxLength": 128,
                    "description": "生成方式：knowledge_distillation|dialog_mining|file_ingest|manual 等。",
                },
                "wasAttributedTo": {
                    "type": "string",
                    "maxLength": 128,
                    "description": "责任主体（谁写入/加工），如 PMCAMasterOfMemory。",
                },
                # 可选：轻量领域标签（最多 5 个键；值一律字符串）
                "labels": {
                    "type": "object",
                    "additionalProperties": {"type": "string", "maxLength": 256},
                    "maxProperties": 5,
                    "description": "可选：领域标签，如 {'severity':'high'}（≤5键）；不强制、可不使用。",
                },
            },
            "required": ["type", "subject"],
        },
        # ---- 受控取值（最小化）：仅保留 type 的常见别名；subject 不再绑定允许集 ----
        "vocab": {
            "type": {
                "allowed": ["observation", "rule", "procedure", "faq", "note"],
                "aliases": {
                    "观察": "observation",
                    "规则": "rule",
                    "流程": "procedure",
                    "常见问题": "faq",
                    "笔记": "note",
                },
            },
            # subject：通用 slug，不提供 allowed 集；如需别名，可按需加到 aliases
            "subject": {"allowed": [], "aliases": {}},
        },
        # ---- 建议建立的 Qdrant 索引（仅过滤常用字段）----
        # Qdrant：title 适合 "text"（全文）；type/subject 适合 "keyword"（枚举/标签）
        # 你在 provider 里可据此创建对应的 payload index 类型。
        "index_fields": ["title", "type", "subject"],
        # ---- （可选）覆盖全局 add 推理策略；不设置则沿用 provider 全局 ----
        "infer_default": True,
    },
}

