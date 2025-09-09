# base/runtime/task_workbench.py
import json
from typing import Any, List

from pydantic import BaseModel, ConfigDict
import redis.asyncio as aioredis
from autogen_core.tools import BaseTool, StaticWorkbench

from core.client import LLMFactory
from core.assistant.factory import PMCAAgentFactory


class PMCARedisTaskWorkbench:
    """
    使用 Redis 存储任务状态的工作台，实现 get_item/set_item 接口。
    """

    def __init__(self, task_id: str, redis_client: aioredis.Redis):
        self.task_id = task_id
        self.redis_client = redis_client

    async def set_item(self, key: str, value: Any):
        await self.redis_client.hset(
            f"pmca:task:{self.task_id}", key, json.dumps(value)
        )

    async def get_item(self, key: str) -> Any:
        val = await self.redis_client.hget(f"pmca:task:{self.task_id}", key)
        return json.loads(val) if val else None


class PMCATaskWorkbench(StaticWorkbench):
    """
    自定义任务工作台，组合了 Autogen 的工具和我们的状态存储。
    """

    def __init__(self, task_id: str, redis_client):
        self.task_id = task_id
        self._kv_storage = PMCARedisTaskWorkbench(task_id, redis_client)
        tools: List[BaseTool] = []
        # 初始化与任务隔离的工具，如代码执行器
        super().__init__(tools=tools)

    async def set_item(self, key: str, value: Any):
        await self._kv_storage.set_item(key, value)

    async def get_item(self, key: str):
        return await self._kv_storage.get_item(key)


class PMCATaskContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    task_id: str
    task_mission: str
    task_model_provider: str
    task_model_name: str
    task_workbench: PMCATaskWorkbench
    agent_factory: PMCAAgentFactory
    llm_factory: LLMFactory


class PMCATaskWorkbenchManager:
    """
    创建与管理任务工作台的工厂。
    """

    @staticmethod
    def create_workbench(task_id: str, redis_client):
        # 如果需要同时创建本地工作目录，也可以在此创建
        return PMCATaskWorkbench(task_id, redis_client)
