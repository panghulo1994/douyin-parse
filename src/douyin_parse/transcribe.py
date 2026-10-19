"""语音转录：openai-whisper 与 faster-whisper 双后端。

faster-whisper 走 CTranslate2，CPU 上通常比 openai-whisper 快 3–4 倍，
且不需要装 torch（安装体积从 ~2.5 GB 降到 ~300 MB）。
"""

from __future__ import annotations

import importlib.util
import time
from dataclasses import dataclass

DEFAULT_PROMPT = (
    "以下是普通话短视频内容，可能涉及财税、自媒体、AI工具、经营合规。"
    "请准确保留专有名词、人名、平台名和数字。"
)

BACKENDS = ("faster-whisper", "whisper")


@dataclass
class Transcription:
    text: str
    seconds: float = 0.0
    backend: str = ""
    model: str = ""


def _has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def available_backends() -> list[str]:
    found = []
    if _has_module("faster_whisper"):
        found.append("faster-whisper")
    if _has_module("whisper"):
        found.append("whisper")
    return found


def pick_backend(preferred: str = "auto") -> str:
    """auto 时优先 faster-whisper；都没装返回空字符串。"""
    if preferred and preferred != "auto":
        return preferred
    found = available_backends()
    return found[0] if found else ""


def transcribe_file(
    path: str,
    model: str = "small",
    backend: str = "auto",
    language: str = "zh",
    prompt: str = DEFAULT_PROMPT,
) -> Transcription:
    """转录一个音频/视频文件，返回文本与耗时。"""
    name = pick_backend(backend)
    started = time.time()
    if name == "faster-whisper":
        text = _run_faster_whisper(path, model, language, prompt)
    elif name == "whisper":
        text = _run_openai_whisper(path, model, language, prompt)
    else:
        raise RuntimeError("未安装转录后端：pip install openai-whisper 或 faster-whisper")
    return Transcription(text=text.strip(), seconds=time.time() - started, backend=name, model=model)


def _run_openai_whisper(path: str, model: str, language: str, prompt: str) -> str:
    import whisper

    # Python 3.11+ 的 mock 兼容补丁（torch/whisper 遗留问题）
    from unittest import mock

    if not hasattr(mock, "patch"):  # pragma: no cover
        def _patch(target, *args, **kwargs):
            return mock.patch(target, *args, **kwargs)

        mock.patch = _patch

    audio = _load_audio(whisper, path)
    instance = whisper.load_model(model)
    result = instance.transcribe(
        audio,
        language=language,
        verbose=False,
        fp16=False,
        initial_prompt=prompt,
    )
    return str(result.get("text", ""))


def _load_audio(whisper, path: str):
    """优先用 whisper 自带的解码；失败再退回 soundfile + scipy 重采样。"""
    try:
        return whisper.load_audio(path)
    except Exception:
        import numpy as np
        import soundfile as sf
        from scipy import signal as sig

        data, rate = sf.read(path)
        if data.ndim > 1:
            data = data.mean(axis=1)
        data = data.astype(np.float32)
        if rate != 16000:
            data = sig.resample(data, int(len(data) * 16000 / rate))
        return data


def _run_faster_whisper(path: str, model: str, language: str, prompt: str) -> str:
    from faster_whisper import WhisperModel

    instance = WhisperModel(model, device="cpu", compute_type="int8")
    segments, _info = instance.transcribe(
        path,
        language=language,
        initial_prompt=prompt,
        vad_filter=True,
        beam_size=1,
    )
    return "".join(segment.text for segment in segments)
