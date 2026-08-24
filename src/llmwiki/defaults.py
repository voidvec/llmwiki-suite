# -*- coding: utf-8 -*-
"""套件默认值（三层配置模型的底层：套件默认 → 用户 llmwiki.toml → 环境变量）。

刻意与 config.py 分离：本模块只有常量，无 I/O，方便测试与文档引用。
"""

# 排除目录基础集：引擎/编辑器/运行时目录，任何知识库都不应索引。
# 用户可通过 llmwiki.toml 的 [ingest].extra_exclude 追加（见 config.py 合并语义）。
DEFAULT_EXCLUDE_DIRS = {
    ".git", ".workbuddy", "Excalidraw", "Templates", "scripts",
    ".claudian", ".claude", ".obsidian", ".idea", ".vscode", ".venv",
    "templates", "node_modules", "eval_reports",
}

# 受控 categories 默认小词表（通用、面向个人知识管理的起点）。
# 用户应在 llmwiki.toml 的 [categories].allowed 覆盖为自己的词表（整体替换）。
# 注意：「导航索引」是 gen_index 生成的 category-index.md 专用类别，必须保留在词表内，
# 否则新用户首次 lint 就会因生成产物报词表越界。
DEFAULT_CATEGORIES = [
    "知识库规范", "软件架构", "会议纪要", "读书笔记",
    "工具指南", "参考手册", "导航索引",
]

# LLM 非密钥默认值（LLM_API_KEY 只走环境变量，绝不写进任何文件）。
DEFAULT_LLM_BASE_URL = "https://api.openai.com/v1"
DEFAULT_LLM_MODEL = "gpt-4o-mini"

# 检索参数默认值（与个人库调优后的生产值一致，见 docs/tutorial-03）
DEFAULT_MIN_SCORE = 0.15
DEFAULT_TOP_K = 6

# 默认别名组（P1）：组内变体视为同义，打分时短语级**双向扩展**（追加、不改原文）。
# 解决词法检索的中英/缩写语义失配（如查「系统架构」命不中标题为 architecture 的文档）。
# 用户通过 llmwiki.toml 的 [aliases].groups 在此之上**追加**自定义组（见 config.py）。
# 原则：只放高频通用组，宁缺勿滥——组内变体会互相注入文档 token，过泛会稀释 idf 判别力。
DEFAULT_ALIAS_GROUPS = [
    ["kubernetes", "k8s"],
    ["end-to-end", "e2e", "端到端"],
    ["系统架构", "architecture"],
    ["可观测性", "observability"],
    ["反向代理", "reverse-proxy"],
]
