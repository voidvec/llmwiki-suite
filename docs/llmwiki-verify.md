# LLMWiki 知识库重建流程

## 用户资产说明

> **这是「用户资产」**：`llmwiki.toml` / `eval_queries.json` / `README.md` / 全部 `.md` —— **千万别删！**

下面脚本只会删除可再生成产物，由命令重建，不会触碰上述用户资产。

---

## 1. 删除可再生成产物（不留库，由命令重建）

```bash
cd /d/work/development/Repos/docs/knowledge-base/knowledge-base

rm -f kb-index.json category-index.md ingest-report.json lint-report.json
rm -rf eval_reports
```
---

## 2. 用与套件一致的 Python 建 venv（3.13，套件 .venv 用的版本）

```bash
python -m venv .venv
```

### Windows:

```bash
.venv\Scripts\activate
```

### macOS / Linux:

```bash
source .venv/bin/activate
```

---

## 3. 在 knowledge-base 的 .venv 里安装本地最新套件 + serve 依赖

> 本质相当于 `pip install -e .[serve]`，但指向套件源码目录。

```bash
pip install -e "D:\work\development\Repos\docs\llmwiki-suite[serve]"
```

---

## 4. 验证安装（editable 指向本地源码 + 版本 + CLI 8 命令）

```bash
llmwiki --version
llmwiki --help
```

---

## 5. init —— 生成/检测 llmwiki.toml（已有则跳过，不会覆盖）

### Windows:

```bash
llmwiki init
```

---

## 6. ingest dry-run —— 先看计划，不要急着 `--apply`

```bash
llmwiki ingest
```

---

## 7. （确认计划无误后）真正执行：规范化 65 个文件名（Drogon 教程全角冒号 → 连字符）

```bash
# 秒级，跳过 LLM（改文件名/补 FM 照常）
llmwiki ingest --apply --no-llm

# 想补分类：只对缺类目/缺标签的文件调，单次、带总超时
llmwiki ingest --apply
```

> 注意：这条之前静默退出码 1 是因为当时 venv 正在被删、python 环境不完整；
> 你全新 venv 应该能过。若仍失败，把报错发我。

---

## 8. index（建 BM25 + 链接图）

```bash
llmwiki index
```

---

## 9. lint（健康巡检，预期 errors=0 / warnings=0）

```bash
llmwiki lint
```

---

## 10. categories-sync（词表自愈，先 dry-run 后 `--apply`）

```bash
llmwiki categories-sync
llmwiki categories-sync --apply
```

---

## 11. eval（用你自己的评估集测召回）

```bash
llmwiki eval
```

若要用自定义评估集：

```bash
llmwiki eval --queries eval_queries.json
```
