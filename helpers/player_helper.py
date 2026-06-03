import os
import sys
import subprocess

def open_local_folder(path: str) -> bool:
    """
    在系统的文件管理器中打开指定的物理文件夹或文件所在的父目录。
    """
    if not path or not os.path.exists(path):
        return False
        
    dir_path = path if os.path.isdir(path) else os.path.dirname(path)
    
    try:
        if sys.platform == 'win32':
            os.startfile(dir_path)
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', dir_path])
        else:
            subprocess.Popen(['xdg-open', dir_path])
        return True
    except Exception as e:
        print(f"打开文件夹失败 {dir_path}: {e}")
        return False

def play_video(video_path: str, custom_player_path: str = "") -> bool:
    """
    使用系统关联的默认媒体播放器或用户配置的自定义播放器播放视频文件。
    """
    if not video_path or not os.path.exists(video_path) or os.path.isdir(video_path):
        return False
        
    try:
        # 如果指定了合法的自定义播放器路径
        if custom_player_path and os.path.exists(custom_player_path):
            if sys.platform == 'win32':
                subprocess.Popen([custom_player_path, video_path])
            elif sys.platform == 'darwin':
                if custom_player_path.endswith('.app'):
                    subprocess.Popen(['open', '-a', custom_player_path, video_path])
                else:
                    subprocess.Popen([custom_player_path, video_path])
            else:
                subprocess.Popen([custom_player_path, video_path])
            return True
            
        # 降级：调用系统关联的默认程序进行打开
        if sys.platform == 'win32':
            os.startfile(video_path)
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', video_path])
        else:
            subprocess.Popen(['xdg-open', video_path])
        return True
    except Exception as e:
        print(f"调用播放器播放视频失败 {video_path}: {e}")
        return False
