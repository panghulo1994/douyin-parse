"""AI 调用：标点恢复与可靠性分析（OpenAI 兼容接口）。"""
import json
import re

try:
    import requests
except ModuleNotFoundError:  # pragma: no cover
    requests = None

import urllib.error
import urllib.request

REQUESTS_AVAILABLE = requests is not None

AI_PROVIDER = ""
AI_API_URL = ""
AI_API_KEY = ""
AI_MODEL = ""
AI_API_FORMAT = ""
AI_ENABLED = False


def configure(provider="", url="", key="", model="", api_format=""):
    """写入运行时 AI 配置；未配置时全部功能自动降级。"""
    global AI_PROVIDER, AI_API_URL, AI_API_KEY, AI_MODEL, AI_API_FORMAT, AI_ENABLED
    AI_PROVIDER = provider or ""
    AI_API_URL = url or ""
    AI_API_KEY = key or ""
    AI_MODEL = model or ""
    AI_API_FORMAT = api_format or ""
    AI_ENABLED = bool(AI_API_KEY and AI_API_URL)


class SimpleResponse:
    """requests 不可用时的最小响应对象。"""
    def __init__(self, status_code, headers=None, body=b""):
        self.status_code = status_code
        self.headers = headers or {}
        self._body = body
        self.text = body.decode("utf-8", errors="replace")

    def iter_content(self, chunk_size=8192):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i:i + chunk_size]

    def json(self):
        return json.loads(self.text)


