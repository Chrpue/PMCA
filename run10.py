import requests, json, pprint, sys
from loguru import logger

base_url = "http://localhost:13004"
endpoint = f"{base_url}/query"
headers = {"Content-Type": "application/json"}

payload = {
    "query": "对磨溪站H8井进行昨天上午2点到下午3点的电子巡检",
    "mode": "mix",  # 换成 hybrid，优先尝试图 + 向量综合
    "top_k": 2,  # 提高召回条数
    "only_need_context": False,
    "only_need_prompt": False,
    "response_type": "string",
    "stream": False,
    "user_prompt": """你是一个负责掌管记忆的专家，你的任务是根据用户的查询内容，提供最相关的记忆上下文，
你需要注意的事情是.
1. 不要做出任何决断，仅仅提供记忆.
2. 输出格式增加前缀`根据我的回忆`，比如如下格式.
根据我的回忆：xxxx
""",
}

resp = requests.post(endpoint, headers=headers, json=payload, timeout=60)
resp.raise_for_status()

data = resp.json()

# ----------- 兼容两种返回结构 -----------
if isinstance(data, dict) and "answer" in data:
    print("答案摘要:\n", data["answer"])
    print("\n引用片段:")
    for ref in data.get("references", []):
        print(f"- {ref['file_name']} (p.{ref['page_number']}): {ref['score']:.2f}")
        print(" 片段内容:", ref["content"][:120], "...")
else:
    logger.info(data)
    msg = data["response"] if isinstance(data, dict) else data

    logger.error(msg)
    if "[no-context]" in msg:
        print(
            "\n检索到相关上下文：\n"
            "1) 先确认已上传并成功索引含『运动方程』等关键词的文档；\n"
            "2) 或把 mode 调成 'naive' 让 LLM 直接回答；\n"
            "3) 或增大 top_k、换 中文/英文 同义词关键词。"
        )
