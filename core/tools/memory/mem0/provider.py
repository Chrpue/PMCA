from __future__ import annotations

import copy
import threading
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

import requests
from autogen_core.tools import FunctionTool
from loguru import logger
from mem0 import Memory

from base.configs import mem0config
from .policy import PMCAMem0OpsPolicy
from core.tools.factory import PMCAToolProvider

try:
    import jsonschema
    from .contract import CONTRACT_OF_MASTEROFMEMORY
except Exception:
    jsonschema = None
    from contract import CONTRACT_OF_MASTEROFMEMORY


def _snake(name: str) -> str:
    import re

    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


DEFAULT_CONTRACTS: Dict[str, Dict[str, Any]] = {
    CONTRACT_OF_MASTEROFMEMORY["name"]: CONTRACT_OF_MASTEROFMEMORY["memory_contract"],
}


class PMCAMem0ToolsProvider(PMCAToolProvider):
    """
    本地 mem0 工具提供器：按“每智能体一集合”，并在写入时套用**智能体契约**（schema+vocab）。
    - 工具方法名/对外行为按你现有实现，未改。
    """

    # ======== 契约注册（避免 for_assistant 签名变动） ========
    _contract_by_assistant: Dict[str, Dict[str, Any]] = {}

    def register_contract(self, assistant_name: str, contract: Dict[str, Any]) -> None:
        """
        由工厂在创建智能体前调用：为某个智能体注册 memory_contract。
        """
        if not isinstance(contract, dict):
            raise ValueError("memory_contract 必须是 dict")
        self._contract_by_assistant[assistant_name] = contract

    # ======== 内部缓存/锁 ========
    _mem_cache: Dict[str, Tuple[Memory, str]] = {}
    _lock = threading.Lock()

    def _ensure_contract_loaded(self, assistant_name: str) -> None:
        """
        若调用者智能体尚未注册契约，则尝试从 DEFAULT_CONTRACTS 自动注册。
        这样就不需要在 assistant_factory 中显式传入契约，避免循环依赖/侵入。
        """
        if assistant_name in self._contract_by_assistant:
            return
        if assistant_name in DEFAULT_CONTRACTS:
            self._contract_by_assistant[assistant_name] = DEFAULT_CONTRACTS[
                assistant_name
            ]

    # ======== Qdrant 基础 ========
    @staticmethod
    def _qdrant_base(cfg: Dict[str, Any]) -> str:
        vs = cfg.get("vector_store", {}) or {}
        vsc = vs.get("config", {}) or {}
        host = vsc.get("host", "localhost")
        port = int(vsc.get("port", 6333))
        scheme = vsc.get("scheme", "http")
        return f"{scheme}://{host}:{port}"

    @classmethod
    def _qdrant_collection_exists(cls, name: str, cfg: Dict[str, Any]) -> bool:
        base = cls._qdrant_base(cfg)
        try:
            r = requests.get(
                f"{base}/collections/{name}/exists",
                timeout=PMCAMem0OpsPolicy.HTTP_TIMEOUT_S,
            )
            if r.status_code == 200 and (r.json().get("result") or {}).get("exists"):
                return True
        except Exception:
            pass
        try:
            r = requests.get(
                f"{base}/collections/{name}", timeout=PMCAMem0OpsPolicy.HTTP_TIMEOUT_S
            )
            return r.status_code == 200
        except Exception:
            return False

    @classmethod
    def _qdrant_create_collection(cls, name: str, cfg: Dict[str, Any]) -> None:
        base = cls._qdrant_base(cfg)
        dims = (
            (cfg.get("embedder", {}) or {})
            .get("config", {})
            .get("embedding_dims", None)
        )
        if not isinstance(dims, int) or dims <= 0:
            raise ValueError("embedding_dims 未设置，无法创建集合。")
        body = {
            "vectors": {
                "size": dims,
                "distance": PMCAMem0OpsPolicy.DEFAULT_QDRANT_DISTANCE,
            }
        }
        r = requests.put(
            f"{base}/collections/{name}",
            json=body,
            timeout=PMCAMem0OpsPolicy.HTTP_TIMEOUT_S,
        )
        if r.status_code not in (200, 201):
            raise RuntimeError(
                f"Qdrant create collection failed: {r.status_code}, {r.text}"
            )

    @classmethod
    def _qdrant_list_payload_indexes(
        cls, name: str, cfg: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        读取 collection info，从 payload_schema 中判断已建索引的字段。:contentReference[oaicite:4]{index=4}
        """
        base = cls._qdrant_base(cfg)
        r = requests.get(
            f"{base}/collections/{name}", timeout=PMCAMem0OpsPolicy.HTTP_TIMEOUT_S
        )
        r.raise_for_status()
        return r.json().get("result", {}).get("payload_schema", {}) or {}

    @classmethod
    def _qdrant_create_payload_index(
        cls, name: str, field: str, field_schema: str, cfg: Dict[str, Any]
    ) -> None:
        """
        为指定字段创建 payload 索引。官方 API: POST /collections/{collection}/index。:contentReference[oaicite:5]{index=5}
        field_schema 可选：'keyword'（分类/枚举）、'integer'、'float'、'bool'、'text'（全文）
        """
        base = cls._qdrant_base(cfg)
        body = {"field_name": field, "field_schema": field_schema}
        r = requests.post(
            f"{base}/collections/{name}/index",
            json=body,
            timeout=PMCAMem0OpsPolicy.HTTP_TIMEOUT_S,
        )
        if r.status_code not in (200, 202):
            raise RuntimeError(
                f"Create payload index failed ({field}): {r.status_code} {r.text}"
            )

    # ======== 结果规整（与之前相同的思想） ========
    def _normalize_results(self, res: Any) -> List[Dict[str, Any]]:
        if isinstance(res, dict) and isinstance(res.get("results"), list):
            seq = res["results"]
        elif isinstance(res, list):
            seq = res
        else:
            return []
        out: List[Dict[str, Any]] = []
        for x in seq:
            if isinstance(x, dict):
                out.append(x)
            elif isinstance(x, str):
                out.append({"id": x, "content": x})
        return out

    def _extract_first_id(self, res: Any) -> Optional[str]:
        if isinstance(res, list):
            for e in res:
                if isinstance(e, dict) and e.get("id"):
                    return str(e["id"])
            return None
        if isinstance(res, dict):
            if res.get("id"):
                return str(res["id"])
            results = res.get("results")
            if isinstance(results, list) and results and isinstance(results[0], dict):
                return str(results[0].get("id") or results[0].get("_id") or "")
        if isinstance(res, str):
            return res
        return None

    # ======== 契约应用：校验 + 归一（零推理） ========
    @staticmethod
    def _nfkc(s: str) -> str:
        return unicodedata.normalize("NFKC", s).strip()

    def _apply_contract_on_metadata(
        self, assistant_name: str, md: Optional[Dict[str, Any]]
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[bool]]:
        """
        根据注册的 memory_contract 对 metadata 做：
        - JSON Schema 校验（仅结构与必填，需安装 jsonschema）；
        - 轻量归一：NFKC、去多空格、别名映射到 allowed 集合；
        - 仅保留 schema 声明的字段；其他丢弃；
        - 返回 (规范后的 metadata, 错误信息, infer_override)
        """
        self._ensure_contract_loaded(assistant_name)
        contract = self._contract_by_assistant.get(assistant_name) or {}
        schema = contract.get("schema")
        vocab = contract.get("vocab") or {}
        infer_override = contract.get("infer_default")

        if not isinstance(md, dict):
            return (None, None, infer_override)

        # 1) 结构校验（如无 jsonschema 则仅做字段裁剪）
        data = {}
        allowed_fields = set()
        required_fields = set()
        if isinstance(schema, dict):
            props = schema.get("properties") or {}
            allowed_fields = set(props.keys())
            required_fields = set(schema.get("required") or [])
            # 先裁剪到声明字段集合
            for k in allowed_fields:
                if k in md:
                    data[k] = md[k]

            # === 预归一：先把 type/subject 变成契约能接受的形态，再进 JSON Schema ===
            # a) type：中文/别名 -> 英文枚举（observation|rule|procedure|faq|note）
            if "type" in data and isinstance(data["type"], str):
                t = self._nfkc(data["type"])
                type_vocab = vocab.get("type") or {}
                aliases = type_vocab.get("aliases") or {}
                if t in aliases:
                    data["type"] = aliases[t]

            # b) subject：若是 str 则包成 list；若缺失则兜底为 ["general"]（通用、无领域绑定）
            if "subject" not in data or not data.get("subject"):
                data["subject"] = ["general"]
            elif isinstance(data["subject"], str):
                data["subject"] = [data["subject"]]

            if jsonschema is not None:
                try:
                    jsonschema.validate(
                        instance=data, schema=schema
                    )  # additionalProperties:false 生效
                except Exception as ve:
                    return (None, f"metadata 不符合 schema: {ve}", infer_override)
        else:
            # 无 schema 时，仅复制
            data = md.copy()

        # 2) 归一：NFKC + 别名映射 + allowed 集合校验
        def _canon_field(field: str, value: Any) -> Optional[str]:
            if value is None:
                return None
            s = self._nfkc(str(value))
            v = vocab.get(field) or {}
            aliases = v.get("aliases") or {}
            if s in aliases:
                s = aliases[s]
            allowed = set(v.get("allowed") or [])
            if allowed and s not in allowed:
                # 不在允许集合，回退为“其他”
                raise ValueError(f"{field} 值不在允许集合: {s}")
            return s

        # subject: 将每个条目做 slug 化（小写 + 仅保留 a-z0-9_-），并应用别名映射
        def _slugify_tag(x: str) -> str:
            import re

            s = self._nfkc(x).lower()
            s = re.sub(r"[^a-z0-9_-]", "-", s)
            s = re.sub(r"-{2,}", "-", s).strip("-")
            return s[:63] if s else s

        result: Dict[str, Any] = {}
        for k, v in data.items():
            if k == "type":
                try:
                    result[k] = _canon_field("type", v)
                except ValueError as ve:
                    return (None, f"metadata 不符合 schema: {ve}", infer_override)
            elif k == "subject":
                arr = v if isinstance(v, list) else [v]
                canon = []
                subj_aliases = (vocab.get("subject") or {}).get("aliases") or {}
                for item in arr:
                    item_s = self._nfkc(str(item))
                    if item_s in subj_aliases:
                        item_s = subj_aliases[item_s]
                    canon.append(_slugify_tag(item_s))
                # 去重并去空
                result[k] = [t for i, t in enumerate(canon) if t and t not in canon[:i]]
            else:
                # 其他字段（title/source_uri/wasGeneratedBy/wasAttributedTo/labels.*）做 NFKC
                result[k] = self._nfkc(str(v))

        if not result.get("type") or not (
            isinstance(result.get("subject"), list) and result["subject"]
        ):
            return (
                None,
                "metadata 缺少必填字段 type/subject 或 subject 非法",
                infer_override,
            )

        return (result, None, infer_override)

    def _list_with_filters(
        self, m: Memory, *, user_id: str, filters: Dict[str, Any]
    ) -> Any:
        """
        统一的“列举”入口：
        - 优先使用 get_all(user_id, filters=...)（v2 支持 / 结构清晰）；
        - 老版本不支持 filters 时退回 search("") + filters。:contentReference[oaicite:6]{index=6}
        """
        try:
            return m.get_all(user_id=user_id, filters=filters)
        except TypeError:
            return m.search(
                "",
                user_id=user_id,
                limit=PMCAMem0OpsPolicy.MAX_LIST_BATCH,
                filters=filters,
            )

    def _delete_by_scope(
        self,
        m: Memory,
        *,
        user_id: Optional[str],
        agent_id: Optional[str],
        run_id: Optional[str],
        extra_filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        统一的“按范围删除”入口：
        - 若过滤键仅包含 user_id/agent_id/run_id -> 直接走 delete_all(...)（官方支持；会 reset 集合）:contentReference[oaicite:7]{index=7}
        - 否则：列举（get_all/search 回退） -> 逐条 delete(id)
        """
        if not (
            extra_filters
            and (set(extra_filters.keys()) - {"user_id", "agent_id", "run_id"})
        ):
            if user_id or agent_id or run_id:
                res = m.delete_all(user_id=user_id, agent_id=agent_id, run_id=run_id)
                return {"ok": True, "raw": res, "mode": "delete_all"}
            return {
                "ok": False,
                "error": "缺少删除过滤条件（至少需要 user_id/agent_id/run_id 之一）。",
            }

        flt = dict(extra_filters or {})
        if user_id:
            flt["user_id"] = user_id
        if agent_id:
            flt["agent_id"] = agent_id
        if run_id:
            flt["run_id"] = run_id

        res = self._list_with_filters(
            m, user_id=user_id or flt.get("user_id", ""), filters=flt
        )
        deleted = 0
        for r in self._normalize_results(res):
            mid = r.get("id") or r.get("_id")
            if mid:
                m.delete(mid)
                deleted += 1
        return {"ok": True, "deleted": deleted, "mode": "list_then_delete"}

    # ======== Memory 实例解析（与你之前一致的单例+集合切换） ========
    @classmethod
    def _memory_for(
        cls,
        target_assistant: str,
        *,
        create_if_missing: bool = False,
        check_exists: bool = True,
    ) -> Tuple[Memory, str]:
        pair = cls._mem_cache.get(target_assistant)
        if pair:
            return pair

        collection_name = _snake(target_assistant)
        with cls._lock:
            pair = cls._mem_cache.get(target_assistant)
            if pair:
                return pair

            cfg = copy.deepcopy(mem0config.PMCAMem0LocalConfig)
            cfg.setdefault("vector_store", {}).setdefault("config", {}).update(
                collection_name=collection_name
            )

            if create_if_missing and not PMCAMem0OpsPolicy.ALLOW_AUTO_CREATE:
                raise RuntimeError(f"全局已禁用自动创建集合：{collection_name}")

            if check_exists and not cls._qdrant_collection_exists(collection_name, cfg):
                if create_if_missing:
                    cls._qdrant_create_collection(collection_name, cfg)
                else:
                    raise RuntimeError(f"目标集合未供给: {collection_name}")

            memory = Memory.from_config(config_dict=cfg)
            pair = (memory, collection_name)
            cls._mem_cache[target_assistant] = pair
            return pair

    # ======== 统一 add（保留你原有统一封装思想；此处只融合“契约”与 infer 覆盖） ========
    def _add_unified(
        self,
        m: Memory,
        *,
        content: str,
        user_id: str,
        agent_id: str,
        run_id: Optional[str],
        metadata: Optional[Dict[str, Any]],
        assistant_name: str,
    ) -> Dict[str, Any]:
        # 先套用智能体契约
        canon_md, md_err, infer_override = self._apply_contract_on_metadata(
            assistant_name, metadata
        )
        if md_err:
            return {"ok": False, "error": md_err}

        kwargs: Dict[str, Any] = {
            "user_id": user_id,
            "agent_id": agent_id,
            "run_id": run_id,
            "metadata": canon_md,
        }

        # infer 的优先级：智能体契约覆盖 > 全局策略；仅在 add 支持 infer 时传
        infer_value = (
            infer_override
            if isinstance(infer_override, bool)
            else PMCAMem0OpsPolicy.DEFAULT_ADD_INFER
        )
        if "infer" in m.add.__code__.co_varnames:
            kwargs["infer"] = infer_value

        # messages/content 的兼容（不同本地版本差异较大：只传支持的参数）
        try:
            if "messages" in m.add.__code__.co_varnames:
                res = m.add(
                    messages=[{"role": "user", "content": content}],
                    **{k: v for k, v in kwargs.items() if v is not None},
                )
            elif "content" in m.add.__code__.co_varnames:
                res = m.add(
                    content=content,  # type:ignore
                    **{k: v for k, v in kwargs.items() if v is not None},
                )
            else:
                res = m.add(
                    content, **{k: v for k, v in kwargs.items() if v is not None}
                )
        except TypeError:
            # 极端兼容：去掉 infer/metadata 再试
            kwargs.pop("infer", None)
            kwargs.pop("metadata", None)
            res = m.add(content, **{k: v for k, v in kwargs.items() if v is not None})

        mem_id = self._extract_first_id(res)
        if not mem_id:
            return {
                "ok": False,
                "error": "未抽取到可存的记忆；或本地版本未返回 id。可调整 infer 策略或升级 mem0。",
                "raw": res,
            }
        return {"ok": True, "id": mem_id, "raw": res}

    # =========================
    # 对外：为某个“调用者智能体”暴露工具集
    # =========================
    def for_assistant(self, assistant_name: str) -> List[FunctionTool]:
        """
        为指定调用者智能体生成可用的工具列表。

        约定
        ----
        - “自用”操作：目标=caller（user_id=assistant_name, agent_id=assistant_name）
        - “代办”操作：目标=target_assistant（user_id=target, agent_id=assistant_name）
        - 所有操作均落在**目标智能体绑定的 collection** 上（严格按集合切换）
        """
        tools: List[FunctionTool] = []
        self._ensure_contract_loaded(assistant_name)

        # ========== 自用：解析自己的实例 ==========
        def _self_mem() -> Tuple[Memory, str]:
            return self._memory_for(
                assistant_name, create_if_missing=False, check_exists=True
            )

        def _target_mem(target_assistant: str) -> Tuple[Memory, str]:
            return self._memory_for(
                target_assistant, create_if_missing=False, check_exists=True
            )

        # ---------------------- 自用：写入 ----------------------
        def add_memory_for_self(
            content: str,
            metadata: Optional[Dict[str, Any]] = None,
            run_id: Optional[str] = None,
        ) -> Dict[str, Any]:
            try:
                m, _ = _self_mem()
                return self._add_unified(
                    m,
                    content=content,
                    user_id=assistant_name,
                    agent_id=assistant_name,
                    run_id=run_id,
                    metadata=metadata,
                    assistant_name=assistant_name,
                )
            except Exception as e:
                logger.exception("add_memory_for_self failed")
                return {"ok": False, "error": str(e)}

        tools.append(
            FunctionTool(
                name="add_memory_for_self",
                description="[自身] 为自己写入记忆（user_id=自己，agent_id=自己）",
                func=add_memory_for_self,
            )
        )

        # ---------------------- 自用：检索 ----------------------
        def search_memories_for_self(
            query: str,
            limit: int = 10,
            threshold: Optional[float] = None,
            run_id: Optional[str] = None,
            only_written_by_me: bool = False,
            filters: Optional[Dict[str, Any]] = None,
        ) -> Dict[str, Any]:
            """
            [自用] 在“自己的记忆”中进行语义检索。

            参数
            ----
            query : str
                检索查询文本。
            limit : int
                返回条数上限。
            threshold : float, optional
                相似度阈值（具体含义视底层实现）。
            run_id : str, optional
                若提供，则仅匹配指定批次。
            only_written_by_me : bool
                若为 True，仅返回 agent_id=自己 的结果（排除他人代写）。
            filters : dict, optional
                其他过滤条件（与 user_id/agent_id/run_id 组合）。

            返回
            ----
            dict: { ok: bool, items: List[...], raw: Any, error?: str }
            """
            try:
                m, _ = _self_mem()
                flt = filters.copy() if isinstance(filters, dict) else {}
                flt.setdefault("user_id", assistant_name)
                if run_id:
                    flt["run_id"] = run_id
                if only_written_by_me:
                    flt["agent_id"] = assistant_name
                res = m.search(
                    query,
                    user_id=assistant_name,
                    limit=limit,
                    threshold=threshold,
                    filters=flt,
                )
                items: List[Dict[str, Any]] = []
                for r in self._normalize_results(res):
                    items.append(
                        {
                            "id": r.get("id") or r.get("_id"),
                            "content": r.get("content") or r.get("text"),
                            "metadata": r.get("metadata"),
                            "score": r.get("score"),
                            "created_at": r.get("created_at"),
                            "updated_at": r.get("updated_at"),
                            "agent_id": r.get("agent_id"),
                            "run_id": r.get("run_id"),
                        }
                    )
                return {"ok": True, "items": items, "raw": res}
            except Exception as e:
                logger.exception("search_memories_for_self failed")
                return {"ok": False, "error": str(e)}

        tools.append(
            FunctionTool(
                name="search_memories_for_self",
                description="[self] 在自己的集合中检索（支持 user_id/agent_id/run_id 等高级过滤）",
                func=search_memories_for_self,
            )
        )

        # ---------------------- 自用：读取/更新/删除 ----------------------
        def get_memory(memory_id: str) -> Dict[str, Any]:
            """
            [自用] 读取自己集合中的单条记忆。
            """
            try:
                m, _ = _self_mem()
                res = m.get(memory_id)
                item = None
                if isinstance(res, dict):
                    item = {
                        "id": res.get("id") or res.get("_id"),
                        "content": res.get("content") or res.get("text"),
                        "metadata": res.get("metadata"),
                        "created_at": res.get("created_at"),
                        "updated_at": res.get("updated_at"),
                        "agent_id": res.get("agent_id"),
                        "run_id": res.get("run_id"),
                    }
                return {"ok": True, "item": item, "raw": res}
            except Exception as e:
                logger.exception("get_memory failed")
                return {"ok": False, "error": str(e)}

        tools.append(
            FunctionTool(
                name="get_memory",
                description="[self] 读取单条记忆（自己的集合）",
                func=get_memory,
            )
        )

        def get_memory_history(memory_id: str) -> Dict[str, Any]:
            """
            [自用] 查询单条记忆的历史（修订/版本轨迹）。
            """
            try:
                m, _ = _self_mem()
                res = m.history(memory_id)
                return {"ok": True, "history": res}
            except Exception as e:
                logger.exception("get_memory_history failed")
                return {"ok": False, "error": str(e)}

        tools.append(
            FunctionTool(
                name="get_memory_history",
                description="[self] 获取记忆历史（自己的集合）",
                func=get_memory_history,
            )
        )

        def update_memory(
            memory_id: str,
            content: Optional[str] = None,
            metadata: Optional[Dict[str, Any]] = None,
        ) -> Dict[str, Any]:
            """
            [自用] 更新自己集合中的单条记忆（内容与/或元数据）。

            说明
            ----
            - mem0 版本差异：某些实现接受 `data=str`（仅内容），也接受 `data=dict`（含 content/metadata）。
            """
            try:
                m, _ = _self_mem()
                if metadata is None and content is not None:
                    data: Any = content
                else:
                    data = {}
                    if content is not None:
                        data["content"] = content
                    if metadata is not None:
                        data["metadata"] = metadata
                res = m.update(memory_id, data=data)
                return {"ok": True, "id": memory_id, "raw": res}
            except Exception as e:
                logger.exception("update_memory failed")
                return {"ok": False, "error": str(e)}

        tools.append(
            FunctionTool(
                name="update_memory",
                description="[self] 更新单条记忆（自己的集合）",
                func=update_memory,
            )
        )

        def delete_memory(memory_id: str) -> Dict[str, Any]:
            """
            [自用] 删除自己集合中的单条记忆。
            """
            try:
                m, _ = _self_mem()
                m.delete(memory_id)
                return {"ok": True, "id": memory_id}
            except Exception as e:
                logger.exception("delete_memory failed")
                return {"ok": False, "error": str(e)}

        tools.append(
            FunctionTool(
                name="delete_memory",
                description="[self] 删除单条记忆（自己的集合）",
                func=delete_memory,
            )
        )

        def get_all_memories_for_self() -> Dict[str, Any]:
            """
            [自用] 获取自己集合中的全部记忆（谨慎使用）。
            """
            try:
                m, _ = _self_mem()
                res = m.get_all(user_id=assistant_name)
                items: List[Dict[str, Any]] = []
                for r in self._normalize_results(res):
                    items.append(
                        {
                            "id": r.get("id") or r.get("_id"),
                            "content": r.get("content") or r.get("text"),
                            "metadata": r.get("metadata"),
                            "created_at": r.get("created_at"),
                            "updated_at": r.get("updated_at"),
                            "agent_id": r.get("agent_id"),
                            "run_id": r.get("run_id"),
                        }
                    )
                return {"ok": True, "items": items, "raw": res}
            except Exception as e:
                logger.exception("get_all_memories_for_self failed")
                return {"ok": False, "error": str(e)}

        tools.append(
            FunctionTool(
                name="get_all_memories_for_self",
                description="[self] 列出自己的全部记忆（可能很大）",
                func=get_all_memories_for_self,
            )
        )

        def delete_all_memories_for_self(
            confirm: bool = False,
            run_id: Optional[str] = None,
            only_written_by_me: bool = False,
        ) -> Dict[str, Any]:
            """
            [自用] 清空自己集合中的全部记忆（危险操作）。

            参数
            ----
            confirm : bool
                必须显式 True 才会执行清空。
            """
            if not confirm:
                return {"ok": False, "error": "需要 confirm=True 以执行清空操作。"}
            try:
                m, _ = _self_mem()
                agent = assistant_name if only_written_by_me else None
                return self._delete_by_scope(
                    m, user_id=assistant_name, agent_id=agent, run_id=run_id
                )
            except Exception as e:
                logger.exception("delete_all_memories_for_self failed")
                return {"ok": False, "error": str(e)}

        tools.append(
            FunctionTool(
                name="delete_all_memories_for_self",
                description="[self] 清空自己的全部记忆（危险，需 confirm=True）",
                func=delete_all_memories_for_self,
            )
        )

        def get_memory_stats_for_self() -> Dict[str, Any]:
            """
            [自用] 统计信息（简版：条数）。可按需扩展为索引健康、最近写入时间等。
            """
            try:
                m, collection = _self_mem()
                res = m.get_all(user_id=assistant_name)
                cnt = len(self._normalize_results(res))
                return {
                    "ok": True,
                    "stats": {
                        "assistant_name": assistant_name,
                        "collection": collection,
                        "total_memories": cnt,
                    },
                }
            except Exception as e:
                logger.exception("get_memory_stats_for_self failed")
                return {"ok": False, "error": str(e)}

        tools.append(
            FunctionTool(
                name="get_memory_stats_for_self",
                description="[self] 获取记忆统计（条数）",
                func=get_memory_stats_for_self,
            )
        )

        # ---------------------- 代办：目标集合切换 ----------------------
        def add_memory_for_other(
            target_assistant: str,
            content: str,
            metadata: Optional[Dict[str, Any]] = None,
            run_id: Optional[str] = None,
        ) -> Dict[str, Any]:
            try:
                m, _ = _target_mem(target_assistant)
                contract_holder = (
                    target_assistant
                    if PMCAMem0OpsPolicy.CONTRACT_SCOPE == "target"
                    else assistant_name
                )
                return self._add_unified(
                    m,
                    content=content,
                    user_id=target_assistant,
                    agent_id=assistant_name,
                    run_id=run_id,
                    metadata=metadata,
                    assistant_name=contract_holder,
                )
            except Exception as e:
                logger.exception("add_memory_for_other failed")
                return {"ok": False, "error": str(e)}

        tools.append(
            FunctionTool(
                name="add_memory_for_other",
                description="[other] 为目标智能体写入记忆（user_id=目标，agent_id=自己）",
                func=add_memory_for_other,
            )
        )

        def search_memories_for_other(
            target_assistant: str,
            query: str,
            limit: int = 10,
            threshold: Optional[float] = None,
            run_id: Optional[str] = None,
            only_written_by_me: bool = False,
            filters: Optional[Dict[str, Any]] = None,
        ) -> Dict[str, Any]:
            """
            [代办] 在“目标智能体”的集合中检索。
            """
            try:
                m, _ = _target_mem(target_assistant)
                flt = filters.copy() if isinstance(filters, dict) else {}
                flt.setdefault("user_id", target_assistant)
                if run_id:
                    flt["run_id"] = run_id
                if only_written_by_me:
                    flt["agent_id"] = assistant_name
                res = m.search(
                    query,
                    user_id=target_assistant,
                    limit=limit,
                    threshold=threshold,
                    filters=flt,
                )
                items: List[Dict[str, Any]] = []
                for r in self._normalize_results(res):
                    items.append(
                        {
                            "id": r.get("id") or r.get("_id"),
                            "content": r.get("content") or r.get("text"),
                            "metadata": r.get("metadata"),
                            "score": r.get("score"),
                            "created_at": r.get("created_at"),
                            "updated_at": r.get("updated_at"),
                            "agent_id": r.get("agent_id"),
                            "run_id": r.get("run_id"),
                        }
                    )
                return {"ok": True, "items": items, "raw": res}
            except Exception as e:
                logger.exception("search_memories_for_other failed")
                return {"ok": False, "error": str(e)}

        tools.append(
            FunctionTool(
                name="search_memories_for_other",
                description="[other] 在目标智能体集合中检索（可按 run_id/agent_id 过滤）",
                func=search_memories_for_other,
            )
        )

        def update_memory_for_other(
            target_assistant: str,
            memory_id: str,
            content: Optional[str] = None,
            metadata: Optional[Dict[str, Any]] = None,
        ) -> Dict[str, Any]:
            """
            [代办] 更新目标智能体集合中的单条记忆。
            """
            try:
                m, _ = _target_mem(target_assistant)
                if metadata is None and content is not None:
                    data: Any = content
                else:
                    data = {}
                    if content is not None:
                        data["content"] = content
                    if metadata is not None:
                        data["metadata"] = metadata
                res = m.update(memory_id, data=data)
                return {"ok": True, "id": memory_id, "raw": res}
            except Exception as e:
                logger.exception("update_memory_for_other failed")
                return {"ok": False, "error": str(e)}

        tools.append(
            FunctionTool(
                name="update_memory_for_other",
                description="[other] 更新目标智能体的记忆",
                func=update_memory_for_other,
            )
        )

        def delete_memory_for_other(
            target_assistant: str, memory_id: str
        ) -> Dict[str, Any]:
            """
            [代办] 删除目标智能体集合中的单条记忆。
            """
            try:
                m, _ = _target_mem(target_assistant)
                m.delete(memory_id)
                return {"ok": True, "id": memory_id}
            except Exception as e:
                logger.exception("delete_memory_for_other failed")
                return {"ok": False, "error": str(e)}

        tools.append(
            FunctionTool(
                name="delete_memory_for_other",
                description="[other] 删除目标智能体的单条记忆",
                func=delete_memory_for_other,
            )
        )

        def delete_memories_for_other(
            target_assistant: str,
            run_id: Optional[str] = None,
            filters: Optional[Dict[str, Any]] = None,
            confirm: bool = False,
            only_written_by_me: bool = False,
        ) -> Dict[str, Any]:
            """
            [代办] 精确删除目标智能体的记忆（推荐：按 run_id / filters 组合）。
            """
            if not confirm:
                return {"ok": False, "error": "需要 confirm=True 以执行删除操作。"}
            try:
                m, _ = _target_mem(target_assistant)
                agent = (
                    assistant_name
                    if only_written_by_me
                    else (filters or {}).get("agent_id")
                )
                return self._delete_by_scope(
                    m,
                    user_id=target_assistant,
                    agent_id=agent,
                    run_id=run_id,
                    extra_filters=filters,
                )
            except Exception as e:
                logger.exception("delete_memories_for_other failed")
                return {"ok": False, "error": str(e)}

        tools.append(
            FunctionTool(
                name="delete_memories_for_other",
                description="[other] 按过滤精确删除目标智能体的记忆（需 confirm=True）",
                func=delete_memories_for_other,
            )
        )

        # ---------------------- 管理：供给与巡检 ----------------------
        def provision_assistant(target_assistant: str) -> Dict[str, Any]:
            """
            [管理] 供给目标集合：若不存在则创建；并按智能体契约的 index_fields 建立 payload 索引。
            """

            self._ensure_contract_loaded(target_assistant)
            try:
                memory, collection = self._memory_for(
                    target_assistant, create_if_missing=True, check_exists=True
                )
                # 按契约建索引
                contract = self._contract_by_assistant.get(target_assistant) or {}
                index_fields: List[str] = list(contract.get("index_fields") or [])
                if index_fields:
                    cfg = copy.deepcopy(mem0config.PMCAMem0LocalConfig)
                    cfg.setdefault("vector_store", {}).setdefault("config", {}).update(
                        collection_name=collection
                    )
                    existing = self._qdrant_list_payload_indexes(
                        collection, cfg
                    )  # payload_schema 可见索引字段 :contentReference[oaicite:6]{index=6}
                    for f in index_fields:
                        if f in existing:
                            continue
                        # 简化策略：字符串字段用 keyword；如果是 run_id 这类标识也适合 keyword
                        field_schema = "text" if f == "title" else "keyword"
                        self._qdrant_create_payload_index(
                            collection, f, field_schema, cfg
                        )

                return {"ok": True, "collection": collection, "indexed": index_fields}
            except Exception as e:
                logger.exception("provision_assistant failed")
                return {"ok": False, "error": str(e)}

        tools.append(
            FunctionTool(
                name="provision_assistant",
                description="[admin] 供给目标智能体集合（显式创建、预热并缓存）",
                func=provision_assistant,
            )
        )

        def list_mem_collections() -> Dict[str, Any]:
            """
            [管理] 列出当前 Qdrant 实例中的所有集合（巡检/对账用）。

            返回
            ----
            dict: { ok, collections: List[str], raw: Any, error? }
            """
            try:
                cfg = copy.deepcopy(mem0config.PMCAMem0LocalConfig)
                base = self._qdrant_base(cfg)
                r = requests.get(
                    f"{base}/collections", timeout=PMCAMem0OpsPolicy.HTTP_TIMEOUT_S
                )
                if r.status_code != 200:
                    return {"ok": False, "error": f"HTTP {r.status_code}: {r.text}"}
                data = r.json()
                cols = [
                    c["name"]
                    for c in (data.get("result", {}).get("collections") or [])
                    if "name" in c
                ]
                return {"ok": True, "collections": cols, "raw": data}
            except Exception as e:
                logger.exception("list_mem_collections failed")
                return {"ok": False, "error": str(e)}

        tools.append(
            FunctionTool(
                name="list_mem_collections",
                description="[admin] 列出 Qdrant 中的全部集合（巡检）",
                func=list_mem_collections,
            )
        )

        return tools
