[KnowledgeFor: PMCATeamDecision]

# 工作流模式：知识管理协作范式

本文档为`PMCATeamDecision`智能体提供决策依据，用于为“知识管理”类任务选择最合适的团队协作组件。

### 1. 核心协作范式

知识管理任务遵循“接口与实现分离”的设计，信息流是单向且确定的：`User` -> `Librarian` -> `Technician` -> `Librarian` -> `User`。

- **接口层 (`KnowledgeLibrarian`)**: 与用户交互，将自然语言转为结构化指令。
- **实现层 (`KnowledgeTechnician`)**: 接收指令，精确调用`LightRAG`工具。

### 2. 团队组件决策建议

- **首选组件：`RoundRobin` (轮询模式)**
  - **理由**: 知识管理是一个典型的**线性流水线**，`RoundRobin` 以其简单、可控的特性，能够完美、高效地支持这种确定的交互顺序。
- **备选组件：`GraphFlow` (图流程模式)**
  - **理由**: 适用于未来可能出现的、包含分支和依赖的更复杂的知识管理工作流。在当前阶段，使用它略显“重”。
- **不推荐的组件**: `Swarm`, `MagenticOne`。它们的动态和探索性不适用于流程固定的知识管理任务。

### 3. 工作流中的元数据处理

元数据处理是此工作流的核心环节。`KnowledgeLibrarian`负责在流程前期与用户交互，完成所有元数据（特别是`owner_agent`）的定义。
