from typing import Dict, Literal
from autogen_ext.tools.mcp import SseServerParams
from loguru import logger
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class PMCAEnvConfig(BaseSettings):
    """
    统一的应用配置管理类（单例模式）。
    使用 pydantic 从环境变量中加载和验证所有配置。
    确保在整个应用程序中只有一个配置实例。
    """

    # --- 项目与交互配置 ---
    PROJECT_NAME: str

    # --- 交互模式 ---
    INTERACTION_MODE: Literal["console", "service"]
    RUN_BACKGROUND: bool

    # --- LLM 服务模式 ---
    LLM_TYPE: str = Field(
        ...,
        description="LLM服务类型: 'openai' (适用于所有在线/VLLM服务) 或 'ollama' (本地)",
    )

    # --- 不同能力的默认模型分配 ---
    DEFAULT_PROVIDER: str
    DEFAULT_MODEL: str
    CODER_PROVIDER: str
    CODER_MODEL: str
    REASONING_PROVIDER: str
    REASONING_MODEL: str

    # --- 在线模型提供商凭证 ---
    QWEN_BASE_URL: str
    QWEN_API_KEY: str
    DEEPSEEK_BASE_URL: str
    DEEPSEEK_API_KEY: str
    OPENAI_BASE_URL: str
    OPENAI_API_KEY: str
    GEMINI_BASE_URL: str
    GEMINI_API_KEY: str

    # --- Ollama 本地服务配置 ---
    OLLAMA_HOST: str

    # --- Routing 配置 ---
    TRIAGE_MAX_TURNS: int
    COMPLEX_EXECUTOR_MAX_TURNS: int
    SWARM_MAX_TURNS: int

    # --- Redis Cache配置信息 ---
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int
    REDIS_PASSWORD: str | None

    # Mcp-Server Infos
    MCP_TIMEOUT: int
    FUNCTIONAL_MCP_SERVER: str

    MCP_SERVER_EXCEL: str
    MCP_SERVER_FILESYSTEM: str
    MCP_SERVER_SEQUENTIALTHINKING: str
    MCP_SERVER_VEGALITE: str
    MCP_SERVER_ANALYSIS: str

    # =======================================================================
    # LightRAG Server and MCP server
    # =======================================================================
    MCP_SERVER_LIGHTRAG_APP: str
    MCP_SERVER_LIGHTRAG_STRATETY: str
    MCP_SERVER_LIGHTRAG_GAS: str

    LIGHTRAG_SERVER_STRATETY: str
    LIGHTRAG_SERVER_APP: str
    LIGHTRAG_SERVER_GAS: str

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    def get_mcp_servers(self) -> Dict[str, SseServerParams]:
        prefix = "MCP_SERVER_"
        servers = {}

        for field_name in self.__class__.model_fields:
            if field_name.startswith(prefix):
                url = getattr(self, field_name)
                if not url:
                    continue
                servers[field_name] = SseServerParams(
                    url=url,
                    timeout=float(self.MCP_TIMEOUT),
                )
        return servers

    def get_functional_servers(self) -> Dict[str, SseServerParams]:
        prefix = "FUNCTIONAL_MCP_SERVER"
        servers = {}

        for field_name in self.__class__.model_fields:
            if field_name.startswith(prefix):
                url = getattr(self, field_name)
                if not url:
                    continue
                servers[field_name] = SseServerParams(
                    url=url,
                    timeout=float(self.MCP_TIMEOUT),
                )
        return servers


try:
    PMCASystemEnvConfig = PMCAEnvConfig()  # type: ignore
except Exception as e:
    import traceback

    traceback.print_exc()
    logger.error(
        f"FATAL: 配置加载失败，请检查 .env 文件是否完整或存在拼写错误。错误: {e}"
    )
    exit(1)
