# -*- coding: utf-8 -*-
"""
Mem0 写入校验种子（纯文本命中版，f-string logs）：
- 生成结构化“蒸馏后档案”文本，并把唯一 tag 嵌入正文（而非依赖 filters/version）
- 写入后用 query(tag) 做纯文本命中；带重试等待 embed/index 完成
运行：
  python base/application/knowledge_distill/distill_seed.py -a PMCATriage
"""

import argparse
import asyncio
import time
import uuid
from datetime import datetime, timezone
from loguru import logger

from core.memory.factory.mem0.service import PMCAMem0LocalService

DISTILLED_BODY = """\
# PMCATriage · 任务分流知识档案（蒸馏示例）
## 目标
- 在用户提交任务时，判断任务清晰度与复杂度，并路由到合适的智能体/流水线。

## 关键维度
- 任务清晰度：clear / partial / unclear
- 复杂度：simple / complex
- 智能体分组：Librarian（检索/知识库）、Technician（工具/执行）、MasterOfMemory（记忆管理）

## 决策要点
1. 若描述清晰 + 简单：直接交给 Technician。
2. 若描述清晰 + 复杂：分解任务，Librarian 辅助检索，Technician 执行。
3. 若描述不清：先由 Librarian 生成澄清问题清单，补齐上下文再路由。
4. 所有高价值事实、偏好、复用性规则 → 写入 mem0（长期记忆）。

## 质量守则
- 产生可验证结果（link / evidence / code）
- 关键节点日志化；失败可重试；输出结构化摘要
"""


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-a",
        "--agent",
        default="PMCATriage",
        help="agent name (collection will be snake_case)",
    )
    args = parser.parse_args()
    agent = args.agent

    # 唯一 tag
    write_tag = f"pmca_write_tag_{uuid.uuid4()}"
    # 把 tag 嵌入正文，确保任何版本的纯文本检索都能命中
    content = f"{DISTILLED_BODY}\n\n---\nTAG: {write_tag}\n"
    metadata = {
        "source": "distill_seed",
        "stage": "post_distillation",
        "ts": datetime.now(timezone.utc).isoformat(),
        "version": "v1",
        "topic": "triage_routing_policy",
        "pmca_write_tag": write_tag,  # 仍写入 metadata，后续升级可用 filters
    }

    logger.info(f"[seed] add → agent='{agent}', tag='{write_tag}'")
    await PMCAMem0LocalService.add_memory(agent, content, metadata)

    # 纯文本命中重试（等待 embed/index 完成）
    q = write_tag
    max_wait = 45
    deadline = time.time() + max_wait
    hit = 0
    while time.time() < deadline:
        res = await PMCAMem0LocalService.query_memory(agent, q)
        items = getattr(res, "results", None)
        hit = len(items) if isinstance(items, list) else 0
        logger.debug(f"[seed] verify (text) hit={hit}")
        if hit > 0:
            break
        await asyncio.sleep(3)

    if hit > 0:
        logger.success(
            f"[VERIFY] 纯文本命中 {hit} 条记录（兼容旧版本地 mem0 搜索）。tag='{write_tag}'"
        )
    else:
        logger.warning(
            f"[VERIFY] 仍为空：请检查 mem0config 的 vector_store/embedder 与 collection_name。tag='{write_tag}'"
        )

    await PMCAMem0LocalService.shutdown()
    logger.success("[seed] done.")


if __name__ == "__main__":
    asyncio.run(main())
