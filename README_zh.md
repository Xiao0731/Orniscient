# Orniscient

**Orniscient** 是一个面向鸟类生态知识推理的大语言模型评测与知识增强项目，集成了领域 Benchmark、多源知识库原型与 knowledge_RAG 评测 Harness。

> **Orniscient = Ornithology + Omniscient**  
> 目标是构建一个可验证、可追溯、可扩展的鸟类生态知识推理基础设施。

<div align="center">

[English](./README.md) | 简体中文

</div>

---

## 项目概览

Orniscient 围绕 **Benchmark–Knowledge Base–Harness** 三个核心部分展开：一方面构建覆盖多层次能力的鸟类生态评测基准，另一方面组织多源知识库，并通过统一的评测 Harness 比较裸模型与知识增强设置下的大语言模型表现。

本项目来自本科毕业设计《基于大语言模型智能体的物种知识库自动构建与知识推理方法研究》。项目与康奈尔鸟类相关团队/数据资源方向开展合作，并已获得 **Birds of the World (BOW)** 的科研使用授权。由于 BOW 等数据源具有授权限制，仓库中不会公开原始 BOW 文本、完整派生 chunks、完整知识库产物或大规模评测日志。

![Framework Overview](docs/assets/framework_overview.png)

---

## 项目背景

大语言模型在通用问答、文本生成和复杂推理任务中已经展现出较强能力，但在鸟类生态等专业领域中，模型仍容易受到以下问题影响：

- **知识过时**：鸟类分类体系、命名体系和保护状态会随 checklist 和权威数据库更新而变化；
- **事实幻觉**：模型可能生成看似合理但无法回溯到权威来源的描述；
- **分类混淆**：相近物种、亚种、科属关系和历史分类变更容易造成错误；
- **证据利用不足**：模型即使拿到原文证据，也不一定能正确抽取与推理；
- **长上下文不稳定**：BOW 中的自然史文本篇幅较长，关键信息可能分散在多个章节中；
- **结构化任务困难**：如全局物种集合枚举、反向物种识别和约束保护规划，不能仅依赖自由生成完成。

鸟类生态知识具有明显的领域复杂性：它同时包含严格的分类层级、动态变化的 checklist、复杂的地理分布、迁徙和生境信息，以及大量分散在长文本中的自然史知识。因此，Orniscient 不只是一个问答题库，而是尝试构建一个从数据组织、题库设计、知识库构建到自动化评测的系统框架。

---

## 核心贡献

Orniscient 当前阶段主要包含四个部分：

1. **Bird Ecology Benchmark**  
   构建覆盖 14 个数据集的鸟类生态 LLM 评测基准，覆盖知识检索、领域推理分析和复杂逻辑推理三个层级。

2. **Multi-source Knowledge Base Prototype**  
   设计多源知识库原型，包括 canonical taxonomy backbone、BOW 文本证据库、Claim–Fact–Evidence–Qualifier 事实证据链、BIRDBASE 表格知识库和 Taxon–Fact–Evidence–Chunk 图谱链路。

3. **knowledge_RAG Harness**  
   实现统一的知识增强评测框架，支持客观题、开放生成题和结构化任务的自动化评测，并能够比较裸模型与知识增强设置。

4. **Evaluation-driven Analysis**  
   通过多模型对比实验分析知识库接入在不同任务上的提升、下降和不稳定现象，进一步诊断知识覆盖率、检索召回、上下文构造和模型证据利用能力。

---

## 目录结构

