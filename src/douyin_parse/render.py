"""把转录、OCR 与分析结果渲染成 Markdown。"""
import json
import time

from .naming import fmt_duration


AI_SECTION_HEADS = ('📊', '✅', '💡', '⚠️')


def format_reliability_output(transcript, analysis, content_type, duration):
    """格式化可靠性分析输出"""
    word_count = len(transcript.replace(" ", ""))
    duration_str = f"{int(duration)}秒" if content_type == "视频" and duration else "N/A"

    output = []
    output.append("=" * 50)
    output.append("视频/图文文案:")
    output.append("=" * 50)
    output.append(transcript)
    output.append("")
    output.append("=" * 50)
    output.append("AI 可靠性分析:")
    output.append("=" * 50)

    if analysis:
        output.append(analysis)
    else:
        # 降级输出
        output.append("📊 基本信息")
        output.append(f"- 类型：{content_type}")
        output.append(f"- 时长：{duration_str}")
        output.append(f"- 转录字数：{word_count}字")
        output.append("")
        output.append("⚠️ AI 分析暂时不可用（API 未配置或调用失败）")

    return "\n".join(output)


def analysis_dict_to_text(d):
    """旧版 info.json 里分析可能是 dict，转成四段式纯文本再排版。"""
    lines = []
    rating = d.get('rating') or d.get('评分')
    if rating:
        lines.append("📊 基本信息")
        lines.append(f"- 评分：{rating}")
        lines.append("")
    judgments = d.get('key_judgments') or d.get('判断') or []
    if judgments:
        lines.append("✅ 内容核查")
        for item in judgments:
            lines.append(f"- {item}")
        lines.append("")
    notes = d.get('notes') or d.get('注意事项')
    if notes:
        lines.append("⚠️ 注意事项")
        lines.append(f"- {notes}")
    if not lines:
        lines.append(json.dumps(d, ensure_ascii=False, indent=2))
    return "\n".join(lines)


def mdify_analysis(text):
    """把 AI 分析里的 emoji 段落头升级为 Markdown 三级标题，正文文字一律不动。"""
    if isinstance(text, dict):
        text = analysis_dict_to_text(text)
    elif isinstance(text, (list, tuple)):
        text = "\n".join(f"- {x}" for x in text)
    elif text is None:
        text = ""
    out = []
    for line in (text or '').splitlines():
        s = line.strip()
        if s and any(s.startswith(h) for h in AI_SECTION_HEADS) and len(s) <= 20:
            out.append(f"### {s}")
        else:
            out.append(line)
    return "\n".join(out).strip()


def build_analysis_md(transcript, analysis, content_type, duration,
                      title=None, tags=None, author=None, url=None,
                      ocr_count=0, ocr_file=None, elapsed=None, parsed_at=None):
    """生成新版式：标题 + 元信息表 + 正文 + AI 可靠性分析。内容一个字不改。"""
    word_count = len((transcript or '').replace(" ", ""))
    lines = []
    lines.append(f"# {title or '未命名'}")
    if tags:
        lines.append("")
        tag_text = " ".join(tags) if isinstance(tags, (list, tuple)) else str(tags)
        lines.append(tag_text)
    lines.append("")
    lines.append("| 项目 | 内容 |")
    lines.append("| --- | --- |")
    if author:
        lines.append(f"| 作者 | {author} |")
    lines.append(f"| 类型 | {content_type} |")
    if content_type == "视频":
        lines.append(f"| 时长 | {fmt_duration(duration)} |")
    lines.append(f"| 转录 | {word_count} 字 |")
    if ocr_count:
        where = f"（另存于 `{ocr_file}`）" if ocr_file else ""
        lines.append(f"| 画面文字 | {ocr_count} 段{where} |")
    lines.append(f"| 解析日期 | {parsed_at or time.strftime('%Y-%m-%d %H:%M')} |")
    if elapsed:
        lines.append(f"| 总耗时 | {fmt_duration(elapsed)} |")
    if url:
        lines.append(f"| 原链接 | {url} |")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 正文")
    lines.append("")
    lines.append(transcript or "")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## AI 可靠性分析")
    lines.append("")
    if analysis:
        lines.append(mdify_analysis(analysis))
    else:
        lines.append("⚠️ AI 分析暂时不可用（API 未配置或调用失败）")
        lines.append("")
        lines.append(f"- 类型：{content_type}")
        if content_type == "视频":
            lines.append(f"- 时长：{fmt_duration(duration)}")
        lines.append(f"- 转录字数：{word_count}字")

    return "\n".join(lines) + "\n"


def build_ocr_md(title, ocr_texts, url=None):
    """画面文字单独成文件，避免挤占正文。"""
    lines = []
    lines.append(f"# {title or '未命名'} · 画面文字（OCR 提取）")
    lines.append("")
    lines.append(f"> 共 {len(ocr_texts)} 段。从视频画面里抓到的文字，用来补人名、数据、产品名。")
    if url:
        lines.append(">")
        lines.append(f"> 原链接：{url}")
    lines.append("")
    for i, t in enumerate(ocr_texts, 1):
        lines.append(f"{i}. {t}")
    return "\n".join(lines) + "\n"
