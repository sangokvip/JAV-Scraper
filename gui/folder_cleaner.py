import os

def clean_empty_parent_dirs(parent_dirs) -> list[str]:
    """
    盘点被移动影片的原父目录。如果它们变为空（或仅有垃圾隐藏文件），
    且不是系统或用户的敏感路径，则加入待清理列表返回。
    
    Args:
        parent_dirs: 待检查的父目录路径集合或列表
        
    Returns:
        可以安全删除的空文件夹绝对路径列表
    """
    empty_dirs = []
    user_home = os.path.expanduser("~")
    
    # 敏感路径定义
    sensitive_paths = {
        os.path.abspath("/"),
        os.path.abspath(user_home),
        os.path.abspath(os.path.join(user_home, "Desktop")),
        os.path.abspath(os.path.join(user_home, "Documents")),
        os.path.abspath(os.path.join(user_home, "Downloads")),
        os.path.abspath(os.path.join(user_home, "Movies")),
        os.path.abspath(os.path.join(user_home, "Pictures")),
        os.path.abspath(os.path.join(user_home, "Music")),
    }
    
    for pdir in parent_dirs:
        if not pdir:
            continue
            
        abs_pdir = os.path.abspath(pdir)
        
        # 1. 安全验证：如果文件夹不存在或不是文件夹，则跳过
        if not os.path.exists(abs_pdir) or not os.path.isdir(abs_pdir):
            continue
            
        # 2. 安全验证：如果是敏感路径或者路径太短（长度小于等于10，防御根目录），则屏蔽
        if abs_pdir in sensitive_paths or len(abs_pdir) <= 10:
            continue
            
        try:
            items = os.listdir(abs_pdir)
            # 3. 排除无用系统小文件后，确认是否为空
            remaining = [item for item in items if item not in (".DS_Store", "Thumbs.db")]
            if not remaining:
                empty_dirs.append(abs_pdir)
        except Exception as e:
            print(f"检查文件夹空状态失败 {abs_pdir}: {e}")
            
    return empty_dirs
