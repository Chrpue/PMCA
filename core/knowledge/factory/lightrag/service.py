import os
import json
import re
import requests
from loguru import logger
from copy import deepcopy
from typing import Dict, Any, Optional, List
from threading import Lock
from urllib.parse import urljoin

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    print("dotenv库未安装，将直接从系统环境变量读取。")


class PMCALightRAGClient:
    """
    一个线程安全的单例客户端，作为服务编排引擎。
    它通过组合调用 /query 和 /graphs 接口，为智能体提供丰富的结构化上下文。
    """

    _instance = None
    _lock = Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(PMCALightRAGClient, cls).__new__(
                        cls, *args, **kwargs
                    )
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            with self._lock:
                if not hasattr(self, "_initialized"):
                    self._servers: Dict[str, Dict[str, str]] = {}
                    self._base_params: Dict[str, Any] = self._get_base_params()
                    self._discover_servers()
                    self._initialized = True

    def _discover_servers(self):
        prefix = "LIGHTRAG_SERVER_"
        for key, value in os.environ.items():
            if key.startswith(prefix):
                instance_name = key[len(prefix) :].lower()
                base_url = value.strip()
                self._servers[instance_name] = {
                    "query": urljoin(base_url, "/query"),
                    "graphs": urljoin(base_url, "/graphs"),
                }

    def _get_base_params(self) -> Dict[str, Any]:
        """通用的基础查询参数模板"""

        return {
            "mode": "mix",
            "response_type": "Multiple Paragraphs",
            "top_k": 10,
            "chunk_top_k": 5,
            "enable_rerank": False,
            "conversation_history": [],
            "user_prompt": None,
        }

    def get_servers(self) -> List[str]:
        return list(self._servers.keys())

    def get_graph_for_label(
        self, instance_name: str, label: str, max_depth: int = 2, max_nodes: int = 50
    ) -> Optional[Dict]:
        instance_name = instance_name.lower()
        if instance_name not in self._servers:
            raise ValueError(f"错误：未找到名为 '{instance_name}' 的LightRAG实例。")
        endpoint = self._servers[instance_name]["graphs"]
        params = {
            "label": label,
            "max_depth": max_depth,
            "max_nodes": max_nodes,
        }
        headers = {"accept": "application/json"}

        try:
            response = requests.get(
                endpoint, headers=headers, params=params, timeout=60
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"调用LightRAG /graphs 接口失败: {e}")
            return None

    def _parse_references(self, text: str) -> Dict:
        answer_text = text
        references_list = []
        ref_match = re.search(
            r"\n\s*(?:##\s*)?(?:References:|参考依据)", text, re.IGNORECASE
        )
        if ref_match:
            answer_text = text[: ref_match.start()].strip()
            references_block = text[ref_match.end() :].strip()
            for line in references_block.split("\n"):
                line = line.strip()
                if not line:
                    continue
                ref_type = (
                    "DocumentChunk"
                    if "[DC]" in line
                    else "KnowledgeGraph"
                    if "[KG]" in line
                    else "unknown"
                )
                content = re.sub(r"^\d+\.\s*|\[(KG|DC)\]\s*", "", line).strip()
                references_list.append({"type": ref_type, "source": content})
        return {"answer": answer_text, "references": references_list}

    def query(
        self,
        instance_name: str,
        query_text: str,
        override_params: Optional[Dict[str, Any]] = None,
        with_graph: bool = True,  # <--- 新增的控制开关
    ) -> Optional[Dict]:
        """
        执行一个增强查询。

        Args:
            instance_name (str): 要查询的服务实例名称。
            query_text (str): 您要提出的问题。
            override_params (dict, optional): 用于覆盖基础查询参数的字典。
            with_graph (bool, optional): 是否在查询后，额外调用/graphs接口来检索知识图谱。默认为True。
        """

        instance_name = instance_name.lower()
        if instance_name not in self._servers:
            raise ValueError(f"错误: 未找到名为 '{instance_name}' 的 LightRAG 实例。")
        query_endpoint = self._servers[instance_name]["query"]
        final_params = deepcopy(self._base_params)
        if override_params:
            final_params.update(override_params)
        payload = {"query": query_text, **final_params}
        headers = {"Content-Type": "application/json", "accept": "application/json"}

        try:
            response = requests.post(
                query_endpoint, headers=headers, json=payload, timeout=300
            )
            response.raise_for_status()
            query_result = response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"索引知识失败: {e}")
            return None

        parsed_result = self._parse_references(query_result.get("response", ""))
        final_answer = parsed_result["answer"]
        references = parsed_result["references"]

        subgraph = None

        if with_graph:
            core_entity_label = None
            for ref in references:
                if ref["type"] == "KnowledgeGraph":
                    match = re.search(r"\((.*?)(?:、|实体描述)", ref["source"])
                    if match:
                        core_entity_label = match.group(1).strip()
                        break

            if core_entity_label:
                subgraph = self.get_graph_for_label(instance_name, core_entity_label)

        return {
            "answer": final_answer,
            "references": references,
            "retrieved_subgraph": subgraph,
        }


if __name__ == "__main__":
    client = PMCALightRAGClient()
    question = "一级节流后压力异常如何处理？"

    logger.info("默认检索模式(知识图谱)...")
    full_result = client.query("app", question)
    if full_result:
        logger.info(json.dumps(full_result, indent=2, ensure_ascii=False))

    logger.info("纯文本检索模式...")
    text_only_result = client.query("app", question, with_graph=False)
    if text_only_result:
        logger.info(json.dumps(text_only_result, indent=2, ensure_ascii=False))

    logger.info("图检索模式(自定义提示词)...")
    custom_prompt_result = client.query(
        "app",
        question,
        override_params={
            "user_prompt": "你是一名经验丰富的油田现场工程师。请根据上下文，以清晰的步骤列表形式，告诉一位新手如何处理这个问题。语气要沉稳、专业。"
        },
    )
    if custom_prompt_result:
        logger.info(json.dumps(custom_prompt_result, indent=2, ensure_ascii=False))
