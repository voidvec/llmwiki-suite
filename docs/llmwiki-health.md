# llmwiki health — 健康分（0-100）参考

> 状态：**经验版 Beta**（v0.1）— 定性「健康度参考值」，非质量标准。
> 面向：quick glance / CI 观察 / 趋势追踪。**不阻断**（阻断用 `llmwiki lint`）。

`llmwiki health` 把一个知识库的健康度压缩成 **0-100 的单一分数** + 分项，
输出 JSON（机器可读）+ HTML（自包含可视化，零依赖、无图表库）。

```bash
llmwiki health                # 只打印分数（默认 CWD/--repo 解析库）
llmwiki health --out-dir ./reports   # 双写 health-report.json + .html
llmwiki health --no-json       # 只出 HTML
```

## 三条规则（MVP 版）

| 规则 | 权重 | 计算口径 |
|------|------|----------|
| 文档完整性（meta） | 40% | frontmatter 必填字段（title/description/tags/difficulty）齐全率 + 正文非空 |
| 链接健壮性（link） | 40% | wikilink + 相对 md 链接解析成功率（判死口径对齐 lint）；外部/锚点链接不判 |
| 元数据新鲜度（fresh） | 20% | 90 天内有 updated/date/modified 的文档占比 |

字母档：A ≥90 · B ≥75 · C ≥60 · D <60 · F 空库。

## JSON 结构

```jsonc
{
  "schema": "llmwiki.health.v1",
  "generated_at": "ISO-8601",
  "repo": "绝对路径",
  "score": 98,            // 0-100
  "grade": "A",
  "rules": { "meta": {"score":100,"weight":0.4}, "link": {...}, "fresh": {...} },
  "counts": { "files": 4, "links": 4 },
  "issues": {            // 前 50 条/类
    "fm":    [{"file","detail"}],
    "link":  [{"file","detail","type"}],
    "fresh": [{"file","detail"}]
  },
  "notes": { "overall": "...", "rule_issues": [...] }
}
```

## 与 lint 的区别

| | `llmwiki lint` | `llmwiki health` |
|---|---|---|
| 定位 | 阻断式巡检（errors>0 → 退出码 1） | 趋势式健康度量（分数 + 分项） |
| 用途 | pre-commit / CI 门禁 | 人/CI 观察、健康基线 |
| 判死 | 断链即报 | 断链只折算分数损失 |

## 设计约束

- **零第三方依赖**：仅标准库 + kb_core/config。
- **离线可跑**：无网络、无 LLM 调用。
- **全匿名**：不读取/上传任何行为数据（用户侧；作者侧观测见 `scripts/fetch_pypi_stats.py`）。

## 演进

- 规则 ≥6 版（引用度/内容陈旧/术语覆盖）属 Phase 2（Q1），由「健康分被外部真实使用」触发。