# base/application/knowledge_distill/distill_cli.py (Final, Standalone Version)

import argparse
import asyncio
import json
import re
import importlib
import time
import uuid
from typing import Any, Dict, List, Optional

from loguru import logger

# --- 核心依赖导入 ---
# 我们不再从 base.runtime 导入，而是直接导入我们需要的组件
from base.configs import PMCADistillationConfig, 
from core.client.llm_factory import LLMFactory, AbilityType
from core.knowledge.factory import PMCALightRAGClient
from core.memory.factory.mem0 import PMCAMem0LocalService
from autogen_agentchat.messages import UserMessage
from autogen_core.models import SystemMessage

# --- 手动配置 ---
# 因为我们不再使用 PMCARuntime，我们需要手动为 LLMFactory 提供配置
# 假设这是你的默认LLM配置
DEFAULT_LLM_CONFIG = {
    "provider": "deepseek",
    "config": {
        "model": "deepseek-chat",
        "api_key": .PMCAMem0LocalConfig["llm"]["config"]["api_key"],
        "base_url": .PMCAMem0LocalConfig["llm"]["config"][
            "deepseek_base_url"
        ],
    },
}


class DistillationRunner:
    """
    一个独立的、不依赖PMCARuntime的蒸馏执行器。
    """

    def __init__(self, config: PMCADistillationConfig, llm_client: Any):
        self.config = config
        self.rag_client = PMCALightRAGClient()
        self.llm_client = llm_client
        module = importlib.import_module(
            f"base.prompts.knowledge_distill.{self.config.template}"
        )
        self.templates = {
            "topic_prompt": getattr(module, "topic_prompt"),
            "distill_prompt": getattr(module, "distill_prompt"),
        }

    def _discover_topics(self, workspace: str, assistant_name: str) -> List[str]:
        logger.info(f"[{assistant_name}] (Sync) 步骤 1/3: 正在发现核心主题...")
        prompt = self.templates["topic_prompt"].format(agent_name=assistant_name)
        try:
            result = self.rag_client.query(workspace, prompt, with_graph=False)
            if result and result.get("answer"):
                topics = [t.strip() for t in result["answer"].split(",") if t.strip()][
                    : self.config.topic_top_k
                ]
                logger.success(
                    f"[{assistant_name}] (Sync) 发现 {len(topics)} 个主题: {topics}"
                )
                return topics
        except Exception as exc:
            logger.error(f"[{assistant_name}] (Sync) 主题发现失败: {exc}")
        return []

    async def _retrieve_and_distill(
        self, workspace: str, assistant_name: str, topics: List[str]
    ) -> Optional[str]:
        if not topics:
            return None
        logger.info(f"[{assistant_name}] (Sync+Async) 步骤 2/3: 正在检索和蒸馏...")

        query_text = f"请为我提供关于以下主题的、最全面和详细的综合知识总结：{', '.join(topics)}。"
        override_params = {
            "top_k": self.config.retrieval_top_k,
            "chunk_top_k": self.config.chunk_top_k,
        }
        result = self.rag_client.query(
            workspace, query_text, override_params=override_params, with_graph=True
        )
        rag_answer = result.get("answer") if result else ""
        if not rag_answer:
            logger.warning(f"[{assistant_name}] 深度检索未返回任何内容。")
            return None

        distill_prompt = self.templates["distill_prompt"].format(
            agent_name=assistant_name, rag_answer=rag_answer
        )
        messages = [
            SystemMessage(content="你是一个只返回有效JSON的AI助手。"),
            UserMessage(content=distill_prompt, source="user"),
        ]
        try:
            llm_response = await self.llm_client.create(messages=messages)
            raw_content = getattr(llm_response, "content", "")
            match = re.search(
                r"```json\s*(\{.*?\})\s*```", raw_content, re.DOTALL
            ) or re.search(r"(\{.*?\})", raw_content, re.DOTALL)
            if not match:
                return None

            profile = json.loads(match.group(1))
            parts: List[str] = []
            if p := profile.get("persona"):
                parts.append(f"**我的核心身份 (Persona):**\n{p}")
            if p := profile.get("core_memory_principles"):
                parts.append(
                    "**我必须遵守的核心原则:**\n" + "\n".join(f"- {i}" for i in p)
                )
            if p := profile.get("episodic_memories"):
                parts.append(
                    "**我需要记住的关键经验和案例:**\n" + "\n".join(f"- {i}" for i in p)
                )
            if p := profile.get("procedural_memories"):
                parts.append(
                    "**我需要掌握的标准操作流程:**\n" + "\n".join(f"- {i}" for i in p)
                )

            if not parts:
                return None
            return (
                "请为我植入初始记忆。这对我至关重要，请确保完全理解并存储以下所有信息。\n\n"
                + "\n\n".join(parts)
            )
        except Exception as e:
            logger.error(f"[{assistant_name}] LLM蒸馏失败: {e}")
            return None

    async def run_for_assistant(self, workspace: str, assistant_name: str):
        logger.info(f"========== 开始处理: {assistant_name} ==========")

        topics = self._discover_topics(workspace, assistant_name)
        injection_message = await self._retrieve_and_distill(
            workspace, assistant_name, topics
        )

        if not injection_message:
            logger.error(f"[{assistant_name}] 未能生成有效的记忆内容，流程终止。")
            return

        write_tag = f"distill-tag-{uuid.uuid4().hex[:8]}"
        final_content = f"{injection_message}\n\n[VerificationTag: {write_tag}]"

        logger.info(f"[{assistant_name}] 步骤 3/3: 正在向 mem0 注入记忆...")
        if self.config.inject:
            await PMCAMem0LocalService.add(
                assistant_name, final_content, {"tag": write_tag}
            )
            logger.success(f"[{assistant_name}] add() 方法调用完成。")
        else:
            logger.info(f"[{assistant_name}] (Dry Run模式) 跳过写入。")
            return

        logger.info(f"[{assistant_name}] 正在执行验证性查询以确保数据持久化...")
        max_wait_seconds = 45
        deadline = time.time() + max_wait_seconds
        hit_count = 0

        while time.time() < deadline:
            try:
                query_result = await PMCAMem0LocalService.query(
                    assistant_name, write_tag, limit=1
                )
                if query_result:
                    hit_count = len(query_result)
                    logger.success(
                        f"[{assistant_name}] 验证成功！在Qdrant中找到 {hit_count} 条匹配记录。"
                    )
                    break
                else:
                    logger.info(
                        f"[{assistant_name}] 查询成功但未找到记录，等待3秒后重试..."
                    )
            except Exception as e:
                logger.error(f"[{assistant_name}] 验证查询时出错: {e}")

            await asyncio.sleep(3)

        if hit_count == 0:
            logger.error(
                f"[{assistant_name}] 验证失败！在 {max_wait_seconds} 秒内未能从Qdrant中查询到注入的数据。"
            )


