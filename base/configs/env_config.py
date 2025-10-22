from typing import Dict, Literal
from urllib.parse import urlparse, urlunparse
from autogen_ext.tools.mcp import (
    McpServerParams,
    SseServerParams,
    StreamableHttpServerParams,
)
from loguru import logger
from dotenv import load_dotenv
from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


def _normalize_streamable_http_base(raw: str) -> str:
    """把任意 http(s) 地址规范成以 /mcp 结尾（不带尾斜杠）的基址。"""
    parsed = urlparse(raw.strip())
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Only http/https are allowed for MCP servers: {raw}")

    path = (parsed.path or "").rstrip("/")
    if not path.endswith("/mcp"):
        # 去掉多余尾斜杠后再拼接，最终统一为 “…/mcp”
        if path == "":
            path = "/mcp"
        else:
            path = path + "/mcp"
    normalized = parsed._replace(path=path)  # 保留原 query/fragment/host/port
    return urlunparse(normalized)


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
    MCP_SERVER_TODO: str

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

    @validator("*", pre=True)
    def _strip(cls, v):
        return v.strip() if isinstance(v, str) else v

    def _to_mcp_params(self, raw: str, timeout: float) -> McpServerParams | None:
        if not raw:
            return None
        u = raw.strip()
        parsed = urlparse(u)
        path = (parsed.path or "").rstrip("/")

        # 显式 SSE：仅当 URL 以 /sse 结尾时
        if path.endswith("/sse"):
            return SseServerParams(url=u, timeout=timeout)

        # 其余一律按 Streamable HTTP 处理，并规范成以 /mcp 结尾（无尾斜杠）
        norm = _normalize_streamable_http_base(u)
        return StreamableHttpServerParams(url=norm, timeout=timeout)

    def get_mcp_servers(self) -> Dict[str, McpServerParams]:
        servers: Dict[str, McpServerParams] = {}
        prefix = "MCP_SERVER_"
        for field_name in self.__class__.model_fields:
            if not field_name.startswith(prefix):
                continue
            url = getattr(self, field_name, None)
            if not url:
                continue
            params = self._to_mcp_params(url, float(self.MCP_TIMEOUT))
            if params:
                servers[field_name] = params

        return servers

    def get_functional_servers(self) -> dict[str, McpServerParams]:
        servers: Dict[str, McpServerParams] = {}
        url = getattr(self, "FUNCTIONAL_MCP_SERVER", None)
        if url:
            params = self._to_mcp_params(url, float(self.MCP_TIMEOUT))
            if params:
                servers["FUNCTIONAL_MCP_SERVER"] = params
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
