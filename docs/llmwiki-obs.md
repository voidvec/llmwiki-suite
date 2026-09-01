# llmwiki-suite 曝光监控（Observability, D4）

> 实施合同 D4 · W1 交付 · 作者侧观测（作者可见的公开指标，非用户行为追踪）

## 是什么

每天 1 次抓取两个公开源的指标，落盘成可追溯的 stats 文件，供周报自动汇总与长期趋势对比：

| 来源 | 抓什么 | 数据源 |
|------|--------|--------|
| PyPI | 下载量（last_day / last_week / last_month） | pypistats 公开 API |
| GitHub | star / fork / open issues / open PRs / latest release | GitHub 公开 REST API |

全部**零第三方依赖**（仅标准库 `urllib.request`/`json`/`csv`），限流/网络失败**逐项降级**，不因单一来源失败而中断。

## 3 步使用

```bash
# 1. 只抓 GitHub（单测 / 快速查）
python scripts/fetch_github_stats.py --out stats/github-daily.json

# 2. 每日快照：合并 PyPI + GitHub，写 stats/llmwiki-obs-YYYY-MM-DD.json + 追加 daily-series.csv
python scripts/obs_daily_snapshot.py --out-dir stats

# 3. 看结果 / 周报汇总
ls stats/                        # 逐日 JSON 快照（可追溯）
cat stats/daily-series.csv       # 时序序列，直接可画趋势图
```

## 设计与降级约定

- **幂等**：同日多次运行 `obs_daily_snapshot.py` 会**覆盖**当日 CSV 行，不产生重复行。
- **降级**：任一来源 429/断网 → 该字段记 `null`/空，错误写进 JSON 的 `error` 字段，脚本退出码仍为 0（不误报），全部来源都失败才返回非 0。
- **GitHub 无 token**：公开 API 限流 60 次/小时，每次抓取仅 4 个请求，单日 1 次绰绰有余；若要更稳可 `--token ghp_xxx`（5000 次/小时）。当前 repo 公开，基础字段无需认证。
- **PyPI 429**：pypistats 对同一 IP 短时限流较严（实测连续调用会出现 `HTTP 429`），脚本内置 1s 间隔 + 降级，重试即可补回。

## 周报自动汇总（D12 联动）

周报模板（`docs/weekly-report-template.md`）外部信号栏直接引用 `stats/daily-series.csv` 最近 7 行：star / fork / issue / PR / 下载趋势。并入「周二 PT」周复盘流程。