"""ASR 文案修订：长词优先替换 + 白名单防误改。"""
import json
import re
from pathlib import Path

_DATA = json.loads((Path(__file__).with_name("corrections.json")).read_text(encoding="utf-8"))
CORRECTIONS = _DATA["corrections"]
KEEP_AS_IS = _DATA["keep_as_is"]


def correct_transcript(text: str) -> dict:
    """
    修订转录文本，返回修订结果
    """
    original = text
    corrections_made = []
    corrected_text = text
    
    # 按错误长度排序（长的优先，避免短词误匹配）
    sorted_corrections = sorted(
        CORRECTIONS.items(), 
        key=lambda x: len(x[0]), 
        reverse=True
    )
    
    for wrong, right in sorted_corrections:
        if wrong in corrected_text:
            # 检查是否在KEEP_AS_IS列表中
            if any(keep in wrong for keep in KEEP_AS_IS):
                continue
                
            # 计数并替换
            count = corrected_text.count(wrong)
            if count > 0:
                corrected_text = corrected_text.replace(wrong, right)
                corrections_made.append({
                    "wrong": wrong,
                    "right": right,
                    "count": count
                })
    
    # 二次修正：处理重叠替换（如"开开源项目"→"开源项目"）
    if "开开源项目" in corrected_text:
        corrected_text = corrected_text.replace("开开源项目", "开源项目")

    # 断句优化：在特定标点后添加句号
    sentence_endings = [
        (r'([。！？])([a-zA-Z\u4e00-\u9fff])', r'\1\n\2'),  # 句号后换行
        (r'([。！？])\s*([a-zA-Z\u4e00-\u9fff])', r'\1\n\2'),  # 去掉多余空格
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
            "corrected_length": len(corrected_text)
        }
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
|---------|--------|----------|
"""
    
    for correction in result['corrections']:
        report += f"| {correction['wrong']} | {correction['right']} | {correction['count']} |\n"
    
    report += f"""
## 修订后文案

{result['corrected']}
"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    return report
