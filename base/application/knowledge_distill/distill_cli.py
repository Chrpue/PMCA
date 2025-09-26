"""
PMCA 新版知识蒸馏脚本 (最终决定版)
"""

from __future__ import annotations
import argparse
import asyncio
import importlib
import json
import re
from typing import Any, Dict, List, Optional, Type
from loguru import logger

try:
    from base.runtime import PMCARuntime
    from base.configs import PMCADistillationConfig
    from core.client import LLMFactory
    from core.knowledge.factory import PMCALightRAGClient
    from core.memory.factory.mem0 import PMCAMem0LocalService
    from autogen_agentchat.messages import UserMessage
    from autogen_core.models import SystemMessage
except ImportError as exc:
    raise ImportError("PMCA 核心模块导入失败。") from exc

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.syntax import Syntax
    from rich.table import Table

    HAS_RICH = True
except ImportError:
    HAS_RICH = False


class PMCADistillationPipeline:
    def __init__(
        self, config: PMCADistillationConfig, prompts_module_path: Optional[str] = None
    ):
        self.config = config
        self.prompts_module_base = (
            prompts_module_path or "base.prompts.knowledge_distill"
        )
        self._templates: Dict[str, Dict[str, str]] = {}

    def _load_template(self) -> Dict[str, str]:
        name = self.config.template
        if name in self._templates:
            return self._templates[name]
        module_name = f"{self.prompts_module_base}.{name}"
        try:
            module = importlib.import_module(module_name)
            self._templates[name] = {
                "topic_prompt": getattr(module, "topic_prompt"),
                "distill_prompt": getattr(module, "distill_prompt"),
            }
            return self._templates[name]
        except (ModuleNotFoundError, AttributeError) as exc:
            logger.error(f"加载提示词模板 '{module_name}' 失败: {exc}")
            raise

    def _extract_json_from_response(self, raw_response: str) -> Optional[str]:
        match = re.search(
            r"```json\s*(\{.*?\})\s*```", raw_response, re.DOTALL
        ) or re.search(r"(\{.*?\})", raw_response, re.DOTALL)
        return match.group(1) if match else None

    async def _discover_topics(
        self, rag_client: PMCALightRAGClient, workspace: str, agent_name: str
    ) -> List[str]:
        logger.info(f"[{agent_name}] 步骤 1/4: 正在发现核心主题...")
        prompt = self._load_template()["topic_prompt"].format(agent_name=agent_name)
        try:
            # RAG client 是同步的，需要在线程中运行
            result = await asyncio.to_thread(
                rag_client.query, workspace, prompt, with_graph=False
            )
            if result and result.get("answer"):
                topics = [t.strip() for t in result["answer"].split(",") if t.strip()][
                    : self.config.topic_top_k
                ]
                logger.success(f"[{agent_name}] 发现 {len(topics)} 个主题: {topics}")
                return topics
        except Exception as exc:
            logger.error(f"[{agent_name}] LightRAG 主题查询失败: {exc}")
        return []

    async def _retrieve_and_distill(
        self,
        rag_client: PMCALightRAGClient,
        llm_client,
        workspace: str,
        agent_name: str,
        topics: List[str],
    ) -> Dict[str, Any]:
        if not topics:
            return {}
        logger.info(f"[{agent_name}] 步骤 2/4: 正在进行深度知识检索...")
        query_text = f"请为我提供关于以下主题的、最全面和详细的综合知识总结：{', '.join(topics)}。"
        try:
            override = {
                "top_k": self.config.retrieval_top_k,
                "chunk_top_k": self.config.chunk_top_k,
            }
            result = await asyncio.to_thread(
                rag_client.query,
                workspace,
                query_text,
                override_params=override,
                with_graph=True,
            )
            rag_answer = result.get("answer") if result else ""
            if not rag_answer:
                logger.warning(f"[{agent_name}] 深度检索未返回有效内容。")
                return {}
            logger.success(
                f"[{agent_name}] 深度检索完成，获得 {len(rag_answer)} 字符的知识。"
            )
        except Exception as exc:
            logger.error(f"[{agent_name}] LightRAG 深度检索失败: {exc}")
            return {}

        logger.info(f"[{agent_name}] 步骤 3/4: 正在使用 LLM 提炼记忆档案...")
        distill_prompt = self._load_template()["distill_prompt"].format(
            agent_name=agent_name, rag_answer=rag_answer
        )
        messages = [
            SystemMessage(content="你是一个只返回有效 JSON 的 AI 助手。"),
            UserMessage(content=distill_prompt, source="user"),
        ]
        try:
            llm_response = await llm_client.create(messages=messages)
            json_str = self._extract_json_from_response(
                getattr(llm_response, "content", "")
            )
            if not json_str:
                logger.error(f"[{agent_name}] 未能从 LLM 响应中解析出 JSON。")
                return {}
            profile = json.loads(json_str)
            logger.success(f"[{agent_name}] 成功提炼出结构化的记忆档案。")
            return profile
        except Exception as exc:
            logger.error(f"[{agent_name}] LLM 请求或 JSON 解析失败: {exc}")
            return {}

    def _build_injection_message(self, profile: Dict[str, Any]) -> str:
        if not profile:
            return ""
        parts = [
            f"**我的核心身份 (Persona):**\n{p}" for p in [profile.get("persona")] if p
        ]
        parts.extend(
            [
                f"**我必须遵守的核心原则:**\n" + "\n".join(f"- {p}" for p in principles)
                for principles in [profile.get("core_memory_principles")]
                if principles
            ]
        )
        parts.extend(
            [
                f"**我需要记住的关键经验和案例:**\n"
                + "\n".join(f"- {e}" for e in episodes)
                for episodes in [profile.get("episodic_memories")]
                if episodes
            ]
        )
        parts.extend(
            [
                f"**我需要掌握的标准操作流程:**\n"
                + "\n".join(f"- {p}" for p in procedures)
                for procedures in [profile.get("procedural_memories")]
                if procedures
            ]
        )
        if not parts:
            return ""
        return (
            "请为我植入初始记忆。这对我至关重要，请确保完全理解并存储以下所有信息。\n\n"
            + "\n\n".join(parts)
        )

    async def run_single_agent(self, agent_name: str, workspace: str) -> str:
        rag_client, llm_client = PMCALightRAGClient(), LLMFactory.client()
        topics = await self._discover_topics(rag_client, workspace, agent_name)
        profile = await self._retrieve_and_distill(
            rag_client, llm_client, workspace, agent_name, topics
        )
        injection_message = self._build_injection_message(profile)

        if self.config.inject and injection_message:
            logger.info(f"[{agent_name}] 步骤 4/4: 正在向 mem0 注入记忆...")
            try:
                # 直接调用 add_memory，它现在是安全的
                await PMCAMem0LocalService.add_memory(
                    agent_name=agent_name,
                    content=injection_message,
                    metadata={
                        "category": "seed",
                        "source": f"distillation:{self.config.template}",
                    },
                )
            except Exception as e:
                # 如果 add_memory 内部有异常，现在我们能在这里看到了
                logger.error(f"[{agent_name}] 向 mem0 注入记忆时发生明确错误: {e}")
        elif not injection_message:
            logger.warning(f"[{agent_name}] 未生成有效的注入信息，跳过注入步骤。")

        return injection_message

    async def run_multiple_agents(
        self, agent_names: List[str], workspace: str
    ) -> Dict[str, str]:
        tasks = [self.run_single_agent(name, workspace) for name in agent_names]
        results = await asyncio.gather(*tasks)
        return dict(zip(agent_names, results))


