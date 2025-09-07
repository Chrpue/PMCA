import os
import sys
import argparse
import yaml
import json
import re
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional

from loguru import logger
from dotenv import load_dotenv
from tqdm import tqdm

# --- 动态添加项目根目录到Python路径 ---
try:
    # 假定此脚本位于 project_root/scripts/knowledge/ 目录下
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from core.knowledge.factory import PMCALightRAGClient
    from core.memory.factory import PMCAMirixMemoryManager
    from client import LLMFactory, ProviderType, DutyType
    from autogen_agentchat.messages import UserMessage
    from autogen_core.models import SystemMessage
except ImportError as e:
    print(
        f"Error: 无法导入项目模块。请确保此脚本位于您项目根目录的 'scripts/knowledge' 子目录下。"
    )
    print(f"Details: {e}")
    sys.exit(1)


# --- (setup_logger 和 extract_json_from_response 函数保持不变) ---
def setup_logger():
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    )


def extract_json_from_response(raw_response: str) -> Optional[str]:
    match = re.search(r"```json\s*(\{.*?\})\s*```", raw_response, re.DOTALL)
    if match:
        return match.group(1)
    match = re.search(r"(\{.*?\})", raw_response, re.DOTALL)
    if match:
        return match.group(1)
    return None


class AdvancedKnowledgeDistiller:
    # --- (init, discover_topics_for_agent, distill_memory_profile 保持不变) ---
    def __init__(self, workspace: str = "app"):
        self.workspace = workspace
        self.local_knowledge_dir = (
            project_root / "documents" / self.workspace / "base_knowledge"
        )
        logger.info("Initializing clients...")
        self.lightrag_client = PMCALightRAGClient()
        self.mirix_manager = None
        self.llm_client = LLMFactory.client(ProviderType.DEEPSEEK, DutyType.BASE)
        logger.success("Clients initialized successfully.")

    def _ensure_mirix_manager(self):
        if self.mirix_manager is None:
            logger.info("Initializing Mirix Memory Manager...")
            self.mirix_manager = PMCAMirixMemoryManager()
            self.mirix_manager.client.list_users()
            logger.success("Mirix Memory Manager initialized.")

    async def discover_topics_for_agent(self, agent_name: str) -> List[str]:
        logger.info(f"Phase 1: Discovering topics for '{agent_name}' from LightRAG...")
        meta_query = f"基于你拥有的全部知识，请列出与 '{agent_name}' 智能体的核心职责、决策策略和工作流最相关的核心主题关键词。请只返回关键词列表，用逗号分隔。"
        rag_response = self.lightrag_client.query(
            self.workspace, meta_query, with_graph=False
        )
        if not rag_response or not rag_response.get("answer"):
            logger.error("Failed to discover topics from LightRAG.")
            return []
        topics = [
            topic.strip()
            for topic in rag_response["answer"].split(",")
            if topic.strip()
        ]
        logger.success(f"Discovered {len(topics)} topics: {topics}")
        return topics

    async def distill_memory_profile(
        self, agent_name: str, topics: List[str]
    ) -> Dict[str, Any]:
        if not topics:
            return {}
        logger.info(
            f"Phase 2: Deep-diving into {len(topics)} topics and distilling memory profile..."
        )
        deep_dive_query = f"请为我提供关于以下主题的、最全面和详细的综合知识总结：{', '.join(topics)}。请整合所有相关的原则、策略、案例和工作流程。"
        rag_response = self.lightrag_client.query(
            self.workspace, deep_dive_query, with_graph=True
        )
        if not rag_response or not rag_response.get("answer"):
            logger.error("Failed to get a deep-dive response from LightRAG.")
            return {}
        distill_prompt = f"""
        你是一位顶级的认知架构师。你的任务是为名为 '{agent_name}' 的AI智能体，根据下方由LightRAG提供的深度知识，生成一个结构化的JSON记忆档案。
        这个JSON档案必须包含以下四个键：'persona', 'core_memory_principles', 'episodic_memories', 'procedural_memories'。

        1.  `persona`: 提炼一句（不超过50字）关于该智能体核心身份、使命和性格的第一人称描述。
        2.  `core_memory_principles`: 提炼出3-5条该智能体必须遵守的、永恒不变的核心原则或真理。这是一个字符串列表。
        3.  `episodic_memories`: 将知识中的具体案例或场景，转化为1-3条“我记得一个经验/案例...”形式的第一人称情景记忆。这是一个字符串列表。
        4.  `procedural_memories`: 将知识中的工作流程，提炼成1-2条“当处理...任务时，我的标准流程是：...”形式的第一人称程序性记忆。这是一个字符串列表。

        如果某个类型的记忆在提供的知识中不适用或无法提炼，请返回一个空列表 `[]`。
        请严格按照JSON格式输出，不要包含任何额外的解释或Markdown标记。

        [LightRAG 提供的深度知识]
        {rag_response["answer"]}
        """
        messages = [
            SystemMessage(
                content="You are a helpful AI assistant that only responds with valid JSON.",
            ),
            UserMessage(content=distill_prompt, source="memory_architect"),
        ]

        logger.info(f"Distilling memory profile for '{agent_name}' using LLM...")
        llm_response = await self.llm_client.create(messages=messages)

        raw_content = llm_response.content if hasattr(llm_response, "content") else ""
        clean_json_str = extract_json_from_response(raw_content)

        if not clean_json_str:
            logger.error(
                f"Could not extract a valid JSON object from the LLM response. Response was:\n{raw_content}"
            )
            return {}

        try:
            memory_profile = json.loads(clean_json_str)
            logger.success("Successfully distilled a structured memory profile.")
            return memory_profile
        except json.JSONDecodeError:
            logger.error(
                f"LLM did not return a valid JSON even after cleaning. Cleaned string was:\n{clean_json_str}"
            )
            return {}

    async def seed_agent_memory(
        self, agent_name: str, memory_profile: Dict[str, Any], dry_run: bool = False
    ):
        if not memory_profile:
            logger.warning(
                f"Memory profile for '{agent_name}' is empty. Skipping seeding."
            )
            return

        # --- **核心修复：将所有记忆打包成一个大的注入指令** ---
        full_injection_message = f"请为我植入初始记忆。这对我至关重要，请确保完全理解并存储以下所有信息。\n\n"

        if memory_profile.get("persona"):
            full_injection_message += (
                f"**我的核心身份 (Persona):**\n{memory_profile['persona']}\n\n"
            )

        if memory_profile.get("core_memory_principles"):
            principles = "\n".join(
                [f"- {p}" for p in memory_profile["core_memory_principles"]]
            )
            full_injection_message += f"**我必须遵守的核心原则:**\n{principles}\n\n"

        if memory_profile.get("episodic_memories"):
            episodes = "\n".join(
                [f"- {e}" for e in memory_profile["episodic_memories"]]
            )
            full_injection_message += f"**我需要记住的关键经验和案例:**\n{episodes}\n\n"

        if memory_profile.get("procedural_memories"):
            procedures = "\n".join(
                [f"- {p}" for p in memory_profile["procedural_memories"]]
            )
            full_injection_message += f"**我需要掌握的标准操作流程:**\n{procedures}\n"

        if len(full_injection_message) < 150:  # 检查是否有有效内容
            logger.warning(
                f"No valid memories distilled for '{agent_name}'. Nothing to seed."
            )
            return

        if dry_run:
            logger.info(f"--- [Dry Run] Memory Injection Plan for {agent_name} ---")
            print(f"\n>>>>>> Agent: {agent_name} <<<<<<")
            print(f"--- Full Memory Injection Payload ---")
            print(full_injection_message)
            print("-" * 35)
            logger.info("--- [Dry Run] Completed. No data was written to Mirix. ---")
            return

        self._ensure_mirix_manager()

        target_user_id = self.mirix_manager.agent_to_user_id.get(agent_name)
        if not target_user_id:
            logger.error(
                f"Could not find user_id for agent '{agent_name}'. Cannot seed memory."
            )
            return

        logger.info(
            f"Phase 3: Seeding single memory package into Mirix for '{agent_name}' (User ID: {target_user_id})..."
        )

        # **通过一次调用，注入所有记忆**
        response = await asyncio.to_thread(
            self.mirix_manager.remember, agent_name, full_injection_message
        )

        if response:
            logger.success(
                f"Memory package successfully sent to Mirix for '{agent_name}'."
            )
        else:
            logger.error(f"Failed to inject memory package for {agent_name}.")


