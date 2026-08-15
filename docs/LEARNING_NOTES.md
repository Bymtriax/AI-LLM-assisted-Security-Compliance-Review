# 学习笔记

> 用于记录项目开发过程中学到的概念、工具用法和实践经验。内容面向项目成员，也让后续接手的 Agent 能快速了解已学习的内容。
>


---

## Git 常用指令

```powershell
# 查看目前改了什么
git status

# 查看具体改动
git diff

# 将指定文件加入下一次提交
git add docs/LEARNING_NOTES.md

# 将所有已追踪文件的改动加入下一次提交
git add -u

# 建立一次提交
git commit -m "docs: add Git learning notes"

# 查看提交记录
git log --oneline

# 拉取远端最新改动
git pull

# 上传本地提交到 GitHub
git push
```

### Commit 备注常用简写

提交备注建议使用：`类型: 简短说明`。

| 简写 | 含义 | 示例 |
|---|---|---|
| `feat` | 新功能 | `feat: add regulation retrieval` |
| `fix` | 修复问题 | `fix: handle empty query` |
| `docs` | 修改文档 | `docs: update project framework` |
| `test` | 新增或修改测试 | `test: add vector store tests` |
| `refactor` | 重构，不改变功能 | `refactor: simplify embedding API` |
| `chore` | 杂项，如环境或依赖配置 | `chore: update environment dependencies` |
| `style` | 只改格式，不改变逻辑 | `style: format source files` |

## 数据储存流程格式

`build` 从 PDF 切分出一个 chunk：

```python
chunk = {
    "id": "S17-v8.2-15.2.2-clause-part-01",
    "section": "15.2.2",
    "parent_titles": [
        "15. COMMUNICATIONS SECURITY",
        "15.2. Information Transfer",
    ],
    "text": "CONFIDENTIAL/RESTRICTED information shall be encrypted...",
    "metadata": {
        "document": "S17",
        "version": "8.2",
        "pdf_page_start": 39,
        "printed_page_start": "33",
    },
}
```

传给 `embedded_api` 的文字只使用 `section`、`parent_titles` 和 `text`：

```text
Section: 15.2.2
Parent sections: 15. COMMUNICATIONS SECURITY > 15.2. Information Transfer
Text: CONFIDENTIAL/RESTRICTED information shall be encrypted...
```

`embedded_api` 返回 `vector` 后，`build` 组成写入数据库的 `record`。`parent_titles` 在 metadata 中转为文字，避免把 Python list 直接写入 ChromaDB：

```python
record = {
    "id": "S17-v8.2-15.2.2-clause-part-01",
    "text": "CONFIDENTIAL/RESTRICTED information shall be encrypted...",
    "metadata": {
        "section": "15.2.2",
        "parent_titles": "15. COMMUNICATIONS SECURITY > 15.2. Information Transfer",
        "document": "S17",
        "version": "8.2",
        "pdf_page_start": 39,
        "printed_page_start": "33",
    },
}

vector_store.store_vector(record, vector)
```

---

<!-- 在此开始继续记录学习笔记。 -->
