PMCAMem0LocalConfig = {
    "llm": {
        "provider": "deepseek",
        "config": {
            "model": "deepseek-chat",
            "temperature": 0,
            "max_tokens": 2000,
            "deepseek_base_url": "https://api.deepseek.com/v1",
            "api_key": "sk-0189f706f4674f76b0d04c3421764d21",
        },
    },
    "vector_store": {
        "provider": "pgvector",
        "config": {
            "collection_name": "test",
            "host": "localhost",
            "port": 25432,
            "user": "postgres",
            "password": "postgres",
            "embedding_model_dims": 1024,
        },
    },
    "embedder": {
        "provider": "ollama",
        "config": {
            "model": "bge-m3:latest",
            "ollama_base_url": "http://localhost:11434",
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
