---
owner_agent: "PMCAKnowledgeLibrarian"
knowledge_type: "workflow_protocol"
task_keywords:
  - "更新知识"
  - "删除知识"
  - "修改文档"
  - "知识生命周期"
---

# 知识生命周期管理策略

本文档为`PMCAKnowledgeLibrarian`和`PMCAAgentsDecision`智能体提供关于如何处理知识更新与删除任务的指导。

### 1. 更新知识

- **触发指令**: 当用户指令包含“更新”、“修改”、“修正”、“替换内容”等意图时。
- **流程**:
  1. `PMCAAgentsDecision`选择 `KnowledgeLibrarian` 作为执行者。
  2. `KnowledgeLibrarian` 与用户确认需要更新的知识的唯一标识（可以是文件名或ID）。
  3. `KnowledgeLibrarian` 接收用户提供的新内容。
  4. `KnowledgeLibrarian` 构建一个包含`action: "update_document"`和相应参数的结构化指令，并发送给`KnowledgeTechnician`。

### 2. 删除知识

- **触发指令**: 当用户指令包含“删除”、“移除”、“废弃”、“忘记”等意图时。
- **流程**:
  1. `PMCAAgentsDecision`选择 `KnowledgeLibrarian` 作为执行者。
  2. `KnowledgeLibrarian` 与用户二次确认需要删除的知识，并提醒此操作不可逆。
  3. 在用户确认后，`KnowledgeLibrarian` 构建一个包含`action: "delete_document"`和相应参数的结构化指令，并发送给`KnowledgeTechnician`。
