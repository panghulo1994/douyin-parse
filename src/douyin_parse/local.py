"""本地文件模式：不开浏览器、不联网，直接转录音视频。"""

from __future__ import annotations

import json
import subprocess
import time
import wave
from pathlib import Path

from . import ai
from .ai import call_ai_analysis, normalize_extracted_text, regex_punctuation, restore_punctuation
from .config import Config
from .correct import correct_transcript, save_correction_report
from .naming import fmt_duration, safe_name
from .render import build_analysis_md
from .transcribe import pick_backend, transcribe_file


def _wav_seconds(path: Path) -> float:
    try:
        with wave.open(str(path), "rb") as handle:
            return handle.getnframes() / float(handle.getframerate() or 16000)
    except Exception:
        return 0.0


def _extract_audio(cfg: Config, source: Path, target: Path) -> bool:
    if not cfg.ffmpeg:
        return False
    cmd = [
        cfg.ffmpeg,
        "-i", str(source),
        "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        str(target), "-y",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return proc.returncode == 0 and target.exists()


def run_local(cfg: Config) -> int:
    source = Path(cfg.input_file).expanduser()
    if not source.is_file():
        print(f"错误: 文件不存在 - {source}")
        return 2

    backend = pick_backend(cfg.transcribe_backend)
    if not backend:
        print("错误: 没有可用的转录后端，先 pip install openai-whisper（或 faster-whisper）")
        return 2

    started = time.time()
    out_dir = Path(cfg.output_base) / f"{safe_name(source.stem)}_{time.strftime('%Y%m%d')}"
    out_dir.mkdir(parents=True, exist_ok=True)
    audio = out_dir / "audio.wav"

    print(f"=== 本地转录 ===\n文件: {source}")
    if not _extract_audio(cfg, source, audio):
        if source.suffix.lower() == ".wav":
            audio = source
        else:
            print("错误: ffmpeg 转换失败，请确认 ffmpeg 可用（dyparse doctor）")
            return 1

    duration = _wav_seconds(audio) if audio.suffix.lower() == ".wav" else 0.0
    print(f"  音频: {fmt_duration(duration) or '未知'} | 后端: {backend} | 模型: {cfg.whisper_model}")

    try:
        transcription = transcribe_file(audio, model=cfg.whisper_model, backend=backend)
    except Exception as exc:
        print(f"错误: 转录失败 - {exc}")
        return 1

    transcript_raw = normalize_extracted_text(transcription.text)
    if ai.AI_ENABLED:
        transcript = restore_punctuation(transcript_raw)
    else:
        transcript = regex_punctuation(transcript_raw)

    correction = correct_transcript(transcript)
    transcript = correction["corrected"]
    if correction["stats"]["total_corrections"]:
        save_correction_report(correction, out_dir / "修订报告.md")

    analysis = ""
    if ai.AI_ENABLED:
        analysis = call_ai_analysis(transcript, "视频", source.stem, "", duration, [], "") or ""
    if not analysis:
        analysis = "⚠️ AI 分析暂时不可用（API 未配置或调用失败）"

    (out_dir / "文案.txt").write_text(transcript, encoding="utf-8")
    (out_dir / "文案_分析版.md").write_text(
        build_analysis_md(
            transcript,
            analysis,
            "视频",
            duration,
            title=source.stem,
            parsed_at=time.strftime("%Y-%m-%d %H:%M"),
            elapsed=time.time() - started,
        ),
        encoding="utf-8",
    )
    (out_dir / "info.json").write_text(
        json.dumps(
            {
                "source": str(source),
                "title": source.stem,
                "content_type": "本地文件",
                "duration": round(duration, 2),
                "backend": transcription.backend,
                "model": transcription.model,
                "transcript": transcript,
                "transcript_raw": transcript_raw,
                "ai_reliability_analysis": analysis,
                "ocr_texts": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\n=== 完成 ({time.time() - started:.1f}秒) ===")
    print(f"输出: {out_dir}")
    return 0
