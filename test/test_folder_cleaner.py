import os
import shutil
import tempfile
from gui.folder_cleaner import clean_empty_parent_dirs

def test_clean_empty_parent_dirs():
    # 创建临时测试根目录
    temp_root = tempfile.mkdtemp()
    try:
        # 1. 完全空文件夹
        empty_dir = os.path.join(temp_root, "empty")
        os.makedirs(empty_dir)
        
        # 2. 只有垃圾隐藏文件的文件夹
        trash_dir = os.path.join(temp_root, "trash")
        os.makedirs(trash_dir)
        with open(os.path.join(trash_dir, ".DS_Store"), "w") as f:
            f.write("")
            
        # 3. 非空文件夹（内含其他文件）
        non_empty_dir = os.path.join(temp_root, "non_empty")
        os.makedirs(non_empty_dir)
        with open(os.path.join(non_empty_dir, "movie.mp4"), "w") as f:
            f.write("fake video data")
            
        # 4. 模拟敏感路径（例如当前用户的 Desktop）
        user_home = os.path.expanduser("~")
        desktop_dir = os.path.abspath(os.path.join(user_home, "Desktop"))
        
        # 5. 不存在的路径
        fake_dir = os.path.join(temp_root, "does_not_exist")
        
        parent_dirs = {
            os.path.abspath(empty_dir),
            os.path.abspath(trash_dir),
            os.path.abspath(non_empty_dir),
            desktop_dir,
            os.path.abspath(fake_dir)
        }
        
        # 执行盘点
        result = clean_empty_parent_dirs(parent_dirs)
        
        # 验证结果
        assert os.path.abspath(empty_dir) in result
        assert os.path.abspath(trash_dir) in result
        assert os.path.abspath(non_empty_dir) not in result
        assert desktop_dir not in result
        assert os.path.abspath(fake_dir) not in result
        
    finally:
        shutil.rmtree(temp_root)
