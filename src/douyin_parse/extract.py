"""页面解析：图文/视频判定、标题、作者、标签。"""

from __future__ import annotations

import time


def analyze_page(page, final_url: str, force_video: bool = False) -> dict:
    """对已加载的内容页做图文/视频判定，并读标题、作者、标签。"""
    page_title = page.title()

    # 多维度综合判定图文/视频
    score = 0

    # 维度1：URL 路径包含 /note/（强信号）
    if '/note/' in final_url:
        score += 2

    # 维度2：页面是否有 <video> 元素（加导航稳定性处理）
    try:
        page.wait_for_load_state('domcontentloaded', timeout=8000)
    except:
        pass
    try:
        has_video = page.evaluate('!!document.querySelector("video")')
    except:
        # 页面导航中导致 evaluate 失败，等待后重试
        print("  页面导航中，等待2秒后重试...")
        time.sleep(2)
        try:
            page.wait_for_load_state('domcontentloaded', timeout=10000)
        except:
            pass
        has_video = page.evaluate('!!document.querySelector("video")')
    if not has_video:
        score += 1

    # 维度3：图片数量 + 视频播放器 + 图文DOM 综合检测
    dom_check = page.evaluate("""
        () => {
            const imgs = document.querySelectorAll('img');
            // 排除小图标（头像、点赞等 < 100px 的图）
            const largeImgs = Array.from(imgs).filter(i =>
                i.naturalWidth > 100 || i.width > 100 || i.clientWidth > 100
            ).length;
            const hasVideoPlayer = !!document.querySelector(
                'video, [class*="video-player"], [class*="player"], [class*="xgplayer"]'
            );
            const hasImageNoteDOM = !!document.querySelector(
                '[class*="image-note"], [class*="slide"], [class*="swiper"], ' +
                '[class*="carousel"], [class*="gallery-view"], [class*="image-viewer"]'
            );
            return { largeImgs, hasVideoPlayer, hasImageNoteDOM };
        }
    """)
    if dom_check['largeImgs'] > 3 and not dom_check['hasVideoPlayer']:
        score += 1
    if dom_check['hasImageNoteDOM']:
        score += 1

    # 维度4：标题关键词（仅在无视频或明确有图文标签时计入）
    title_keywords = ['#图文', '#图片', '#笔记', '#图集', '#相册', '【图文】']
    if any(kw in page_title for kw in title_keywords):
        score += 1

    # 如果有video标签或URL含有/video/，只有在/note/存在或score>=3时才认定为图文
    if has_video or '/video/' in final_url:
        is_image_text = ('/note/' in final_url) or (score >= 3)
    else:
        is_image_text = score >= 2

    # 强制视频模式
    if force_video:
        is_image_text = False
        print(f"  [强制视频模式] 忽略图文判定，强制走视频流程")

    print(f"  图文判定得分: {score}/5 (阈值≥2)")
    print(f"    URL /note/: {'[YES]' if '/note/' in final_url else '[NO]'} (+2)")
    print(f"    无video元素: {'[YES]' if not has_video else '[NO]'} (+1)")
    print(f"    大图>3且无播放器: {'[YES]' if dom_check['largeImgs']>3 and not dom_check['hasVideoPlayer'] else '[NO]'} (+1)")
    print(f"    图文DOM结构: {'[YES]' if dom_check['hasImageNoteDOM'] else '[NO]'} (+1)")
    print(f"    标题关键词: {'[YES]' if any(kw in page_title for kw in title_keywords) else '[NO]'} (+1)")

    content_type = "图文" if is_image_text else "视频"
    print(f"  内容类型: {content_type}")

    # --- 提取标题 ---
    title = ''
    for sel in ['[data-e2e="video-title"]', '[data-e2e="note-title"]', 'h1', '[class*="title"]']:
        e = page.query_selector(sel)
        if e:
            title = e.inner_text().strip()
            break
    if not title:
        title = page.title()

    # --- 提取作者 ---
    author = ''
    for sel in ['[data-e2e="user-info"]', '[class*="author"]', '[class*="nickname"]', '[class*="creator"]']:
        e = page.query_selector(sel)
        if e:
            author = e.inner_text().strip()
            break

    # --- 提取标签 ---
    tags = []
    for sel in ['[class*="tag"]', '[class*="hashtag"]', 'a[href*="tag"]']:
        for e in page.query_selector_all(sel):
            t = e.inner_text().strip()
            if t and len(t) < 30 and t not in tags:
                tags.append(t)

    return {
        "content_type": content_type,
        "is_image_text": is_image_text,
        "score": score,
        "title": title,
        "author": author,
        "tags": tags,
    }
