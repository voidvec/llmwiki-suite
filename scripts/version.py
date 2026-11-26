#!/usr/bin/env python3
"""版本号单一真源：定向同步 + 一致性门禁（stdlib，零第三方依赖）。

真源只有一个：``pyproject.toml`` 的 ``[project].version``。

本脚本把「必须跟着版本走」的落点与真源对齐，并对「由人撰写但必须一致」的落点做校验。
刻意**不做**全仓正则替换——同一个版本号在文档里至少有三种语义（当前版本 / 历史事实 /
版本线叙述），全局替换必然误伤后两者。因此每个落点都写成一条锚定规则。

用法（仓库根目录执行）::

    python scripts/version.py --check                 # 门禁：不一致则退出码 1
    python scripts/version.py --next patch            # 打印下一个版本号
    python scripts/version.py --set 0.1.9             # 预览 diff（dry-run，不写盘）
    python scripts/version.py --set 0.1.9 --apply --date 2026-11-27
    python scripts/version.py --check-tag v0.1.9      # 发版门禁：tag 与版本号一致
"""

from __future__ import annotations

import argparse
import datetime
import difflib
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMVER = r"\d+\.\d+\.\d+"


# ---------------------------------------------------------------- 落点规则

@dataclass(frozen=True)
class Target:
    """一个版本落点。

    pattern 必须**恰好含一个捕获组**，捕获组内容即版本号——这样 --set 只替换该组，
    前后文（日期、标点、说明文字）原样保留。
    """

    rel: str
    pattern: str
    label: str
    writable: bool = True


def targets() -> tuple[Target, ...]:
    return (
        Target("pyproject.toml", rf'(?m)^version = "({SEMVER})"', "真源 pyproject"),
        Target(
            "src/llmwiki/__init__.py",
            rf'(?m)^__version__ = "({SEMVER})"',
            "包内 __version__（--version 读它）",
        ),
        Target(
            "docs/getting-started.md",
            rf"`llmwiki-suite ({SEMVER})`",
            "getting-started 发布状态行",
        ),
        Target(
            "docs/getting-started.md",
            rf"llmwiki-suite\[serve\]==({SEMVER})",
            "getting-started 安装锁定版本",
        ),
        # 以下两处由人写正文，脚本只校验不顺带改
        Target(
            "CHANGELOG.md",
            rf"(?m)^## \[({SEMVER})\]",
            "CHANGELOG 最新段头",
            writable=False,
        ),
        Target(
            "docs/project-records/00-canonical-baseline.md",
            rf"(?m)^\| 当前版本 \| `({SEMVER})`",
            "基准台账「当前版本」行",
            writable=False,
        ),
    )


# 负向检查：收缩后的漂移面不允许回潮。
# 1) 锁定版本只允许出现在 getting-started（读者要能复制粘贴）；
# 2) 「版本线已推进到 X.Y.Z」这种把当前版本写进计划文档的叙述一律禁止。
PIN_RX = re.compile(rf"llmwiki-suite\[serve\]==({SEMVER})")
PIN_ALLOW = {"docs/getting-started.md"}
NARRATIVE_RX = re.compile(rf"版本线已推进到 `?({SEMVER})`?")
SCAN_GLOBS = (
    "*.md",
    "docs/**/*.md",
    "deliverables/**/*.md",
    "knowledge-base/**/*.md",
    ".github/**/*.yml",
)


# ---------------------------------------------------------------- 读写工具

def read_text(rel: str) -> str:
    # newline="" 保留原始换行，避免 Windows 工作区被整篇改成 LF
    with (ROOT / rel).open(encoding="utf-8", newline="") as fh:
        return fh.read()


def write_text(rel: str, text: str) -> None:
    with (ROOT / rel).open("w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def source_version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as fh:
        return tomllib.load(fh)["project"]["version"]


def find_value(text: str, target: Target) -> tuple[str | None, re.Match[str] | None]:
    m = re.search(target.pattern, text)
    return (m.group(1) if m else None), m


def bump_semver(version: str, part: str) -> str:
    major, minor, patch = (int(x) for x in version.split("."))
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


# ---------------------------------------------------------------- 命令实现

def cmd_check() -> int:
    current = source_version()
    print(f"真源 pyproject.toml: {current}\n")

    problems: list[str] = []
    for t in targets():
        if t.rel == "pyproject.toml":
            ok, found = True, current
        else:
            found, match = find_value(read_text(t.rel), t)
            ok = found == current
            if match is None:
                found = "<未匹配到锚点>"

        mark = "OK  " if ok else "FAIL"
        detail = "" if ok else f"  <- 应为 {current}"
        if found is None and ok:
            found = current
        print(f"{mark} {t.rel:<47} {t.label:<28} {found}{detail}")
        if not ok:
            problems.append(f"{t.rel}（{t.label}）：{found}，应为 {current}")

    # 漂移面回潮检查
    for pattern in SCAN_GLOBS:
        for path in sorted(ROOT.glob(pattern)):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT).as_posix()
            text = read_text(rel)
            if rel not in PIN_ALLOW:
                for m in PIN_RX.finditer(text):
                    problems.append(f"{rel}: 锁定版本 {m.group(1)} 只允许出现在 getting-started")
            for m in NARRATIVE_RX.finditer(text):
                problems.append(f"{rel}: 「版本线已推进到 {m.group(1)}」应改为指向基准 §0.1")

    print()
    if problems:
        for p in problems:
            print(f"FAIL {p}")
        print(f"\n{len(problems)} 处不一致")
        return 1
    print("全部一致")
    return 0


