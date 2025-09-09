import asyncio
from autogen_agentchat.ui import Console
from autogen_ext.models.ollama import OllamaChatCompletionClient
from autogen_ext.models.openai import OpenAIChatCompletionClient
from loguru import logger

from typing import ClassVar, Union, cast, Dict, Any

from pydantic import BaseModel, ConfigDict, model_validator

from base.runtime import PMCARuntime
from core.client import LLMFactory, ProviderType, DutyType
from core.assistant.factory import PMCAAgentFactory

from entry import PMCAEntryGraph, APPWorkbench


async def main():
    runtime = PMCARuntime()
    await runtime.initialize()

    task_ctx = runtime.create_task_context()

    await PMCAEntryGraph.begin(task_ctx)


if __name__ == "__main__":
    asyncio.run(main())
