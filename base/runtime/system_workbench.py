import json
from dataclasses import dataclass
from typing import Any, Dict, Optional, List

from loguru import logger
from redis.asyncio import Redis
from autogen_core.tools import StaticWorkbench

from base.configs.env_config import PMCAEnvConfig


class _RedisKV:
    """任务级 KV 存储：pmca:task:{task_id} -> Hash"""

    def __init__(self, redis: Redis, task_id: str):
        self.redis = redis
        self.key = f"pmca:task:{task_id}"

    async def set(self, k: str, v: Any):
        await self.redis.hset(self.key, k, json.dumps(v, ensure_ascii=False))

    async def get(self, k: str) -> Any:
        v = await self.redis.hget(self.key, k)
        return json.loads(v) if v else None

    async def clear(self):
        await self.redis.delete(self.key)


class PMCATaskWorkbench(StaticWorkbench):
    """
    任务工作台：
    - 组合 StaticWorkbench（注册工具）与 Redis 持久 KV（状态）
    - 提供 async set_item / get_item，供 Selector/Swarm/MagOne 持久化 state
    """

    def __init__(self, redis: Redis, task_id: str, tools: Optional[List[Any]] = None):
        super().__init__(tools=tools or [])
        self._kv = _RedisKV(redis, task_id)
        self.task_id = task_id

    async def set_item(self, key: str, value: Any):
        await self._kv.set(key, value)
        logger.debug(f"[WB:{self.task_id}] SET {key}.")

    async def get_item(self, key: str) -> Any:
        v = await self._kv.get(key)
        logger.debug(f"[WB:{self.task_id}] GET {key} -> {type(v)}")
        return v

    async def save_team_state(self, state: Dict[str, Any]):
        await self.set_item("team_state", state)

    async def load_team_state(self) -> Optional[Dict[str, Any]]:
        return await self.get_item("team_state")


class PMCATaskWorkbenchManager:
    """简单工厂：创建任务隔离的 Workbench"""

    @staticmethod
    def create_workbench(task_id: str, redis: Redis) -> PMCATaskWorkbench:
        return PMCATaskWorkbench(redis, task_id, tools=[])