```text
orniscient/
├── evaluation/                  # 评测流程与评分脚本
│   ├── objective_eval.py         # 客观题评测
│   ├── subjective_answer.py      # 主观题回答生成
│   ├── subjective_judge.py       # LLM-as-a-Judge 评分
│   ├── subjective_aggregate.py   # 主观题结果聚合
│   ├── structured_eval.py        # 结构化任务评测
│   ├── run_subjective_pipeline.py
│   ├── run_remaining_four_eval.py
│   ├── text_RAG/                 # Text-RAG 相关评测模块
│   ├── kg_RAG/                   # KG-RAG 相关模块
│   ├── knowledge_RAG/            # 统一知识增强评测 Harness
│   ├── fewshot_examples/         # few-shot 示例
│   └── figures/                  # 项目图示与可视化结果
│
├── kg_v2/                        # 多源知识库构建模块
│   ├── Step1_taxonomy/           # canonical taxonomy backbone 构建
│   ├── Step2_attachment/         # BOW 文本记录挂载与 chunk 对齐
│   ├── Step3_extraction/         # Claim/Fact/Evidence/Qualifier 抽取
│   ├── Step4_graph/              # Taxon-Fact-Evidence-Chunk 图谱构建
│   ├── builders/                 # 知识库构建工具
│   ├── extractors/               # 信息抽取模块
│   ├── parsers/                  # 数据解析模块
│   ├── rag/                      # 知识增强检索相关模块
│   ├── renderers/                # 渲染与导出模块
│   ├── schema/                   # schema 定义
│   ├── utils/                    # 通用工具函数
│   ├── validators/               # 数据校验模块
│   └── run_build_kb_v2.py        # 知识库构建入口
│
├── question/                     # Benchmark 题库
│   ├── QA-SC/
│   ├── QA-MC/
│   ├── QA-SA/
│   ├── Bird-Geo/
│   ├── Bird-Taxonomy/
│   ├── Bird-Life/
│   ├── Bird-Eco/
│   ├── Bird-Con/
│   ├── Bird-Comp/
│   ├── Bird-Reason/
│   ├── Bird-Plan/
│   ├── Bird-ID/
│   ├── List-Global/
│   └── Bird-Classify/
│
├── scripts/                      # 辅助脚本
├── tests/                        # 测试脚本
├── md/                           # 项目说明与中间文档
├── reports/                      # 报告材料与结果整理
├── docs/assets/                  # README 使用的图片资源
├── prompt.py                     # Prompt 模板与生成逻辑
├── benchmark_complete.py         # Benchmark 构建主脚本
├── kb_benchmark_queries.py       # 知识库查询与 benchmark 相关工具
├── docker-compose.yml            # 可选服务配置
├── .env.example                  # 环境变量模板
├── .gitignore
├── README.md                     # 英文 README
└── README_zh.md                  # 中文 README
```

---

## Benchmark Design

Orniscient 的 Benchmark 由 **14 个数据集**组成，按照任务复杂度划分为三个层级：**知识检索、领域推理分析和复杂逻辑推理**。该设计不是简单增加题目数量，而是希望从不同认知难度和知识类型上刻画大语言模型在鸟类生态任务中的能力边界。

### 知识点脑图

以下两张图展示了 Benchmark 中“知识获取”和“逻辑推理”两类任务的知识点组织方式。

![知识获取](docs/assets/知识获取.png)

![逻辑推理](docs/assets/逻辑推理.png)

### Level 1：知识检索

Level 1 主要考察模型对鸟类生态基础事实的掌握能力，题目通常可以从 BOW 或辅助数据源中的局部证据直接得到答案。

| Dataset | 任务说明 |
|---|---|
| `QA-SC` | 单选题，考察单一事实或基础属性识别 |
| `QA-MC` | 多选题，考察多个正确事实的同时识别 |
| `QA-SA` | 简答题，考察模型对短事实答案的生成能力 |

典型知识维度包括形态、食性、分布、生境、分类、保护状态、繁殖行为和生态习性等。该层级用于评估模型是否具备基本的鸟类生态事实检索能力。

### Level 2：领域推理与综合分析

Level 2 主要考察模型在鸟类分类学、地理分布、生态功能、保护状态、繁殖生物学和相似种比较等领域任务中的分析能力。

| Dataset | 任务说明 |
|---|---|
| `Bird-Geo` | 地理分布、生境、迁徙和空间边界推理 |
| `Bird-Taxonomy` | 分类层级、命名变迁、split/lump 等分类学推理 |
| `Bird-Life` | 繁殖生物学、生命周期和行为时序归纳 |
| `Bird-Eco` | 食性、觅食策略、生态功能和因果链推理 |
| `Bird-Con` | 保护状态、威胁因素和保护风险分析 |
| `Bird-Comp` | 相似种或近缘类群之间的形态与行为比较 |
| `Bird-Classify` | 根据特征描述推断分类层级或总结分类特征 |

该层级的核心目标不是让模型复述文本，而是要求模型在证据基础上进行归纳、比较、判断和解释。

### Level 3：复杂逻辑推理

Level 3 面向更复杂的任务，包括长上下文、多跳推理、反向识别、约束规划和全局集合枚举。

| Dataset | 任务说明 |
|---|---|
| `Bird-Reason` | 跨章节、跨证据的长上下文推理与鉴伪 |
| `Bird-Plan` | 带预算、地形、法律和威胁约束的保护规划 |
| `Bird-ID` | 根据掩码后的形态、声学、地理和生态描述反向识别物种 |
| `List-Global` | 基于结构化条件筛选生成全局物种集合 |