async def main():
    parser = argparse.ArgumentParser(description="知识蒸馏脚本 (Standalone Version)")
    # ... (参数定义保持不变) ...
    parser.add_argument("--assistant", "-a", required=True, help="智能体名称或 'all'。")
    parser.add_argument("--workspace", "-w", default="app", help="LightRAG工作区")
    parser.add_argument("--template", "-t", default="default", help="提示词模板")
    parser.add_argument("--topic-top-k", type=int, default=5)
    parser.add_argument("--retrieval-top-k", type=int, default=5)
    parser.add_argument("--chunk-top-k", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # 1. 手动初始化我们需要的服务，避免 PMCARuntime 的复杂性
    logger.info("正在手动初始化所需服务...")
    llm_client = LLMFactory.client(ability=AbilityType.DEFAULT)
    logger.success("服务初始化成功。")

    # 2. 准备资源
    distill_config = PMCADistillationConfig(
        template=args.template,
        topic_top_k=args.topic_top_k,
        retrieval_top_k=args.retrieval_top_k,
        chunk_top_k=args.chunk_top_k,
        inject=not args.dry_run,
    )
    runner = DistillationRunner(distill_config, llm_client)

    # 3. 确定目标 (这里我们需要手动提供列表，因为没有了AssistantFactory)
    if args.assistant.lower() == "all":
        # 如果需要处理所有，请在这里手动列出
        target_assistants = ["PMCATriage", "PMCADecision"]
    else:
        target_assistants = [args.assistant]

    # 4. 串行执行
    for name in target_assistants:
        await runner.run_for_assistant(args.workspace, name)

    logger.info("=" * 50)
    logger.info("所有蒸馏任务处理完毕。")


if __name__ == "__main__":
    asyncio.run(main())
