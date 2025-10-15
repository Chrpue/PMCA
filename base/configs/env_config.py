from typing import Dict, Literal
from urllib.parse import urlparse, parse_qs, urlunparse
from autogen_ext.tools.mcp import (
    McpServerParams,
    SseServerParams,
    StdioServerParams,
    StreamableHttpServerParams,
)
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

    MCP_SERVER_REDIS: str

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

    def _to_mcp_params(self, url: str, timeout: float) -> McpServerParams | None:
        if not url:
            return None
        raw = url.strip()
        parsed = urlparse(raw)
        path = (parsed.path or "").rstrip("/")

        # 1) 显式 SSE：path 以 /sse 结尾（query 无影响）
        if path.endswith("/sse"):
            return SseServerParams(url=raw, timeout=timeout)

        # 2) 显式 STDIO：path 以 /stdio 结尾（query 携带 docker 参数）
        if path.endswith("/stdio"):
            qs = parse_qs(parsed.query)

            image = (qs.get("image", ["mcp/redis:latest"])[0]).strip()
            network = (qs.get("network", [""])[0]).strip()
            addhosts = [
                h for h in qs.get("addhost", []) if h.strip()
            ]  # e.g. host.docker.internal:host-gateway
            env_list = [e for e in qs.get("env", []) if e.strip()]

            # 批量注入：ENV_PREFIX=REDIS_MCP_  => 把配置里以该前缀的项转换为 -e KEY=VALUE
            env_prefix = (qs.get("ENV_PREFIX", [""])[0]).strip()
            if env_prefix:
                for k, v in self.model_dump().items():
                    if (
                        isinstance(k, str)
                        and k.startswith(env_prefix)
                        and v not in (None, "")
                    ):
                        key = k[len(env_prefix) :]
                        env_list.append(f"{key}={v}")

            args = ["run", "--rm", "-i"]
            if network:
                args += ["--network", network]
            for ah in addhosts:
                args += ["--add-host", ah]
            for kv in env_list:
                args += ["-e", kv]
            args += [image]

            return StdioServerParams(
                command="docker", args=args, read_timeout_seconds=timeout
            )

        # 3) 其余：按 Streamable HTTP 处理，规范化为以 /mcp/ 结尾
        norm_path = path
        if not norm_path.endswith("/mcp"):
            norm_path = norm_path + "/mcp"
        if not norm_path.endswith("/"):
            norm_path = norm_path + "/"
        normalized = parsed._replace(path=norm_path)  # 保留原 query/fragment
        return StreamableHttpServerParams(url=urlunparse(normalized), timeout=timeout)

    def get_mcp_servers(self) -> Dict[str, McpServerParams]:
        prefix = "MCP_SERVER_"
        servers: Dict[str, McpServerParams] = {}

        for field_name in self.__class__.model_fields:
            if not field_name.startswith(prefix):
                continue
            url = getattr(self, field_name)
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
