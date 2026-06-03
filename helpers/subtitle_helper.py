import os
import shutil

SUBTITLE_EXTENSIONS = ('.srt', '.ass', '.ssa', '.vtt', '.sub')

def find_matching_subtitles(video_path: str) -> list:
    """
    检索同文件夹下与视频文件前缀名相匹配的外挂字幕文件。
    例如：视频为 ABC-123.mp4，匹配 ABC-123.zh-CN.srt, ABC-123.ass 等。
    """
    if not video_path or not os.path.exists(video_path):
        return []
    
    dir_name = os.path.dirname(video_path)
    video_filename = os.path.basename(video_path)
    video_base, _ = os.path.splitext(video_filename)
    video_base_lower = video_base.lower()
    
    subtitles = []
    try:
        for entry in os.listdir(dir_name):
            entry_path = os.path.join(dir_name, entry)
            if not os.path.isfile(entry_path):
                continue
            
            entry_lower = entry.lower()
            if entry_lower.endswith(SUBTITLE_EXTENSIONS):
                # 检查字幕基本名是否以视频基本名开头
                entry_base, _ = os.path.splitext(entry)
                if entry_base.lower().startswith(video_base_lower):
                    subtitles.append(entry_path)
    except Exception as e:
        print(f"扫描外挂字幕文件失败: {e}")
        
    return subtitles

def move_and_rename_subtitles(video_path: str, target_video_path: str, subtitles: list) -> list:
    """
    将匹配的外挂字幕同步移动并命名到与新视频文件对应的名称和目录下，保留字幕的语言后缀。
    """
    moved_subs = []
    video_base_old, _ = os.path.splitext(os.path.basename(video_path))
    video_base_new, _ = os.path.splitext(os.path.basename(target_video_path))
    target_dir = os.path.dirname(target_video_path)
    
    for sub_path in subtitles:
        if not os.path.exists(sub_path):
            continue
        
        sub_filename = os.path.basename(sub_path)
        sub_ext = os.path.splitext(sub_filename)[1]
        
        # 截取语言或特殊标记后缀部分 (例如: ABC-123.zh-CN.srt 截取得到 .zh-CN)
        prefix_len = len(video_base_old)
        sub_base_old, _ = os.path.splitext(sub_filename)
        lang_suffix = sub_base_old[prefix_len:]
        
        target_sub_name = f"{video_base_new}{lang_suffix}{sub_ext}"
        target_sub_path = os.path.join(target_dir, target_sub_name)
        
        if os.path.abspath(sub_path) != os.path.abspath(target_sub_path):
            try:
                os.rename(sub_path, target_sub_path)
                moved_subs.append(target_sub_path)
            except Exception:
                try:
                    # 降级方案
                    shutil.copyfile(sub_path, target_sub_path)
                    os.remove(sub_path)
                    moved_subs.append(target_sub_path)
                except Exception as e:
                    print(f"字幕文件移动重命名失败 {sub_path} -> {target_sub_path}: {e}")
                    
    return moved_subs
