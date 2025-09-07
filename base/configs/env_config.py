import os
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 在模块加载时，自动从 .env 文件加载环境变量
load_dotenv()


class PMCAEnvConfig(BaseSettings):
    """
    统一的应用配置管理类。
    使用 pydantic 从环境变量中加载和验证所有配置。
    """

    # --- 项目与交互配置 ---
    PROJECT_NAME: str
    INTERACTION_MODE: str = Field(default="MANUAL", alias="PMCA_INTERACTION_MODE")

    # --- LLM Provider ---
    LLM_TYPE: str

    # --- LLM TYPES ---
    # --- Qwen ---
    QWEN_BASE_URL: str
    QWEN_API_KEY: str
    QWEN_MODEL_NAME: str
    QWEN_CODER_NAME: str

    # --- OpenAI ---
    OPENAI_BASE_URL: str
    OPENAI_API_KEY: str
    OPENAI_MODEL_NAME: str

    # --- DeepSeek ---
    DEEPSEEK_BASE_URL: str
    DEEPSEEK_API_KEY: str
    DEEPSEEK_MODEL_NAME: str

    # --- Ollama ---
    OLLAMA_HOST: str
    OLLAMA_MODEL_NAME: str
    OLLAMA_CODER_NAME: str

    # --- Docker (for Code Executor) ---
    DOCKER_IMAGE: str
    DOCKER_CONTAINER_NAME: str
    DOCKER_TIMEOUT: int
    DOCKER_WORK_DIR: str
    DOCKER_AUTO_REMOVE: bool
    DOCKER_STOP_CONTAINER: bool
    DOCKER_EXTRA_VOLUMES: str

    # --- File Surfer Agent ---
    FILESURFER_BASE_PATH: str

    # --- MCP Servers ---
    MCP_TIMEOUT: int
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

    # --- Redis Cache ---
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int
    REDIS_PASSWORD: str | None = None
    REDIS_AGENT_REGISTRY_KEY: str = "pmca:agent_registry"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


# 创建一个全局唯一的配置实例
try:
    config = PMCAEnvConfig()  # type: ignore
    print(config)
except Exception as e:
    import traceback

    traceback.print_exc()
    print(f"FATAL: 配置加载失败，请检查 .env 文件是否完整或存在拼写错误。错误: {e}")
    exit(1)
