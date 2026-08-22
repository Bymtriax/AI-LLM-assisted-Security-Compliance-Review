# S17/G3 AI 安全合规审查助手：计划与进度

> 本文件记录已经发布的计划、实际进度和计划变更。

## 计划（未实现）

### 混合RAG 检索

- [ ] 新增 BM25 关键词检索；

## 进度（已实现）

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


### 2026-08-16 — 正式 S17 处理程序

- 新增 `src/corpus_builder/handle_s17.py`，负责读取完整英文 S17 PDF，并按条例结构生成可直接写入 vector store 的 records；
- 正式输出格式为 `id`、`text` 和 `metadata`，metadata 保存章节、版本、语言、页码、来源和切分追踪信息；
- embedding API 输入决定简化为纯 `text` 数组，其他信息不参与 embedding；
- `main()` 调用已有 `embedded_api.embed_texts()` 和 `vector_store.store_vectors()` 完成后两步；
- 新增 `tests/corpus_builder/test_handle_s17.py`；完整 QA 为 15 passed；
- 使用官方 S17 v8.2 PDF 实际验证：过滤残留页眉 `INFORMATION SECURITY` 后生成 224 条 records，ID 全部唯一，长度范围为 7–220 个英文词；
- 已完成正式 S17 建库：调用 `Qwen/Qwen3-VL-Embedding-8B` 生成 224 条 4096 维向量，并写入共享 Chroma collection `security_standards`；数据库记录数、S17 记录数和唯一 ID 数均为 224；
- 下一步：实现或验证正式法规检索流程。

### 2026-08-16 — 正式库 embedding 上下文

- 正式 S17 建库改为将条款编号、上级章节标题和条款正文共同输入 embedding 模型；
- 数据库保存的 document 仍为原始条款正文，供检索结果展示、引用和生成回答时使用；
- 这一格式与先前 ChromaDB 实验保持一致，可让较短的条款保留所属法规领域和主题语义；
- 已删除并重建共享 Chroma collection，以免混用旧的纯正文向量与新向量。

### 2026-08-19 — Vector Store 查询记录类型

- `query_vectors(vector, top_k=3)` 改为返回按相似度排序的 `list[CorpusRecord]`，不再将 Chroma distance 暴露为公共结果字段；
- 交互查询脚本改为直接读取 record 的 `id`、`text` 和 metadata；
- Vector Store 相关测试改为验证查询结果的 `CorpusRecord` 类型与完整 metadata 往返。
- 完整离线测试：42 passed。

### 2026-08-20 — S17 Handler 职责收敛

- `handle_s17(pdf_path: Path)` 改为必填 PDF 路径并只返回 `list[CorpusRecord]`；
- 已移除 handler 内部的 embedding、写入 ChromaDB 和命令列入口，后续由统一建库编排器处理；
- 测试改为验证必填路径契约，不再测试已移除的建库编排流程。

### 2026-08-20 — 统一法规建库入口

- 新增 `src/corpus_builder/build_corpus.py`，依次调用已登记的 handlers，合并 `CorpusRecord` 后完成既有 embedding 与 ChromaDB 写入流程；
- 新增 `scripts/build_corpus.py`，作为从项目根目录启动统一建库的命令入口；
- S17 是当前登记的 handler，后续法规 handler 只需加入 `HANDLERS`；
- 入口在调用 embedding API 前验证跨 handler 的 record ID 唯一，避免重复记录写入；
- 本次不建立 BM25 索引，BM25 步骤将在后续加入。
- 完整离线测试：44 passed。

### 2026-08-20 — S17 Record 检索文本

- S17 handler 现在直接在 `CorpusRecord.text` 写入 `Section`、`Parent sections` 与 `Text` 三行格式；
- 统一建库入口原样将 `record.text` 传给 embedding API，ChromaDB document 与查询结果也保留相同上下文；
- `text_sha256` 改为对应实际储存的完整检索文本。
- 全部 corpus 测试资料改为使用带上下文的 S17 `text`；一次性 embedding API 检查脚本也改用并验证相同格式。
- 完整离线测试：51 passed。

```markdown
## 更新格式

### YYYY-MM-DD — 更新标题

- 完成：
- 测试结果：
- 新决定：
- 计划变更：无 / 说明变更
- 风险或阻碍：
- 下一步：
```
