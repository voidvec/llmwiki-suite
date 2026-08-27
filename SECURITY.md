# Security Policy

## 报告漏洞

**发现安全问题，请不要开公开 Issue。** 优先通过 GitHub 的
[Private vulnerability reporting](https://github.com/voidvec/llmwiki-suite/security/advisories)
提交，或私有方式联系维护者（[voidvec](https://github.com/voidvec)）。

我们会：

1. 48 小时内确认收到；
2. 评估影响范围与是否已发布版本受影响；
3. 修复后统一发布公告（含受影响版本与缓解措施）。

## 安全设计底线（本套件自身）

- **密钥只走环境变量**：套件不读取任何 `.env` 文件，也不把密钥写进
  `llmwiki.toml` / README / 示例。涉及密钥的新功能必须延续这一约定。
- **丢到公网的通道服务默认受保护**：`llmwiki serve` 若暴露在公网，请设置
  `LLM_WIKI_BRIDGE_TOKEN` 保护问答接口；Telegram / 飞书 webhook 回调用各自的
  `*_SECRET_TOKEN` / `*_VERIFY_TOKEN` 做签名校验。
- **推理预算熔断**：`llmwiki ingest --apply` 的 LLM 推断有**全局总超时**（默认 600s，env
  `LLM_WIKI_INGEST_LLM_TOTAL_TIMEOUT` 可调），防止慢 API / 意外批量调用造成无界费用；
  不需要推断时可加 `--no-llm` 完全跳过（离线秒级）。
- **最小权限原则**：工具只操作你指定的笔记库（`--repo` 指向），不扫系统目录。

## 你的笔记库安全

- `kb-index.json` 等产物不进版本库（脚手架已配 `.gitignore`）。
- 正在写入的 Markdown 由 `llmwiki ingest` 处理——改动前建议在分支 / 版本控制下操作，
  因为它可能批量改写 frontmatter 与 wikilink（第一次跑可先 `--dry-run` 或备份）。
- 把服务暴露公网前，先读 `docs/tutorials/llmwiki-tutorial-02-channel.md` 的部署建议。

## 受支持版本

| 版本 | 支持状态 |
|------|----------|
| 最新 release | ✅ 安全修复 |
| 历史版本 | ⛔ 仅影响面极小时修复 |

## 服务器端

本项目无自有服务器端组件；`llmwiki serve` 运行在你自己的机器上，
安全边界由部署方负责（TLS、反代、防火墙）。