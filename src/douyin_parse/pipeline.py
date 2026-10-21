"""主流程：打开页面 → 抓流 → 下载 → 转码 → 转录 → 修订 → OCR → 分析 → 落盘。"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime

from . import ai
from .ai import call_ai_analysis, normalize_extracted_text, restore_punctuation
from .browser import minimize_browser_windows
from .config import Config
from .correct import correct_transcript
from .extract import analyze_page
from .media import choose_record_device, download_to_file
from .naming import auto_number_folders, safe_name
from .render import build_analysis_md, build_ocr_md, format_reliability_output, fmt_duration
from .transcribe import transcribe_file

try:
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError:  # pragma: no cover - 依赖缺失时由 doctor 提示
    sync_playwright = None


def ensure_runtime_ready(cfg):
    """建好输出目录、浏览器 profile 目录，并把 ffmpeg 所在目录加进 PATH。"""
    os.makedirs(cfg.output_base, exist_ok=True)
    os.makedirs(cfg.profile_dir, exist_ok=True)
    if cfg.ffmpeg:
        ffmpeg_dir = os.path.dirname(cfg.ffmpeg)
        if ffmpeg_dir and ffmpeg_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")


def _wav_seconds(path: str) -> float:
    """读 WAV 时长（秒）；失败返回 0。"""
    try:
        import wave

        with wave.open(path, "rb") as handle:
            return handle.getnframes() / float(handle.getframerate() or 16000)
    except Exception:
        return 0.0


def _launch_kwargs(cfg):
    """按配置组装 Playwright 启动参数；Windows 默认接系统 Chrome。"""
    kwargs = {"headless": cfg.headless}
    if cfg.browser_channel:
        kwargs["channel"] = cfg.browser_channel
    if cfg.proxy:
        kwargs["proxy"] = {"server": cfg.proxy}
    if cfg.user_agent:
        kwargs["user_agent"] = cfg.user_agent
    return kwargs


def run(cfg: Config) -> int:
    """解析一条链接，返回退出码（0 成功）。"""
    if sync_playwright is None:
        print("错误: 未安装 playwright，请先 pip install playwright && playwright install chromium")
        return 2

    # ============ 1. Playwright 打开页面，检测内容类型 ============

    ensure_runtime_ready(cfg)

    print(f"  AI分析: {'启用' if ai.AI_ENABLED else '未启用'} (Provider: {ai.AI_PROVIDER or '未配置'})")
    print(f"=== 抖音内容文案提取 ===")
    print(f"链接: {cfg.url}")
    t0 = time.time()

    video_urls = []
    audio_urls = []


    def on_response(response):
        url = response.url
        ct = response.headers.get('content-type', '')
        if 'audio' in ct or any(k in url for k in ['.m4a', '.mp3', '.aac', 'audio']):
            if 'douyin' in url or 'douyinvod' in url or 'amemv' in url:
                audio_urls.append(url)
                return
        if any(k in url for k in ['video/', '.mp4', 'play', 'v26']):
            if 'video' in ct or '.mp4' in url:
                video_urls.append(url)


    print("步骤1: 打开页面，检测内容类型...")
    with sync_playwright() as p:
        try:
            context = p.chromium.launch_persistent_context(
                cfg.profile_dir, **_launch_kwargs(cfg),
                viewport={'width': 1280, 'height': 900}
            )
        except Exception as exc:
            print(f"  错误: 浏览器启动失败 - {exc}")
            print("  处理办法：先关掉所有 Chrome 窗口再重试；仍然失败就删除浏览器配置目录：")
            print(f"    {cfg.profile_dir}")
            return 2
        page = context.new_page()
        # new_page() 才会创建可见标签页，此时立即最小化。
        minimize_browser_windows()
        page.on('response', on_response)
        page.goto(cfg.url, timeout=45000, wait_until='domcontentloaded')
        time.sleep(6)

        final_url = page.url

        # --- 检测内容类型（多维度综合判定）---
        page_title = page.title()
        is_content_page = '/video/' in final_url or '/note/' in final_url or 'modal_id' in final_url

        # 先处理非内容页的重定向
        if not is_content_page:
            print("  页面未加载到内容页，等待重定向...")
            time.sleep(3)
            final_url = page.url
            is_content_page = '/video/' in final_url or '/note/' in final_url or 'modal_id' in final_url
            if not is_content_page:
                page.screenshot(path=f'{cfg.output_base}/debug_{time.strftime("%Y%m%d_%H%M%S")}.png')
                print(f"  错误: 无法加载内容页，当前URL={final_url[:80]}，截图已保存")
                context.close()
                return 1

        meta = analyze_page(page, final_url, cfg.force_video)
        content_type = meta["content_type"]
        is_image_text = meta["is_image_text"]
        title = meta["title"]
        author = meta["author"]
        tags = meta["tags"]

        # ============ 图文分支：从DOM提取文本 ============
        if is_image_text:
            print("\n步骤2: 提取图文内容（DOM文本）...")

            text_parts = []

            # 方式0：多图片描述提取（图文特有）
            image_descs = page.evaluate("""
                () => {
                    const descs = [];
                    // 在图片展示区域中查找每张图片的描述文字
                    const containers = document.querySelectorAll(
                        '[class*="image-note"], [class*="slide"], [class*="swiper-slide"], ' +
                        '[class*="carousel"] > *, [class*="gallery"] > *'
                    );
                    containers.forEach(c => {
                        // 提取该容器内的文本（图片alt/描述）
                        const imgs = c.querySelectorAll('img');
                        imgs.forEach(img => {
                            const desc = img.alt || img.getAttribute('aria-label') || '';
                            if (desc && desc.length > 2 && !descs.includes(desc)) {
                                descs.push(desc);
                            }
                        });
                        // 也提取容器内的文字说明
                        const textEls = c.querySelectorAll('[class*="text"], [class*="desc"], [class*="caption"]');
                        textEls.forEach(el => {
                            const t = el.innerText?.trim();
                            if (t && t.length > 5 && !descs.includes(t) && descs.length < 20) {
                                descs.push(t);
                            }
                        });
                    });
                    return descs;
                }
            """)
            if image_descs:
                text_parts.append('\n\n'.join(image_descs))
                print(f"  提取到 {len(image_descs)} 条图片描述")

            # 方式1：描述区域（精准选择器）
            for sel in [
                '[data-e2e="video-desc"]',
                '[data-e2e="note-desc"]',
                '[class*="note-desc"]',
                '[class*="desc-text"]',
                '[class*="image-note-text"]',
                '[class*="note-content-text"]',
                'div[class*="detail"] span',
                '[class*="post-desc"]',
                '[class*="content-desc"]',
            ]:
                e = page.query_selector(sel)
                if e:
                    t = e.inner_text().strip()
                    if t and len(t) > 10:
                        text_parts.append(t)
                        break

            # 方式2：用JS智能定位图文主体区域，排除推荐流
            if not text_parts:
                smart_text = page.evaluate("""
                    () => {
                        const excludeSelectors = [
                            '[class*="recommend"]', '[class*="related"]',
                            '[class*="sidebar"]', '[class*="list-item"]',
                            '[class*="comment"]', '[class*="footer"]',
                            '[class*="banner"]', '[class*="ad"]',
                            '[class*="follow"]', '[class*="search"]',
                            '[class*="nav"]', '[class*="tab"]',
                            '[class*="live"]', '[class*="stream"]',
                        ];

                        const centerX = window.innerWidth / 2;
                        const centerY = window.innerHeight * 0.3;
                        const el = document.elementFromPoint(centerX, centerY);
                        if (!el) return '';

                        let container = el;
                        for (let i = 0; i < 12; i++) {
                            if (!container || container === document.body) break;
                            // 检查容器本身是否被排除
                            let selfExcluded = false;
                            for (const excl of container.matches
                                ? [excludeSelectors.find(s => container.matches(s))]
                                : []) {
                                if (excl) { selfExcluded = true; break; }
                            }
                            if (!selfExcluded) {
                                const text = container.innerText || '';
                                if (text.length > 50 && text.length < 5000) {
                                    let excluded = false;
                                    for (const excl of excludeSelectors) {
                                        if (container.querySelector(excl)) { excluded = true; break; }
                                    }
                                    if (!excluded) return text;
                                }
                            }
                            container = container.parentElement;
                        }
                        return '';
                    }
                """)
                if smart_text and len(smart_text) > 10:
                    text_parts.append(smart_text)

            # 方式3：紧凑兜底 - 取页面主区域文本但不含推荐流
            if not text_parts:
                body_text = page.evaluate("""
                    () => {
                        const clone = document.body.cloneNode(true);
                        const removeSels = [
                            '[class*="recommend"]', '[class*="related-post"]',
                            '[class*="list-item"]', '[class*="comment-list"]',
                            '[class*="follow-card"]', '[class*="footer"]',
                            '[class*="nav"]', '[class*="tab-bar"]',
                            '[class*="search"]', '[class*="sidebar"]',
                            '[class*="banner"]', '[class*="ad"]',
                            '[class*="live"]', '[class*="stream"]',
                            'header', 'nav',
                        ];
                        for (const sel of removeSels) {
                            clone.querySelectorAll(sel).forEach(e => e.remove());
                        }
                        const text = (clone.innerText || '')
                            .replace(/\\n{3,}/g, '\\n\\n')
                            .replace(/[ \\t]{2,}/g, ' ')
                            .trim();
                        return text;
                    }
                """)
                if body_text and len(body_text) > 10:
                    # 保留前2000字（图文正文通常在开头），并保持段落结构
                    truncated = body_text[:2000]
                    # 尽量在段落边界截断
                    last_break = max(truncated.rfind('\n\n'), truncated.rfind('\n'))
                    if last_break > 1500:
                        truncated = truncated[:last_break]
                    text_parts.append(truncated)

            transcript_raw = normalize_extracted_text('\n\n'.join(text_parts))
            print(f"  提取文本: {len(transcript_raw)}字")

            # --- 标点恢复 ---
            print("  标点恢复中...")
            transcript_punct = restore_punctuation(transcript_raw)
            if transcript_punct != transcript_raw:
                print(f"  标点恢复完成: {len(transcript_punct)}字")
            else:
                print(f"  标点恢复未生效（AI未配置或返回异常）")

            # --- 文案修订 ---
            correction_result = correct_transcript(transcript_punct)
            transcript = correction_result['corrected']
            print(f"  文案修订: 修正{correction_result['stats']['total_corrections']}处, 修订后{len(transcript)}字")

            context.close()

            # --- AI 可靠性分析 ---
            analysis = None
            if ai.AI_ENABLED and transcript:
                print("  正在调用 AI 可靠性分析...")
                analysis = call_ai_analysis(transcript, "图文", title, author, 0, tags, final_url)
            elif not ai.AI_ENABLED:
                print("  AI 分析未启用（未设置 AI_API_KEY 环境变量）")

            # --- 保存图文结果 ---
            OUTPUT_DIR = f'{cfg.output_base}/{safe_name(title)}_{time.strftime("%Y%m%d")}'
            os.makedirs(OUTPUT_DIR, exist_ok=True)

            with open(f'{OUTPUT_DIR}/文案.txt', 'w', encoding='utf-8') as f:
                f.write(transcript)

            # 保存修订报告
            from .correct import save_correction_report
            if correction_result['stats']['total_corrections'] > 0:
                report_path = f'{OUTPUT_DIR}/修订报告.md'
                save_correction_report(correction_result, report_path)
                print(f"  修订报告已保存: {report_path}")

            meta = {
                'url': final_url,
                'title': title,
                'author': author,
                'content_type': 'image_text',
                'tags': tags,
                'transcript': transcript,
                'transcript_raw': transcript_raw,
                'ai_reliability_analysis': analysis,
            }
            with open(f'{OUTPUT_DIR}/info.json', 'w', encoding='utf-8') as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)

            # 保存分析版（Markdown 版式，2026-10-19 方案B）
            full_output = build_analysis_md(transcript, analysis, "图文", 0,
                                            title=title, tags=tags, author=author,
                                            url=final_url, elapsed=time.time() - t0)
            with open(f'{OUTPUT_DIR}/文案_分析版.md', 'w', encoding='utf-8') as f:
                f.write(full_output)

            print(f"\n=== 完成 ({time.time()-t0:.1f}秒) ===")
            print(f"输出: {OUTPUT_DIR}/文案.txt")
            print(f"输出: {OUTPUT_DIR}/文案_分析版.md")
            print(f"\n{full_output}")
            return 0

        # ============ 视频分支：继续原有流程 ============
        # 获取视频时长
        try:
            duration = page.evaluate('document.querySelector("video").duration')
        except:
            duration = 0

        # 获取视频src（备用方案）
        try:
            video_src = page.evaluate('document.querySelector("video").src || document.querySelector("video source")?.src || ""')
            if video_src and video_src not in video_urls:
                video_urls.append(video_src)
        except:
            pass

        context.close()

    print(f"  标题: {title[:60]}")
    print(f"  作者: {author[:30]}")
    print(f"  时长: {duration:.0f}秒")
    print(f"  拦截到 {len(video_urls)} 个视频URL, {len(audio_urls)} 个音频URL")
    print(f"  耗时: {time.time()-t0:.1f}秒")

    # ============ 2. 下载 ============
    print("\n步骤2: 下载...")

    OUTPUT_DIR = f'{cfg.output_base}/{safe_name(title)}_{time.strftime("%Y%m%d")}'
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    video_file = f'{OUTPUT_DIR}/video.mp4'
    audio_file = f'{OUTPUT_DIR}/audio.wav'
    audio_raw = f'{OUTPUT_DIR}/audio_raw'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.douyin.com/'
    }

    # 优先下载纯音频流
    audio_downloaded_path = None
    for url in audio_urls:
        if not url.startswith('http'):
            continue
        try:
            print(f"  尝试音频流: {url[:80]}...")
            ext = '.mp3' if '.mp3' in url else ('.aac' if '.aac' in url else '.m4a')
            audio_downloaded_path = audio_raw + ext
            ok, error, size = download_to_file(url, audio_downloaded_path, headers, min_bytes=50 * 1024)
            if ok:
                print(f"  音频流下载成功: {size/1024:.0f}KB ({ext})")
                break
            print(f"  音频流无效: {error}")
            audio_downloaded_path = None
        except Exception as e:
            print(f"  音频流失败: {e}")

    # 下载视频流
    downloaded = False
    for url in video_urls:
        if not url.startswith('http'):
            continue
        try:
            print(f"  尝试视频流: {url[:80]}...")
            ok, error, size = download_to_file(url, video_file, headers, min_bytes=100000)
            if not ok:
                print(f"  视频流无效: {error}")
                continue
            size_mb = size / 1024 / 1024
            print(f"  视频流下载成功: {size_mb:.1f}MB")
            downloaded = True

            check_cmd = [cfg.ffmpeg, '-i', video_file]
            check_result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=15, encoding='utf-8', errors='replace')
            has_audio = 'Audio:' in (check_result.stderr or '')
            print(f"  视频含音频: {has_audio}")

            if has_audio or audio_downloaded_path:
                break
            downloaded = False
            if os.path.exists(video_file):
                os.remove(video_file)
            continue
        except Exception as e:
            print(f"  失败: {e}")

    # ============ 3. 提取音频 ============
    print("\n步骤3: 提取音频...")

    audio_ready = False

    # 方案A：纯音频流转wav
    if audio_downloaded_path and os.path.exists(audio_downloaded_path):
        print(f"  从音频流转换: {audio_downloaded_path}")
        cmd = [cfg.ffmpeg, '-i', audio_downloaded_path, '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', audio_file, '-y']
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, encoding='utf-8', errors='replace')
        if r.returncode == 0 and os.path.exists(audio_file) and os.path.getsize(audio_file) > 1000:
            print(f"  音频提取成功(音频流): {os.path.getsize(audio_file)/1024:.0f}KB")
            audio_ready = True
        else:
            print(f"  音频流转换失败: {(r.stderr or '')[:100]}")

    # 方案B：从视频文件提取
    if not audio_ready and downloaded and os.path.exists(video_file):
        print(f"  从视频文件提取音频...")
        cmd = [cfg.ffmpeg, '-i', video_file, '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', audio_file, '-y']
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, encoding='utf-8', errors='replace')
        if r.returncode == 0 and os.path.exists(audio_file) and os.path.getsize(audio_file) > 1000:
            print(f"  音频提取成功(视频): {os.path.getsize(audio_file)/1024:.0f}KB")
            audio_ready = True
        else:
            print(f"  视频无音频流，尝试其他视频URL...")
            for url in video_urls:
                if not url.startswith('http'):
                    continue
                try:
                    ok, error, _ = download_to_file(url, video_file, headers, min_bytes=100000)
                    if not ok:
                        print(f"  备选视频流无效: {error}")
                        continue
                    cmd = [cfg.ffmpeg, '-i', video_file, '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', audio_file, '-y']
                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, encoding='utf-8', errors='replace')
                    if r.returncode == 0 and os.path.exists(audio_file) and os.path.getsize(audio_file) > 1000:
                        print(f"  音频提取成功(备选视频): {os.path.getsize(audio_file)/1024:.0f}KB")
                        audio_ready = True
                        break
                except:
                    continue

    # 方案C：fallback录音
    if not audio_ready:
        print("  所有下载方案失败，改用录音方案...")
        try:
            import sounddevice as sd
            import soundfile as sf
        except ImportError:
            print("错误: 录音降级方案需要 sounddevice 与 soundfile")
            print("      请先 pip install sounddevice soundfile，或排查网络/代理后重试以直接下载到音频流")
            return 1

        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                cfg.profile_dir, **_launch_kwargs(cfg),
                viewport={'width': 1280, 'height': 900}
            )
            page = context.new_page()
            # new_page() 才会创建可见标签页，此时立即最小化。
            minimize_browser_windows()
            page.goto(cfg.url, timeout=45000, wait_until='domcontentloaded')
            time.sleep(3)

            try:
                duration = page.evaluate('document.querySelector("video").duration')
            except:
                duration = 180

            rec_duration = min(duration + 3, 900)
            SAMPLE_RATE = 48000
            REC_DEVICE = choose_record_device(sd)
            if REC_DEVICE is None:
                print("错误: 找不到可用录音设备，请先确认系统输入设备")
                context.close()
                return 1
            print(f"  录音设备: {REC_DEVICE}")

            page.evaluate('const v=document.querySelector("video"); v.pause(); v.currentTime=0; v.muted=false; v.volume=1.0;')
            time.sleep(0.5)

            recording = sd.rec(int(rec_duration * SAMPLE_RATE), samplerate=SAMPLE_RATE,
                               channels=2, device=REC_DEVICE, dtype='float32')
            time.sleep(0.3)
            page.evaluate('document.querySelector("video").play()')
            print(f"  录音中... ({rec_duration:.0f}秒)")
            sd.wait()

            sf.write(audio_file, recording, SAMPLE_RATE)
            print(f"  录音完成: 振幅={recording.max():.4f}")
            audio_ready = True
            context.close()

    if not audio_ready:
        print("错误: 无法获取音频")
        return 1

    # 以音频实际长度为准：页面上读到的 duration 偶尔是预加载片段
    audio_seconds = _wav_seconds(audio_file)
    if audio_seconds and abs(audio_seconds - duration) > 3:
        print(f"  时长以音频为准: {duration:.0f}秒 -> {audio_seconds:.0f}秒")
        duration = audio_seconds

    # ============ 4. Whisper 转录 ============
    print("\n步骤4: Whisper转录...")
    t1 = time.time()

    if cfg.ffmpeg:
        os.environ['PATH'] = os.path.dirname(cfg.ffmpeg) + os.pathsep + os.environ.get('PATH', '')

    print(f"  模型: {cfg.whisper_model} (后端: {cfg.transcribe_backend})")
    try:
        transcription = transcribe_file(
            audio_file,
            model=cfg.whisper_model,
            backend=cfg.transcribe_backend,
        )
    except Exception as exc:
        print(f"  错误: 转录失败 - {exc}")
        return 1

    print(f"  转录耗时: {transcription.seconds:.1f}秒 (后端: {transcription.backend})")
    transcript_raw = normalize_extracted_text(transcription.text)
    print(f"  转录完成: {len(transcript_raw)}字")

    # --- 标点恢复 ---
    print("  标点恢复中...")
    transcript_punct = restore_punctuation(transcript_raw)
    if transcript_punct != transcript_raw:
        print(f"  标点恢复完成: {len(transcript_punct)}字")
    else:
        print(f"  标点恢复未生效（AI未配置或返回异常）")

    # --- 文案修订 ---
    correction_result = correct_transcript(transcript_punct)
    transcript = correction_result['corrected']
    print(f"  文案修订: 修正{correction_result['stats']['total_corrections']}处, 修订后{len(transcript)}字")

    # ============ 5.5 视频画面文字提取(OCR) ============
    ocr_texts = []
    try:
        from .ocr import extract_text_from_video, format_ocr_output
        HAS_OCR = True
    except ImportError:
        HAS_OCR = False

    if cfg.disable_ocr:
        print("\n  [OCR] 已按 --no-ocr 跳过画面文字提取")
    elif HAS_OCR and os.path.exists(video_file):
        print("\n步骤5.5: 提取视频画面文字(OCR)...")
        ocr_texts = extract_text_from_video(video_file, cfg.ffmpeg, interval=1.0, max_frames=60)
        if ocr_texts:
            print(f"  OCR提取到 {len(ocr_texts)} 段文字")
        else:
            print("  OCR未提取到文字")
    else:
        print("\n  [OCR] 未安装 rapidocr-onnxruntime，跳过画面文字提取")

    # ============ 6. AI 可靠性分析 ============
    analysis = None
    if ai.AI_ENABLED and transcript:
        print("\n  正在调用 AI 可靠性分析...")
        analysis = call_ai_analysis(transcript, "视频", title, author, duration, tags, final_url)
    elif not ai.AI_ENABLED:
        print("\n  AI 分析未启用（未设置 AI_API_KEY 环境变量）")

    # ============ 6. 保存 ============
    # 方案B：文案.txt 只留纯正文，画面文字单独存 画面文字.md
    with open(f'{OUTPUT_DIR}/文案.txt', 'w', encoding='utf-8') as f:
        f.write(transcript)

    ocr_file = None
    if ocr_texts:
        ocr_file = '画面文字.md'
        with open(f'{OUTPUT_DIR}/{ocr_file}', 'w', encoding='utf-8') as f:
            f.write(build_ocr_md(title, ocr_texts, url=final_url))
        print(f"  画面文字已保存: {OUTPUT_DIR}/{ocr_file}")

    # 保存修订报告
    from .correct import save_correction_report
    if correction_result['stats']['total_corrections'] > 0:
        report_path = f'{OUTPUT_DIR}/修订报告.md'
        save_correction_report(correction_result, report_path)
        print(f"  修订报告已保存: {report_path}")

    meta = {
        'url': final_url,
        'title': title,
        'author': author,
        'duration': duration,
        'content_type': 'video',
        'tags': tags,
        'transcript': transcript,
        'transcript_raw': transcript_raw,
        'ai_reliability_analysis': analysis,
        'ocr_texts': ocr_texts,
    }
    with open(f'{OUTPUT_DIR}/info.json', 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # 保存分析版（Markdown 版式，2026-10-19 方案B）
    full_output = build_analysis_md(transcript, analysis, "视频", duration,
                                    title=title, tags=tags, author=author,
                                    url=final_url, ocr_count=len(ocr_texts),
                                    ocr_file=ocr_file, elapsed=time.time() - t0)
    with open(f'{OUTPUT_DIR}/文案_分析版.md', 'w', encoding='utf-8') as f:
        f.write(full_output)

    # 清理视频文件
    if os.path.exists(video_file):
        os.remove(video_file)

    # ============ 7. 自动编号文件夹 ============
    # 不参与自动编号的目录（先剥掉 3 位数字前缀，再按这些规则匹配）


    if cfg.auto_number:
        auto_number_folders(cfg.output_base)

    print(f"\n=== 完成 ({time.time()-t0:.1f}秒) ===")
    print(f"输出: {OUTPUT_DIR}/文案.txt")
    print(f"输出: {OUTPUT_DIR}/文案_分析版.md")
    print(f"\n{full_output}")

    return 0