class PMCADistillationPipelineRich(PMCADistillationPipeline):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.console = Console()

    async def run_single_agent(self, agent_name: str, workspace: str) -> str:
        self.console.rule(f"[bold yellow]开始处理: {agent_name}", style="yellow")
        return await super().run_single_agent(agent_name, workspace)


def get_target_agents(agent_arg: str) -> List[str]:
    if agent_arg.lower() == "all":
        return [
            "PMCATriage",
            "PMCATeamDecision",
            "PMCAAgentsDecision",
            "PMCATeamDecisionCritic",
            "PMCAAgentsDecisionCritic",
        ]
    return [agent_arg]


async def main():
    parser = argparse.ArgumentParser(
        description="PMCA 新版知识蒸馏脚本",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--agent", "-a", required=True, help="要处理的智能体名称，或使用 'all'。"
    )
    parser.add_argument(
        "--workspace", "-w", default="app", help="LightRAG 工作区 (默认: 'app')。"
    )
    parser.add_argument(
        "--template", "-t", default="default", help="提示词模板 (默认: 'default')。"
    )
    parser.add_argument(
        "--topic-top-k", type=int, default=5, help="核心主题数量 (默认: 5)。"
    )
    parser.add_argument(
        "--retrieval-top-k", type=int, default=5, help="检索的文档数量 (默认: 5)。"
    )
    parser.add_argument(
        "--chunk-top-k", type=int, default=3, help="每个文档的 chunk 数量 (默认: 3)。"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="干跑模式，不实际写入数据。"
    )
    parser.add_argument("--rich", action="store_true", help="启用 Rich 可视化输出。")
    args = parser.parse_args()

    logger.info("正在初始化 PMCA Runtime...")
    try:
        runtime = PMCARuntime()
        await runtime.initialize()
        logger.success("PMCA Runtime 初始化成功。")
    except Exception as e:
        logger.error(f"PMCA Runtime 初始化失败: {e}")
        return

    target_agents = get_target_agents(args.agent)

    # [最终核心修复]：删除整个“预创建”/“预热”代码块，因为它是不必要的，且可能导致连接失效

    config = PMCADistillationConfig(
        template=args.template,
        topic_top_k=args.topic_top_k,
        retrieval_top_k=args.retrieval_top_k,
        chunk_top_k=args.chunk_top_k,
        inject=not args.dry_run,
    )

    pipeline_class = (
        PMCADistillationPipelineRich
        if args.rich and HAS_RICH
        else PMCADistillationPipeline
    )
    if args.rich and not HAS_RICH:
        logger.warning("请求 Rich 输出但 `rich` 未安装，将回退到标准输出。")

    pipeline = pipeline_class(config)

    try:
        logger.info(f"开始为 {len(target_agents)} 个智能体进行知识蒸馏...")
        results = await pipeline.run_multiple_agents(target_agents, args.workspace)
        logger.info("-" * 50 + "\n知识蒸馏流程全部完成。")
        for name, injection in results.items():
            status = "成功生成" if injection else "生成失败或为空"
            logger.info(f"  - {name}: {status} (长度: {len(injection)} 字符)")
    except Exception as e:
        logger.error(f"蒸馏流程中发生未捕获的异常: {e}")
    finally:
        logger.info("正在关闭 mem0 服务以确保数据持久化...")
        await PMCAMem0LocalService.shutdown()
        logger.success("mem0 服务已成功关闭。")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("\n用户中断了操作。")

