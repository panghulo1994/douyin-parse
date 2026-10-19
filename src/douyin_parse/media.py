"""媒体下载与音频设备选择。"""
import os
import urllib.error
import urllib.request

try:
    import requests
except ModuleNotFoundError:  # pragma: no cover
    requests = None

REQUESTS_AVAILABLE = requests is not None


def download_to_file(url, output_path, headers, min_bytes=1, timeout=60):
    """安全下载：先写临时文件，大小合格后再替换正式文件。"""
    tmp_path = output_path + '.tmp'
    if os.path.exists(tmp_path):
        os.remove(tmp_path)
    try:
        if REQUESTS_AVAILABLE:
            resp = requests.get(url, headers=headers, timeout=timeout, stream=True)
            if resp.status_code != 200:
                return False, f"HTTP {resp.status_code}", 0
            with open(tmp_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        else:
            req = urllib.request.Request(url, headers=headers or {}, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status != 200:
                    return False, f"HTTP {resp.status}", 0
                with open(tmp_path, 'wb') as f:
                    while True:
                        chunk = resp.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
        size = os.path.getsize(tmp_path)
        if size < min_bytes:
            os.remove(tmp_path)
            return False, f"文件过小 {size}B", size
        if os.path.exists(output_path):
            os.remove(output_path)
        os.replace(tmp_path, output_path)
        return True, "", size
    except Exception as e:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return False, str(e), 0


def choose_record_device(sd):
    """优先选择系统默认输入设备，避免录音设备编号写死。"""
    try:
        default_input = sd.default.device[0]
        if default_input is not None and default_input >= 0:
            return default_input
    except Exception:
        pass
    try:
        devices = sd.query_devices()
        for index, device in enumerate(devices):
            if device.get('max_input_channels', 0) > 0:
                return index
    except Exception:
        pass
    return None