def cmd_set(new: str, apply: bool, date: str | None) -> int:
    if not re.fullmatch(SEMVER, new):
        print(f"FAIL 版本号格式不合法：{new}（需 X.Y.Z）", file=sys.stderr)
        return 2

    current = source_version()
    if new == current:
        print(f"版本号未变（{current}），无事可做")
        return 0

    # 同一文件可能有多条规则（getting-started 有 2 处）：必须在**累积文本**上顺序替换，
    # 否则后一条规则会用原文件内容覆盖前一条的结果。
    originals: dict[str, str] = {}
    working: dict[str, str] = {}
    order: list[str] = []

    for t in targets():
        if not t.writable:
            continue
        if t.rel not in working:
            originals[t.rel] = working[t.rel] = read_text(t.rel)
            order.append(t.rel)
        found, match = find_value(working[t.rel], t)
        if match is None:
            print(f"FAIL {t.rel}（{t.label}）：没找到锚点，跳过", file=sys.stderr)
            continue
        start, end = match.span(1)
        working[t.rel] = working[t.rel][:start] + new + working[t.rel][end:]

    # 发布日期：只在显式给出时更新 getting-started 的发布状态行
    if date and "docs/getting-started.md" in working:
        working["docs/getting-started.md"] = re.sub(
            r"(套件已发布到 PyPI\*\*（`llmwiki-suite " + re.escape(new) + r"`，)\d{4}-\d{2}-\d{2}",
            lambda m: m.group(1) + date,
            working["docs/getting-started.md"],
        )

    print(f"{current} -> {new}\n")
    for rel in order:
        diff = list(
            difflib.unified_diff(
                originals[rel].splitlines(keepends=True),
                working[rel].splitlines(keepends=True),
                fromfile=f"a/{rel}",
                tofile=f"b/{rel}",
                n=1,
            )
        )
        sys.stdout.writelines(diff)
        if diff and not diff[-1].endswith("\n"):
            print()
        print()

    if not apply:
        print("（dry-run，未写盘；确认后加 --apply）")
        return 0

    for rel in order:
        write_text(rel, working[rel])
    print(f"已写入 {len(order)} 个文件：{', '.join(order)}")
    print(
        "\n仍需人工补齐：\n"
        f"  1. CHANGELOG.md 加 `## [{new}] - YYYY-MM-DD` 段（--check 会校验段头）\n"
        "  2. docs/project-records/00-canonical-baseline.md 的「当前版本 / 版本 tag / 时间线」\n"
        "  3. 提交后打 tag，release.yml 会先校验 tag 与版本号一致再发版"
    )
    return 0


def cmd_check_tag(tag: str) -> int:
    current = source_version()
    expected = f"v{current}"
    if tag != expected:
        print(
            f"FAIL tag {tag} 与 pyproject 版本 {current} 不一致（应为 {expected}）\n"
            "     拒绝发版：先确认 pyproject.toml 已升到目标版本，再重新打 tag。",
            file=sys.stderr,
        )
        return 1
    print(f"OK   tag {tag} 与 pyproject 版本一致")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="版本号单一真源：定向同步与一致性门禁",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="校验全部落点一致（门禁）")
    group.add_argument("--set", metavar="X.Y.Z", help="把版本号设为指定值")
    group.add_argument("--next", choices=("patch", "minor", "major"), help="打印下一个版本号")
    group.add_argument("--check-tag", metavar="TAG", help="校验 tag 与版本号一致（发版门禁）")
    parser.add_argument("--apply", action="store_true", help="配合 --set：真正写盘")
    parser.add_argument(
        "--date",
        metavar="YYYY-MM-DD",
        help="配合 --set：同步 getting-started 的发布日（默认不动）",
    )
    args = parser.parse_args(argv)

    if args.check:
        return cmd_check()
    if args.next:
        print(bump_semver(source_version(), args.next))
        return 0
    if args.check_tag:
        return cmd_check_tag(args.check_tag)
    if args.set:
        if args.date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date):
            parser.error("--date 需为 YYYY-MM-DD")
        if args.date and args.date > datetime.date.today().isoformat():
            print(f"提醒：--date {args.date} 晚于今天，确认不是笔误", file=sys.stderr)
        return cmd_set(args.set, args.apply, args.date)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
