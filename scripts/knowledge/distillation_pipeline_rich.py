import asyncio
from core.knowledge.distill.distill_config import PMCADistillationConfig
from core.knowledge.distill.distill_pipeline_rich import PMCADistillationPipelineRich

cfg = PMCADistillationConfig(topic_top_k=8, retrieval_top_k=8, chunk_top_k=4)
pipeline = PMCADistillationPipelineRich(cfg)
agents = [
    "PMCATeamDecision",
    "PMCAAgentsDecision",
    "PMCATeamDecisionCritic",
    "PMCAAgentsDecisionCritic",
]
asyncio.run(pipeline.run_agents(agents, "app"))
