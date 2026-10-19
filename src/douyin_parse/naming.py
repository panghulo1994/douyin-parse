"""命名、时长格式化与产出目录编号。"""
import os
import re


def safe_name(s):
    name = re.sub(r'[\\/:*?"<>|\n\r#]', '_', s or '').strip(' ._')
    return (name or '未命名内容')[:40]


def fmt_duration(seconds):
    """秒数 -> X分Y秒；无效/为0时返回 —"""
    try:
        seconds = float(seconds or 0)
    except (TypeError, ValueError):
        return "—"
    if seconds <= 0:
        return "—"
    if seconds < 60:
        return f"{int(seconds)}秒"
    return f"{int(seconds // 60)}分{int(seconds % 60)}秒"


NUMBER_EXCLUDE_PATTERNS = (
    r'^__tmp',           # 重编号过程中的临时名
    r'^__pycache__$',    # Python 字节码缓存
    r'^temp[_-]',        # 临时视频等中间目录
    r'^batch_summary_',  # 批量汇总
    r'^debug_',          # 失败截图
    r'^\.',              # 隐藏目录
)


def is_excluded_dir(name):
    """判断目录是否应排除在自动编号之外。"""
    clean_name = re.sub(r'^\d{3}_', '', name)
    return any(re.match(pattern, clean_name) for pattern in NUMBER_EXCLUDE_PATTERNS)


def auto_number_folders(base_dir):
    """按修改时间排序，给CC抖音解析下所有文件夹添加编号前缀"""
    import json
    import re
    
    # 收集所有目录
    dirs = []
    junk_cleaned = False
    for name in os.listdir(base_dir):
        full = os.path.join(base_dir, name)
        if not os.path.isdir(full):
            continue
        if is_excluded_dir(name):
            clean_name = re.sub(r'^\d{3}_', '', name)
            if clean_name != name:
                try:
                    os.rename(full, os.path.join(base_dir, clean_name))
                    print(f"  已剔除编号: {name} -> {clean_name}")
                    junk_cleaned = True
                except OSError as e:
                    print(f"  警告: 无法剔除 {name}: {e}")
            continue
        mtime = os.path.getmtime(full)
        dirs.append((mtime, name, full))
    
    if not dirs:
        return
    
    dirs.sort(key=lambda x: x[0])
    
    # 检查是否已经有编号（格式: 数字_名称）
    needs_renumber = False
    for _, name, _ in dirs:
        if not re.match(r'^\d{3}_', name):
            needs_renumber = True
            break
    if junk_cleaned:
        needs_renumber = True  # 本轮剔除过垃圾目录，强制重编号以补上空号
    
    if not needs_renumber:
        # 已有编号，只检查数量是否匹配
        if len(dirs) == len([d for d in dirs if re.match(r'^\d{3}_', d[1])]):
            return  # 数量匹配，无需重编号
    
    print(f"\n  正在重新编号 {len(dirs)} 个文件夹...")
    
    # 清理可能残留的临时文件夹（只删空目录；非空的一律跳过，
    # 因为它们可能是上一次重命名中途留下的真实内容目录，绝不能整批删除）
    for f in os.listdir(base_dir):
        if f.startswith('__tmp') and f.endswith('__'):
            full = os.path.join(base_dir, f)
            try:
                if not os.listdir(full):
                    os.rmdir(full)
                    print(f"  已清理空临时目录: {f}")
                else:
                    print(f"  警告: {f} 非空，已跳过删除（防止误删真实内容）")
            except OSError as e:
                print(f"  警告: 无法清理 {f}: {e}")

    # 第一步：重命名为临时名（避免重名冲突）
    temp_map = []
    for i, (mt, name, full) in enumerate(dirs, 1):
        temp_name = f"__tmp{i:03d}__"
        temp_path = os.path.join(base_dir, temp_name)
        os.rename(full, temp_path)
        temp_map.append((temp_name, name))
    
    # 第二步：重命名为编号名
    for i, (temp_name, orig_name) in enumerate(temp_map, 1):
        old_full = os.path.join(base_dir, temp_name)
        # 如果已有编号前缀，先去掉再重新加
        clean_name = re.sub(r'^\d{3}_', '', orig_name)
        new_name = f"{i:03d}_{clean_name}"
        new_full = os.path.join(base_dir, new_name)
        os.rename(old_full, new_full)
    
    print(f"  编号完成: 001 ~ {len(dirs):03d}")
