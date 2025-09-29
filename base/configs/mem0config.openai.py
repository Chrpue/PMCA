PMCAMem0LocalConfig = {
    "llm": {
        "provider": "openai",
        "config": {
            "model": "gpt-4o",
            "temperature": 0,
            "max_tokens": 2000,
            "openai_base_url": "https://api.openai.com/v1",
            "api_key": "",
        },
    },
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": "mem0",
            "host": "localhost",
            "port": 26333,
            "embedding_model_dims": 3072,
        },
    },
    "embedder": {
        "provider": "openai",
        "config": {
            "model": "text-embedding-3-large",
            "api_key": "",
            "openai_base_url": "https://api.openai.com/v1",
            "embedding_dims": 3072,
        },
    },
    "graph_store": {
        "provider": "neo4j",
        "config": {
            "username": "neo4j",
            "password": "mem0graph",
            "url": "neo4j://localhost:27687",
        },
    },
    "history_db_path": "/home/chrpue/projects/memory/mem0/history.db",
    "version": "v1.1",
    "custom_fact_extraction_prompt": "",
    "custom_update_memory_prompt": "",
}