async def main():
    # ... (main 函数保持不变) ...
    DECISION_AGENTS = [
        "PMCATeamDecision",
        "PMCAAgentsDecision",
        "PMCATeamDecisionCritic",
        "PMCAAgentsDecisionCritic",
    ]
    parser = argparse.ArgumentParser(
        description="Advanced tool to distill and seed multi-faceted memories for agents.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-a",
        "--agent",
        type=str,
        required=True,
        help=f"Agent name to seed. Use 'all' for all core decision agents:\n{', '.join(DECISION_AGENTS)}",
    )
    parser.add_argument(
        "-w",
        "--workspace",
        type=str,
        default="app",
        help="Target LightRAG workspace. Default: 'app'.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the distilled memory profile as JSON without writing to Mirix.",
    )
    args = parser.parse_args()

    load_dotenv()
    distiller = AdvancedKnowledgeDistiller(workspace=args.workspace)

    target_agents = DECISION_AGENTS if args.agent.lower() == "all" else [args.agent]

    if args.agent.lower() == "all":
        logger.info("Processing all core decision agents...")

    for agent_name in target_agents:
        topics = await distiller.discover_topics_for_agent(agent_name)
        memory_profile = await distiller.distill_memory_profile(agent_name, topics)
        await distiller.seed_agent_memory(
            agent_name, memory_profile, dry_run=args.dry_run
        )


if __name__ == "__main__":
    setup_logger()
    asyncio.run(main())
