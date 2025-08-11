import os
import nest_asyncio
from dotenv import load_dotenv
from datetime import datetime
from lightrag import LightRAG
from lightrag.llm.ollama import ollama_model_complete, ollama_embed
from lightrag.utils import EmbeddingFunc

from lightrag.kg.shared_storage import initialize_pipeline_status


nest_asyncio.apply()


class RAGinitializer:
    """
    LightRAG初始化类，支持不同模式下的环境配置
    """

    def __init__(self, area: str = "rag"):
        """
        初始化RAG配置
        :param mode: 运行模式（facts/strategy/rag），决定数据库连接配置
        """
        self.root_dir = os.path.dirname(os.path.abspath(__file__))
        self.working_dir = os.path.join(self.root_dir, "cache")

        self.area = area
        self._load_environment()
        self._setup_enviroment()

    def _load_environment(self):
        """加载.env文件"""
        try:
            load_dotenv()
        except Exception as e:
            print(f"未找到.env文件: {str(e)}")

    def _setup_enviroment(self):
        """根据模式设置环境变量"""
        common_env = {
            # PostgreSQL配置（根据模式切换数据库）
            "AGE_GRAPH_NAME": self.area,
            "POSTGRES_DATABASE": self.area,
        }

        # 设置环境变量
        os.environ.update(common_env)

        if not os.path.exists(self.working_dir):
            os.makedirs(self.working_dir)
        print(f"Working Directory: {self.working_dir}")

    async def initialize(self):
        """初始化LightRAG实例"""
        rag = LightRAG(
            working_dir=os.path.join(
                self.working_dir,
                f"lightrag_cache_{datetime.now().strftime('%Y-%m-%d-%H:%M:%S')}",
            ),
            llm_model_func=ollama_model_complete,
            llm_model_name=os.environ["LLM_MODEL"],
            llm_model_max_async=int(os.environ["MAX_ASYNC"]),
            llm_model_max_token_size=int(os.environ["MAX_TOKENS"]),
            llm_model_kwargs={
                "host": os.environ["LLM_BINDING_HOST"],
                "options": {"num_ctx": int(os.environ["MAX_TOKENS"])},
            },
            embedding_func=EmbeddingFunc(
                embedding_dim=int(os.environ["EMBEDDING_DIM"]),
                max_token_size=int(os.environ["EMBEDDING_MAX_TOKENS"]),
                func=lambda texts: ollama_embed(
                    texts=texts,
                    embed_model=os.environ["EMBEDDING_MODEL"],
                    host=os.environ["EMBEDDING_BINDING_HOST"],
                ),
            ),
            kv_storage="PGKVStorage",
            doc_status_storage="PGDocStatusStorage",
            graph_storage="PGGraphStorage",
            vector_storage="PGVectorStorage",
            auto_manage_storages_states=False,
        )

        await rag.initialize_storages()
        await initialize_pipeline_status()
        return rag