class RequestsFallback:
    """用标准库兜底 requests.get/post，避免缺依赖直接退出。"""
    @staticmethod
    def get(url, headers=None, timeout=60, stream=False):
        req = urllib.request.Request(url, headers=headers or {}, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return SimpleResponse(resp.status, dict(resp.headers), resp.read())
        except urllib.error.HTTPError as e:
            return SimpleResponse(e.code, dict(e.headers), e.read())

    @staticmethod
    def post(url, headers=None, json=None, timeout=60):
        body = None
        if json is not None:
            body = __import__("json").dumps(json, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=headers or {}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return SimpleResponse(resp.status, dict(resp.headers), resp.read())
        except urllib.error.HTTPError as e:
            return SimpleResponse(e.code, dict(e.headers), e.read())


def clean_ai_text(text, original_hint=""):
    """清理 AI 返回里的说明、代码块和标题，只保留正文。"""
    if not text:
        return ""

    s = text.strip().strip('`').strip()
    s = re.sub(r'^```(?:text|markdown|md)?\s*', '', s, flags=re.I)
    s = re.sub(r'\s*```$', '', s).strip()
    s = re.sub(r'^(?:加标点后的文案|修订后文案|输出|结果|正文)[:：]\s*', '', s).strip()

    lines = []
    for line in s.splitlines():
        line = line.strip()
        if not line:
            lines.append("")
            continue
        if re.match(r'^(?:好的|以下是|下面是|已为你|我已|说明|注意)[:：，, ]', line):
            continue
        if line in {"加标点后的文案：", "修订后文案：", "正文："}:
            continue
        lines.append(line)

    s = "\n".join(lines).strip()
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s


def normalize_extracted_text(text):
    """清理页面提取文本，去重并过滤常见按钮、推荐、评论噪声。"""
    if not text:
        return ""

    junk_patterns = [
        r'^打开抖音', r'^登录$', r'^关注$', r'^已关注$', r'^粉丝$', r'^获赞$',
        r'^点赞$', r'^评论$', r'^分享$', r'^收藏$', r'^转发$', r'^私信$',
        r'^推荐$', r'^相关推荐$', r'^相关视频$', r'^查看更多$', r'^展开$', r'^收起$',
        r'^复制链接$', r'^看完整版$', r'^暂无评论$', r'^写评论',
    ]
    seen = set()
    cleaned = []
    for raw_line in text.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        line = re.sub(r'[ \t]+', ' ', raw_line).strip()
        if not line:
            if cleaned and cleaned[-1] != "":
                cleaned.append("")
            continue
        if len(line) <= 2:
            continue
        if any(re.search(pattern, line) for pattern in junk_patterns):
            continue
        key = re.sub(r'\s+', '', line)
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(line)

    result = "\n".join(cleaned).strip()
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result


def call_ai(prompt, system="你是一个专业的中文助手。", temperature=0.3, max_tokens=2000, hint=""):
    """通用 AI API 调用，返回文本或 None。hint 用于从推理模型的 reasoning_content 中提取最终结果。"""
    if not AI_ENABLED:
        return None
    try:
        if AI_API_FORMAT == "anthropic":
            headers = {"x-api-key": AI_API_KEY, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
            payload = {"model": AI_MODEL, "max_tokens": max_tokens, "temperature": temperature,
                       "system": system, "messages": [{"role": "user", "content": prompt}]}
        else:
            headers = {"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"}
            payload = {"model": AI_MODEL, "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt}], "temperature": temperature, "max_tokens": max_tokens}
        resp = requests.post(AI_API_URL, headers=headers, json=payload, timeout=60)
        if resp.status_code == 200:
            data = resp.json()
            if AI_API_FORMAT == "anthropic":
                return data.get("content", [{}])[0].get("text", "").strip()
            else:
                choices = data.get("choices", [])
                if choices:
                    msg = choices[0].get("message", {})
                    content = (msg.get("content") or "").strip()
                    if content:
                        return content
                    # MiMo 推理模型：content 为空，结果在 reasoning_content 里
                    # 从推理内容中提取不含分析标记的最长连续标点文本块
                    reasoning = (msg.get("reasoning_content") or "").strip()
                    if reasoning and hint:
                        import re
                        think_markers = ['这是一个', '意思是', '例如', '可能', '应该',
                                         '我需要', '我将', '让我', '首先', '然后', '现在',
                                         '分析', '识别', '理解', '检查', '确保', '注意',
                                         '句子', '段落', '要求', '输出', '添加标点']
                        blocks = re.split(r'\n+', reasoning)
                        best = ""
                        for block in blocks:
                            block = block.strip()
                            if len(block) < 15:
                                continue
                            if any(m in block for m in think_markers):
                                continue
                            if not re.search(r'[，。！？、；：]', block):
                                continue
                            if len(block) > len(best):
                                best = block
                        if best and len(best) > len(hint):
                            return best
                    return content
    except Exception as e:
        print(f"  AI调用失败: {e}")
    return None


def regex_punctuation(text):
    """正则规则做基础标点补充（AI 降级方案）"""
    import re
    s = text
    # 在常见断句词前加逗号
    s = re.sub(r'(?<=[^\s，。！？、；：])((?:但是|不过|所以|因此|然后|接着|因为|如果|那么|而且|另外|同时|比如|就是说|总之|其实|说实话|另外|还有一个|需要注意))', r'，\1', s)
    # 在语气词后加句号（如果后面紧跟的是新句子的开头）
    s = re.sub(r'((?:好了|可以了|就可以了|就行了|结束了|对吧|明白了吗|了解了吗|看到了吗))((?:我|你|他|它|这|那|那么|所以|然后|接下来|下面|后面|最后|另外))', r'\1。\2', s)
    # 在"了"后如果紧跟常见句首词，加句号
    s = re.sub(r'(了)((?:我|你|他|它|这|那|那么|所以|接下来|下面|后面|最后|另外|还|又|也))', r'\1。\2', s)
    # 常见句尾模式加句号
    s = re.sub(r'(清楚了?)([我你他这那那么所以接下来下面])', r'\1。\2', s)
    s = re.sub(r'(教程|[用使]法|[操配]作|[设更]置|[安下]装)([我你他这那那么所以接下来下面])', r'\1。\2', s)
    # 数字编号后（如1. 2. 3.）的中文内容加句号
    s = re.sub(r'(\d+[.、][^。！？\n]{5,30}?)(?=\d+[.、]|$)', lambda m: m.group(1).rstrip() + ('。' if not m.group(1).rstrip().endswith(('。', '！', '？')) else ''), s)
    # 末尾无标点则加句号
    if s and s[-1] not in '。！？…～':
        s += '。'
    return s


def restore_punctuation(text):
    """用 AI 给无标点文案加标点和分段，AI 失败时用正则降级"""
    if len(text) < 20:
        return text
    if AI_ENABLED:
        prompt = f"""请给以下无标点中文文案添加标点符号并合理分段。

要求：
1. 根据语义和语气添加逗号、句号、问号、感叹号等
2. 每2-4句话分一段，保持段落结构清晰
3. 不要修改或删除任何文字内容，只加标点和换行
4. 专有名词保持原样（如 Codex家家、iCover、DeepSeek 等）
5. 直接输出加标点后的文案，不要加任何说明

原文：
{text}"""
        result = call_ai(prompt, system="你是中文标点恢复助手，只负责加标点和分段，不修改任何文字。", temperature=0.1, max_tokens=8000, hint=text[:30])
        if result:
            result = clean_ai_text(result, text[:30])
        if result and len(result) > len(text) // 2:
            return result
        print("  AI标点未生效，使用正则降级方案")
    return regex_punctuation(text)


def call_ai_analysis(transcript, content_type, title, author, duration, tags, url):
    """调用 AI API 对文案进行可靠性分析，失败时返回降级内容"""
    if not AI_ENABLED:
        print("  AI分析未启用（API Key 未配置）")
        return None

    word_count = len(transcript.replace(" ", ""))
    duration_str = f"{int(duration)}秒" if content_type == "视频" and duration else "N/A"

    prompt = f"""你是一个内容事实核查助手。请对以下抖音{content_type}文案进行简短可靠性分析。

标题：{title}
作者：{author}
类型：{content_type}
字数：{word_count}字
时长：{duration_str}
标签：{', '.join(tags) if tags else '无'}

文案内容：
{transcript[:2000]}

请按以下格式输出分析（总字数控制在200字以内，每个评估点1-3句话）：

📊 基本信息
- 类型：{content_type}
- 时长：{duration_str}
- 转录字数：{word_count}字

✅ 内容核查
- 事实性评估：[评估文案中提到的数据、事件、观点是否可靠]
- 可能的偏差：[指出文案中可能存在的一家之言、信息过时、数据存疑等问题]
- 来源可信度：高/中/低（附简短理由）

💡 使用建议
- [建议如何引用/使用这些信息]
- [如涉及数据，建议核实原始来源]

⚠️ 注意事项
- [需要特别注意的误导性内容]
- [建议交叉验证的关键信息点]
"""

    try:
        # 根据 API 格式构建请求
        if AI_API_FORMAT == "anthropic":
            # Anthropic 格式（MiMo）
            headers = {
                "x-api-key": AI_API_KEY,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
            payload = {
                "model": AI_MODEL,
                "max_tokens": 2000,
                "temperature": 0.3,
                "system": "你是一个专业的内容事实核查助手。请保持分析简短精炼，使用emoji标记分段。",
                "messages": [
                    {"role": "user", "content": prompt}
                ],
            }
        else:
            # OpenAI 格式（DeepSeek）
            headers = {
                "Authorization": f"Bearer {AI_API_KEY}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": AI_MODEL,
                "messages": [
                    {"role": "system", "content": "你是一个专业的内容事实核查助手。请保持分析简短精炼，使用emoji标记分段。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 2000,
            }

        resp = requests.post(AI_API_URL, headers=headers, json=payload, timeout=30)

        if resp.status_code == 200:
            data = resp.json()
            # 根据 API 格式解析响应
            if AI_API_FORMAT == "anthropic":
                analysis = data.get("content", [{}])[0].get("text", "").strip()
            else:
                analysis = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

            if analysis:
                print(f"  AI分析完成 ({len(analysis)}字)")
                return analysis
            else:
                print(f"  AI返回空内容")
                return None
        else:
            print(f"  AI API返回错误: {resp.status_code} - {resp.text[:200]}")
            return None
    except Exception as e:
        print(f"  AI分析调用失败: {e}")
        return None
