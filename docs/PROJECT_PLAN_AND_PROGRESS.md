# S17/G3 AI 安全合规审查助手：计划与进度

> 本文件记录已经发布的计划、实际进度和计划变更。

## 当前计划

### Plan 1：探索并实现 RAG

**目标：** 完成 RAG 的法规建库和法规检索部分。

**范围：**

1. 使用 S17/G3 作为输入资料，调用 embedding model 建立 Vector Database；
2. 实现法规检索：输入一个查询，返回相关的 S17/G3 内容。

**不包括：** Agent 模块和 Web UI。

**完成结果：** 已建立包含 S17/G3 的 Vector Database，并可根据查询取得相关条例内容。

## 进度记录

### 2026-08-11 — 整理法规原件

- 已将现有简体中文 S17/G3 原件归档到 `data/raw/standards/zh-Hans/`；
- 已从 GovCERT 下载官方英文 S17 v8.2 与 G3 v10.2，存放于 `data/raw/standards/en/`；
- 已新增 `docs/STANDARDS.md`，记录文件来源和存放规则；
- 已确认：Plan 1 的主语料使用英文 S17/G3；中文原件保留给后续独立中文索引。

### 2026-08-11 — 整理项目目录
-
- 项目文档已移动到 `docs/`；
- 原始条例保留在 `data/raw/standards/`；
- 已建立 `src/`、`scripts/`、`tests/` 和 `data/` 的目录结构；
- embedding API 连通性脚本已移动到 `scripts/`，并改为从环境变量读取 API key；
- 已添加 `.env.example` 和 `.gitignore`，避免提交密钥、向量数据库、用户上传文件和临时资料。

### 2026-08-11 — 确定 Python 环境管理方式

- 已决定使用 Conda 管理 Python 环境；
- 已新增 `environment.yml`，定义环境名称 `fyp-security-compliance`、Python 3.12 和 pip；
- 已通过 `D:\app\conda\Scripts\conda.exe` 创建 `fyp-security-compliance` 环境；
- 已验证环境的 Python 版本为 3.12.13。

### 2026-08-11 — 分离法规原件与建库代码

- `src/corpus_builder/` 只保留法规建库代码；
- 中英文 S17/G3 原件已移动到 `data/raw/standards/`；
- 条例来源清单已移动到 `docs/STANDARDS.md`；
- 已删除空的 `src/api/` 预留目录。

### 2026-08-11 — S17 Chunking 实验

- 已在 `environment.yml` 加入并安装 `pypdf`；
- 已新增 `exp/build_s17_chunks.py`；
- 已将英文 S17（45 页）切分为 183 个结构化 chunks：155 个编号条款和 28 个章节说明；
- 输出文件为 `exp/output/s17_en_chunks.jsonl` 和 `exp/output/s17_en_chunk_report.json`；
- 已验证指定控制条款及其页码，并确认 chunks 不含重复页眉和页脚；
- 尚未建立 Vector Database 或实现查询。
- 部分chunk字符过多，需要进一步切分，进行v2实验

### 2026-08-11 — S17 Chunking V2 实验

- 保留 V1 的 `exp/build_s17_chunks.py` 及其输出，作为按法规编号切分的基准结果；
- 新增 `exp/build_s17_chunks_v2.py`，直接从英文 S17 PDF 建立 V2 结果；
- V2 可识别没有末尾句点的条款编号，因此已分离先前黏连的 `5.2.4 / 5.2.5` 和 `7.2.1 / 7.2.2`；
- V2 会对超过 220 个英文词的结构化 chunk，按内部标题、项目符号、字母编号术语或段落批量细分；
- 结果：186 个结构化 chunks，生成 225 个用于检索的 chunks；
- 已生成 `exp/output/s17_en_retrieval_chunks_v2.jsonl`、审阅版 Markdown 和实验报告；
- 验证通过：186 个父 chunks 均被完整覆盖、225 个 ID 唯一、没有 chunk 超过 300 个英文词；
- 尚未建立 Vector Database 或实现查询。