该层级尤其关注模型是否能在复杂约束下保持事实一致性、证据可追溯性和推理链条稳定性。

---

## Knowledge Base

Orniscient 的知识库原型采用多源混合知识组织方式，不将所有信息简单压缩为单一知识图谱，而是根据不同任务需求组合文本证据、结构化表格、taxonomy backbone 和图谱链路。

### 多源数据组织

知识库原型围绕以下资源构建：

- **Birds of the World (BOW)**：提供物种和科级自然史文本，是项目的核心文本知识源；
- **AviList / Clements**：用于构建和对齐 canonical taxonomy backbone；
- **BIRDBASE**：用于结构化属性过滤和候选约束；
- **Order 表及其他辅助表格**：用于分类层级校验和补充映射。

由于 BOW 原始文本和派生内容具有授权限制，本仓库不会公开原始 BOW 数据或完整文本 chunks。

### Claim–Fact–Evidence–Qualifier 建模

在 BOW chunk 层之上，项目设计了四类核心知识对象：

| 对象 | 含义 |
|---|---|
| `Claim` | 从原文中抽取的自然语言断言，尽量保留原文语义 |
| `Fact` | 经过标准化后的结构化事实，便于检索、聚合和比较 |
| `Evidence` | 支撑 claim/fact 的原文证据和来源信息 |
| `Qualifier` | 描述事实成立条件的限定信息，如地域、季节、性别、年龄、亚种、时间和不确定性 |

这一层的目标不是简单抽取三元组，而是形成具有证据支撑和条件限定能力的事实证据层。

### Taxon–Fact–Evidence–Chunk 图谱链路

图谱链路用于连接分类实体、结构化事实、证据片段和原始文本块：

```text
Taxon -> Fact -> Evidence -> Chunk
```

该设计使系统能够从结构化事实回溯到原始证据，也能够根据目标物种、事实类型或证据来源进行任务感知检索。

### 知识图谱子图示例

下面是鸟类生态知识图谱的局部子图示例，用于展示目标物种周围的邻域结构和图谱化知识连接方式。

![Knowledge Graph Subgraph Example](docs/assets/kg_subgraph_example.png)

### 分类树与 checklist crosswalk 示例

项目还包含 taxonomy tree 和 checklist crosswalk 的可视化，用于展示分类主树构建和不同 checklist 之间的兼容层对齐。

![Taxonomy Tree](docs/assets/taxonomy_tree_accipitriformes.svg)

![Checklist Crosswalk](docs/assets/checklist_crosswalk_accipitriformes.svg)

---

## Harness

Orniscient 的 `knowledge_RAG` Harness 是连接题库、模型、知识源、Prompt 模式、检索器、评分器和结果日志的统一评测框架。它不是单个评分脚本，而是用于组织实验流程的工程层。

### Harness 支持的能力

- 多模型统一调用；
- 多数据集任务路由；
- zero-shot / few-shot / CoT 等 Prompt 模式；
- Vanilla 与知识增强设置对比；
- objective / subjective / structured 三类任务流程；
- 自动评分与 LLM-as-a-Judge；
- run manifest、context log、resume、dry-run 和错误记录；
- 结果聚合与可视化分析。

### 评测任务类型

| 类型 | 对应任务 | 主要指标 |
|---|---|---|
| 客观题 | `QA-SC`, `QA-MC`, `QA-SA`, `Bird-Geo`, `Bird-Taxonomy` | Accuracy, Exact Match, F1 |
| 开放生成题 | `Bird-Life`, `Bird-Eco`, `Bird-Con`, `Bird-Comp`, `Bird-Reason`, `Bird-Plan` | LLM-as-a-Judge |
| 结构化任务 | `Bird-ID`, `List-Global`, `Bird-Classify` | Recall, weighted top-5 accuracy, hierarchical accuracy |

### Knowledge Modes

项目支持或预留了多种知识接入方式：

| Mode | 含义 |
|---|---|
| `none` | 裸模型，不接入外部知识 |
| `text_rag` | 基于 BOW chunk 的文本检索增强 |
| `kg_v1` | 早期知识图谱原型 |
| `kg_v3` | schema-driven 知识图谱原型 |
| `hybrid` | 文本、图谱和表格知识的混合访问 |

