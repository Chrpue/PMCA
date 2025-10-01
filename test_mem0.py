import asyncio

from autogen_ext.memory.mem0 import Mem0Memory
from loguru import logger
from base.configs import PMCAMem0LocalConfig
from base.runtime import PMCARuntime
from core.memory.factory.mem0 import PMCAMem0LocalService
from autogen_core.memory import MemoryContent, MemoryMimeType


async def test_mem0():
    # runtime = PMCARuntime()
    # await runtime.initialize()

    agent_name = "PMCATriageReviewer"
    mem = PMCAMem0LocalService.memory(agent_name)

    # 2.之前添加记忆（无法落库的代码）
    content1 = MemoryContent(
        content="通常情况下，当用户要给某一个智能体实现知识蒸馏等工作的时候，他的意思是使用已经存入lightrag中的知识，丛总根据不同的场景、话题等，提炼出核心精华作为智能体的原始记忆，这样能让智能体在行动之前总是先检索自己的记忆然后做出后续行动。",
        # content="我是一个AI架构师",
        mime_type=MemoryMimeType.TEXT,
        metadata={"purpose": "connectivity_test"},
    )
    await mem.add(content1)

    content2 = MemoryContent(
        content="PMCAKnowledgeLibrarian是主要负责对接LightRAG系统的智能体，它能使用较为完备的API直接使用LightRAG。",
        #         content="""
        # 南方的秋雨，黏黏腻腻地缠着黄昏。为了躲雨，也想甩掉些心事，阿文拐进了上海一条老弄堂里的小书店。店里很安静，只有旧书页和淡淡霉味混合成的、令人心安的气息。
        # 他在积满灰尘的书架间慢慢走着，随手抽出一本褪色的散文集。书页翻动间，一张泛黄的明信片掉了出来。照片是杭州西_湖的秋景，断桥残雪，雾气蒙蒙。背面是一行清秀的钢笔字：“愿我们像这湖光山色，岁岁皆安。” 像一句轻声的祝福，不知许给谁，也不知来自何年。
        # 阿文握着这张小卡片，心里某个角落忽然被照亮了。这份来自陌生旧时光的温柔，让他感到一种奇妙的慰藉。他拿着书结了账，走出店门时，发现笼罩着整个城市的雨幕，似乎也变得柔和了许多。""",
        mime_type=MemoryMimeType.TEXT,
        metadata={"purpose": "connectivity_test"},
    )
    await mem.add(content2)

    content3 = MemoryContent(
        content="PMCAKnowledgeTechnician是专门负责知识蒸馏的，比如提取话题中的核心内容、关键字等，还有更为复杂的工具，它是对直接从LightRAG系统中提取出的内容进行针对智能体记忆的二次加工。",
        mime_type=MemoryMimeType.TEXT,
    )
    await mem.add(content3)

    content = MemoryContent(
        content="PMCAMasterOfMemory是专门负责为智能体写入记忆、查询智能体记忆等相关工作的。",
        mime_type=MemoryMimeType.TEXT,
        metadata={"purpose": "connectivity_test"},
    )
    await mem.add(content)
    # 查询并打印结果
    result = await mem.query("PMCAMasterOfMemory是用来做什么的", limit=5)
    print(f"Got {len(result.results)} results: {result.results}")

    # 清空内存
    # await mem.clear()

    # 3.之后的代码（可以落库的代码）


#     content = MemoryContent(
#         content="""
#         大家好，我叫彭冰。
# 朋友们常说我人如其名，冷静、理性，像一块沉静的冰。在工作中，我确实习惯于用逻辑和数据作为思考的标尺，享受从纷繁复杂的信息中梳理出清晰脉络的过程。面对挑战时，这份冷静总能帮助我保持专注，找到问题的核心。
# 然而，冰的本质是水。在这份冷静之下，我怀揣着对世界和他人的巨大好奇与热情。我坚信，每一行冰冷的数据背后，都跳动着鲜活的个体和温暖的故事。我的工作不仅是分析，更是倾听——倾听数字背हीं后的需求、渴望与梦想。工作之余，我喜欢在城市的街巷中穿行，用相机捕捉那些不经意的温情瞬间，这让我时刻记得，技术最终要服务的，是充满烟火气的人间。
# 我就是彭冰，一个愿以理性为舟，在感性的海洋中探索的同行者。期待与大家相遇。
#         """,
#         mime_type=MemoryMimeType.TEXT,
#         metadata={"purpose": "connectivity_test"},
#     )
#     await mem.add(content)
#     result = await mem.query(query="hello")
#     print(result)


if __name__ == "__main__":
    asyncio.run(test_mem0())
