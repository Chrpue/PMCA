import json
import uuid
from typing import Any

from pydantic import BaseModel
import redis.asyncio as aioredis
from autogen_core.tools import StaticWorkbench


class PMCARedisKV:
    """
    使用 Redis 存储任务状态的工作台，实现 get_item/set_item 接口。
    """

    def __init__(self, redis: aioredis.Redis, task_id: str):
        self.redis = redis
        self.key = f"pmca:task:{task_id}"

    async def set(self, k: str, v: Any):
        await self.redis.hset(self.key, k, json.dumps(v, ensure_ascii=False))

    async def get(self, k: str) -> Any:
        v = await self.redis.hget(self.key, k)
        return json.loads(v) if v else None


class PMCATaskWorkbench(StaticWorkbench):
    """
    自定义任务工作台，组合了 Autogen 的工具和我们的状态存储。
    """

    def __init__(self, redis: aioredis.Redis, task_id: str):
        super().__init__(tools=[])
        self._kv = PMCARedisKV(redis, task_id)

    async def set_item(self, key: str, value: Any):
        await self._kv.set(key, value)

    async def get_item(self, key: str) -> Any:
        return await self._kv.get(key)


class PMCATaskContext(BaseModel):
    def __init__(
        self, task_id: str, workbench: PMCATaskWorkbench, agent_factory, llm_factory
    ):
        self.task_id = task_id
        self.workbench = workbench
        self.agent_factory = agent_factory
        self.llm_factory = llm_factory


class TaskContextFactory:
    def __init__(self, redis: aioredis.Redis, agent_factory, llm_factory):
        self.redis = redis
        self.agent_factory = agent_factory
        self.llm_factory = llm_factory

    def create(self) -> PMCATaskContext:
        task_id = uuid.uuid4().hex
        wb = PMCATaskWorkbench(self.redis, task_id)
        return PMCATaskContext(task_id, wb, self.agent_factory, self.llm_factory)
