"""
video_ocr.py - 视频画面文字提取模块
从视频中每隔固定间隔截取帧，用OCR提取画面上的文字（字幕/标题/标签等）
"""
import os
import subprocess
import tempfile
import sys


def pick_texts(result, min_conf: float = 0.5, min_len: int = 2) -> list[str]:
    """把 RapidOCR 的原始结果转成文字列表。

    某些版本的 conf 是字符串（'0.79'），直接和 float 比较会抛异常，
    早期代码用 try/except 吞掉，导致整段 OCR 静默返回空。
    """
    texts = []
    for item in result or []:
        try:
            text = str(item[1]).strip()
            conf = float(item[2])
        except (TypeError, ValueError, IndexError):
            continue
        if len(text) >= min_len and conf > min_conf:
            texts.append(text)
    return texts


def extract_text_from_video(video_path: str, ffmpeg_path: str, interval: float = 1.0, max_frames: int = 60) -> list[str]:
    """
    从视频中提取画面文字
    
    Args:
        video_path: 视频文件路径
        ffmpeg_path: ffmpeg可执行文件路径
        interval: 截帧间隔（秒），默认1秒
        max_frames: 最大截帧数，默认60
    
    Returns:
        去重后的文字列表，按出现顺序排列
    """
    if not os.path.exists(video_path):
        print(f"  [OCR] 视频文件不存在: {video_path}")
        return []
    
    # 创建临时目录存放帧图片
    frames_dir = tempfile.mkdtemp(prefix='ocr_frames_')
    
    try:
        # 用ffmpeg每隔interval秒截取一帧
        fps_filter = f'fps=1/{interval}'
        cmd = [
            ffmpeg_path, '-i', video_path,
            '-vf', fps_filter,
            '-frames:v', str(max_frames),
            '-y',
            os.path.join(frames_dir, 'frame_%04d.png')
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, encoding='utf-8', errors='replace')
        
        if result.returncode != 0:
            print(f"  [OCR] ffmpeg截帧失败: {result.stderr[:100]}")
            return []
        
        # 列出截取的帧
        frames = sorted([
            os.path.join(frames_dir, f) 
            for f in os.listdir(frames_dir) 
            if f.endswith('.png')
        ])
        
        if not frames:
            print(f"  [OCR] 未截取到任何帧")
            return []
        
        print(f"  [OCR] 截取了 {len(frames)} 帧，开始识别...")
        
        # 初始化RapidOCR
        try:
            from rapidocr_onnxruntime import RapidOCR
            engine = RapidOCR()
        except ImportError:
            print("  [OCR] 未安装rapidocr-onnxruntime，跳过画面文字提取")
            print("  [OCR] 安装命令: uv pip install rapidocr-onnxruntime")
            return []
        except Exception as e:
            print(f"  [OCR] 初始化RapidOCR失败: {e}")
            return []
        
        # 对每一帧进行OCR
        all_texts = []
        seen_texts = set()
        
        errors = 0
        for frame_path in frames:
            try:
                result, _ = engine(frame_path)
            except Exception:
                errors += 1
                continue
            if not result:
                continue
            for text in pick_texts(result):
                if text not in seen_texts:
                    seen_texts.add(text)
                    all_texts.append(text)
        if errors:
            print(f"  [OCR] {errors} 帧识别失败，已跳过")
        
        print(f"  [OCR] 识别出 {len(all_texts)} 段独立文字")
        return all_texts
        
    finally:
        # 清理临时帧文件
        try:
            for f in os.listdir(frames_dir):
                os.remove(os.path.join(frames_dir, f))
            os.rmdir(frames_dir)
        except:
            pass


def format_ocr_output(ocr_texts: list[str]) -> str:
    """格式化OCR输出"""
    if not ocr_texts:
        return ""
    
    lines = ["## 画面文字（OCR提取）\n"]
    lines.append("以下文字从视频画面中提取，包括字幕、标题、标签、数据等：\n")
    for i, text in enumerate(ocr_texts, 1):
        lines.append(f"{i}. {text}")
    
    return "\n".join(lines)
