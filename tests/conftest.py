import os
import sys

# 保证从任意工作目录运行 pytest 都能 import 项目模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