### 2026-08-12 — Embedding 建库实验：输入格式决定

- Embedding 模型的输入只包含：`section`、`parent_titles`（上级章节）和 `text`（条款正文）；
- `document`、`version`、页码、来源文件和 chunk ID 不参与 embedding，保留为向量数据库的 metadata；
- 下一步：读取 V2 JSONL，先以少量 chunks 验证 API 输入与向量返回的 ID 映射。

### 2026-08-12 — S17 ChromaDB 建库实验

- 已选择 ChromaDB 作为本地嵌入式向量数据库，并在 Conda 环境安装 `chromadb`；
- 新增 `exp/build_s17_chroma_db.py`：读取 V2 JSONL、构造 embedding 输入、批量调用 SiliconFlow API、写入 ChromaDB；
- SiliconFlow 对大于 8 条的请求会重置 response index；为保证 chunk ID 与向量的一一映射，实验批次固定为 8 条；
- 已建立 `data/vector_db/s17_chroma_experiment/`，collection 为 `s17_en_v8_2_experiment`；
- 建库完成：225 个输入 chunks 与数据库记录完全一致，无缺失或额外 ID；使用 `Qwen/Qwen3-VL-Embedding-8B`，向量维度为 4096；
- 已生成本地 `manifest.json`，记录输入、模型、维度、批次大小与建库时间；
- 检索验证：关于「传输机密资料时的加密要求」的测试问题返回了 S17 15.2.2 等相关条款；

### 2026-08-12 — S17 ChromaDB 交互检索测试

- 新增 `exp/test_s17_chroma_retrieval.py`；
- 程序读取用户输入，使用与建库相同的 embedding 模型生成问题向量，并在本地 ChromaDB 返回最相关的 3 条 S17 内容；
- 每条结果显示 chunk ID、条款编号、父章节、来源页码、cosine distance 和原始法规正文。

### 2026-08-12 — 正式法规建库代码：模块职责决定

- 每份条例使用独立的 `build` 程序，负责读取 PDF、按该条例结构筛选和切分、调用 embedding 模块，并调用 Chroma 模块储存；
- embedding 模块为共用模块：输入 txt，输出 vector；
- Chroma 模块为共用模块：提供储存新向量与查询相近向量的接口；
- 下一步：依照上述职责，把 S17 的实验代码整理为 `src/` 中的正式代码。

### 2026-08-12 — Embedding API 模块

- 新增 `src/api/embedded_api.py`；
- 对外只提供两个接口：`embed_text(text)` 和 `embed_texts(texts)`；
- 模块从本地 `.env` 读取 SiliconFlow key，并在内部按每批 8 条处理，确保 API 返回顺序可验证；
- 已实际验证：单条输入返回 4096 维向量；9 条批量输入返回 9 个 4096 维向量。

### 2026-08-12 — Embedding API QA 测试

- 新增 `tests/api/test_embedded_api.py`，直接导入并测试 `src/api/embedded_api.py`；
- 使用 pytest 的 `monkeypatch` 在测试期间临时替换网络请求函数，不调用真实 API、不消耗额度；
- 覆盖单条输入、9 条自动拆为 8 + 1、空列表、空文字和异常 API response index；
- 已安装 pytest，并已运行：7 passed。

### 2026-08-12 — Vector Store 模块

- 新增 `src/corpus_builder/vector_store.py`，内部使用本地 ChromaDB；
- 对外提供：`store_vector(record, vector)`、`store_vectors(records, vectors)`、`query_vectors(vector, top_k=3)`；
- vector store 只处理向量和法规记录，不调用 embedding API；
- 新增 `tests/corpus_builder/test_vector_store.py`，使用临时 ChromaDB 测试储存、查询、批量排序和输入验证；
- 已运行 QA：4 passed。

## 更新格式

```markdown
### YYYY-MM-DD — 更新标题

- 完成：
- 测试结果：
- 新决定：
- 计划变更：无 / 说明变更
- 风险或阻碍：
- 下一步：
```