知识增强并不被假设为对所有任务都单调提升。该 Harness 的目标之一正是分析：知识库在哪些任务上有效、在哪些任务上失效，以及失败来源是知识覆盖不足、检索召回不足、上下文构造问题，还是模型无法正确利用证据。

---

## Data Notice

本仓库主要用于毕业设计审阅和研究展示。项目已获得 BOW 的科研使用授权，但由于 BOW 等数据源具有授权限制，公开版本不会包含以下内容：

- Birds of the World 原始文本；
- BOW 派生的完整文本 chunks；
- API keys 或本地 `.env` 文件；
- 完整知识库生成产物；
- Neo4j 数据库 dump；
- LightRAG 工作缓存；
- 完整模型输出、judge 日志、context logs 和大规模评测结果；
- 大模型权重或 checkpoint。

当前仓库可能包含用于论文审阅的 benchmark question 文件。若未来公开发布，应根据数据授权情况将完整题库替换为脱敏后的 demo 样例。

如需完整复现实验流程，使用者需要自行准备已授权的数据源，并按照 `.env.example` 和代码中的路径配置放置到本地对应目录。

---

## Usage

### 1. 克隆仓库

```bash
git clone https://github.com/<your-username>/orniscient.git
cd orniscient
```

### 2. 创建 Python 环境

```bash
python -m venv .venv
```

Windows PowerShell 下激活环境：

```powershell
.venv\Scripts\Activate.ps1
```

### 3. 安装依赖

如果仓库中提供了 `requirements.txt`：

```bash
pip install -r requirements.txt
```

如果暂未提供，请根据 `evaluation/` 和 `kg_v2/` 中使用的模块手动安装依赖。

### 4. 配置环境变量

复制 `.env.example` 为 `.env`：

```bash
cp .env.example .env
```

Windows PowerShell 下可使用：

```powershell
Copy-Item .env.example .env
```

然后在 `.env` 中填写本地路径和模型 API key。

### 5. 运行客观题评测

```bash
python evaluation/objective_eval.py ^
  --models deepseek qwen kimi ^
  --datasets QA-SC QA-MC QA-SA Bird-Geo Bird-Taxonomy ^
  --question-root question
```

### 6. 运行开放生成题评测流程

```bash
python evaluation/run_subjective_pipeline.py ^
  --models deepseek qwen kimi ^
  --datasets Bird-Life Bird-Eco Bird-Con Bird-Comp Bird-Reason Bird-Plan ^
  --modes zero_shot few_shot cot ^
  --question-root question ^
  --fewshot-root evaluation/fewshot_examples
```

### 7. 运行结构化任务评测

```bash
python evaluation/run_remaining_four_eval.py ^
  --models deepseek qwen kimi ^
  --datasets Bird-ID List-Global Bird-Classify Bird-Con ^
  --question-root question
```

### 8. 构建知识库原型

```bash
python kg_v2/run_build_kb_v2.py
```

实际命令可能会根据本地数据路径、模型提供商、知识接入模式和实验设置有所调整。

---

## Repository Status

当前版本已完成：

- 覆盖 14 个 dataset 的鸟类生态 Benchmark；
- 多源知识库 schema 与构建流程；
- canonical taxonomy backbone；
- BOW 文本记录挂载与 chunk 对齐；
- Claim–Fact–Evidence–Qualifier 建模；
- Taxon–Fact–Evidence–Chunk 图谱设计；
- objective / subjective / structured 三类评测流程；
- knowledge_RAG Harness；
- 裸模型与知识增强设置下的对比评测；
- 项目目录、运行流程和复现机制整理。

后续计划包括：

- 全量 Neo4j 图谱部署；
- LightRAG mix 检索集成；
- reranker 消融实验；
- Bird-ID 候选召回优化；
- List-Global 确定性输出优化；
- LangGraph 或类似框架下的鸟类专家智能体原型；
- 基于评测反馈的系统持续迭代。

---

## License and Data Access

本仓库中的源代码主要用于学术研究和毕业设计展示。

原始数据和由受限来源派生的完整数据产物不随公开仓库分发。请确保任何外部数据源的使用均符合其授权协议和使用条款。

---

## Acknowledgements

Orniscient 源于一个朴素的问题：鸟类生态知识是否可以不再只是散落在长文本、表格和 checklist 之间，而是被组织成可验证、可检索、可推理、可评测的知识基础设施。

本项目希望通过 Benchmark、知识库原型和评测 Harness 的结合，为未来鸟类生态知识库、知识增强问答系统和鸟类专家智能体提供一个可复用的起点。
