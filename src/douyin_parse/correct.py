"""ASR 文案修订：单趟替换（长词优先）+ 白名单防误改。

早期实现是按"长词优先"逐条 `str.replace`，后一条规则会看到前一条规则的产物，
于是出现两类问题：
  1. 规则互相污染：`SOTA → SOTA（State-of-the-Art）` 再被同一条规则追加一次，
     变成 `SOTA（…）（…）`；`FD → FDE` 把已经正确的 `FDE` 再补一个 `E`。
  2. 回调链：`大摩 → 大模型` 之类会被后续更短的规则二次改写。

现在改成**单趟正则替换**：每个位置只匹配一次、只替换一次，规则之间互不可见。
另外加了"窗口守卫"——如果命中位置已经处在完整的"目标形态"里（例如原文就是
`FDE`、`开源项目`、`《女儿红》`），就保持原样，避免套娃。
"""
import json
import re
from pathlib import Path

_DATA = json.loads((Path(__file__).with_name("corrections.json")).read_text(encoding="utf-8"))
CORRECTIONS = _DATA["corrections"]
KEEP_AS_IS = _DATA["keep_as_is"]


def _usable_pairs() -> list[tuple[str, str]]:
    """过滤掉空条目和白名单命中的条目，并按长度倒序（保证同一起点取最长匹配）。"""
    pairs = [
        (wrong, right)
        for wrong, right in CORRECTIONS.items()
        if isinstance(wrong, str) and isinstance(right, str) and wrong and right
    ]
    pairs = [
        (wrong, right)
        for wrong, right in pairs
        if not any(keep in wrong for keep in KEEP_AS_IS)
    ]
    pairs.sort(key=lambda item: len(item[0]), reverse=True)
    return pairs


_PAIRS = _usable_pairs()
_MAPPING = dict(_PAIRS)
_PATTERN = re.compile("|".join(re.escape(wrong) for wrong, _ in _PAIRS)) if _PAIRS else None


def _already_in_target_form(text: str, start: int, end: int, right: str) -> bool:
    """命中位置是否已经处在完整的目标形态里（用于防止注解/包裹类规则套娃）。

    只在"目标值里含有原始错误词"时才检查，例如：
      SOTA  → SOTA（State-of-the-Art）
      女儿红 → 《女儿红》
      开源项目 ← 源项目
    """
    window = text[max(0, start - len(right)):end + len(right)]
    return right in window


def correct_transcript(text: str) -> dict:
    """修订转录文本，返回修订结果。"""
    original = text
    counts: dict[str, int] = {}

    if _PATTERN is None:
        corrected_text = text
    else:
        def _replace(match: re.Match) -> str:
            wrong = match.group(0)
            right = _MAPPING[wrong]
            if wrong in right and _already_in_target_form(
                text, match.start(), match.end(), right
            ):
                return wrong
            counts[wrong] = counts.get(wrong, 0) + 1
            return right

        corrected_text = _PATTERN.sub(_replace, text)

    # 仍保留兜底：历史顺序替换可能残留的重叠形态
    if "开开源项目" in corrected_text:
        corrected_text = corrected_text.replace("开开源项目", "开源项目")

    corrections_made = [
        {"wrong": wrong, "right": _MAPPING[wrong], "count": counts[wrong]}
        for wrong in sorted(counts, key=len, reverse=True)
    ]

    # 断句优化：在特定标点后换行
    sentence_endings = [
        (r'([。！？])([a-zA-Z\u4e00-\u9fff])', r'\1\n\2'),
        (r'([。！？])\s*([a-zA-Z\u4e00-\u9fff])', r'\1\n\2'),
    ]
    for pattern, replacement in sentence_endings:
        corrected_text = re.sub(pattern, replacement, corrected_text)

    return {
        "original": original,
        "corrected": corrected_text,
        "corrections": corrections_made,
        "stats": {
            "total_corrections": len(corrections_made),
            "original_length": len(original),
            "corrected_length": len(corrected_text),
        },
    }


def save_correction_report(result: dict, output_path: Path):
    """保存修订报告"""
    report = f"""# 文案修订报告

## 修订统计
- 原始字数：{result['stats']['original_length']}
- 修订后字数：{result['stats']['corrected_length']}
- 修正处数：{result['stats']['total_corrections']}

## 修正说明表

| 原始错误 | 修正后 | 出现次数 |
|---------|--------|--------|
"""

    for correction in result["corrections"]:
        report += f"| {correction['wrong']} | {correction['right']} | {correction['count']} |\n"

    report += f"""
## 修订后文案

{result['corrected']}
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    return report
