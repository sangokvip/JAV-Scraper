"""
JAVDB API 库
提供统一的接口访问 JAVDB 和 JavBus 平台

================================================================================
================================ 7个核心 API ===================================
================================================================================

1. search_actor_works(actor_id, start=0, end=20, platform=None)
   搜索演员的作品ID列表（支持起始/结束个数，平台选择）

2. get_video_detail(video_id, platform=None)
   通过作品ID获取作品详细信息（平台选择）

3. download_video_images(video_id, output_dir, platform=None)
   通过作品ID下载高清预览图和封面（平台选择）

4. search_videos_by_tags(tag_names, start=0, end=20, platform=None)
   通过标签内容搜索作品ID列表（多标签，起始/结束个数，平台选择）

5. get_user_lists()
   搜索已登录用户的所有清单名称（仅javdb）

6. get_list_works(list_id, start=0, end=20)
   在某清单中搜索作品ID列表（起始/结束个数，仅javdb）

7. login()
   支持登录（仅javdb）

使用示例:
    >>> from lib import (
    ...     search_actor_works,
    ...     get_video_detail,
    ...     download_video_images,
    ...     search_videos_by_tags,
    ...     get_user_lists,
    ...     get_list_works,
    ...     login
    ... )
    
    >>> # 1. 获取演员作品
    >>> works = search_actor_works("0R1n3", start=0, end=20)
    
    >>> # 2. 获取作品详情
    >>> detail = get_video_detail("YwG8Ve")
    
    >>> # 3. 下载图片
    >>> result = download_video_images("YwG8Ve", output_dir="./images")
    
    >>> # 4. 标签搜索
    >>> works = search_videos_by_tags(["美少女", "水手服"], start=0, end=20)
    
    >>> # 5. 获取用户清单
    >>> lists = get_user_lists()
    
    >>> # 6. 获取清单作品
    >>> works = get_list_works("0W97k", start=0, end=20)
    
    >>> # 7. 登录
    >>> success = login()
"""

# 核心类
from javdb_api import JavdbAPI

# 适配器
from .adapter_factory import AdapterFactory
from .base_adapter import BaseAdapter
from .javdb_adapter import JavdbAdapter

# ================================================================================
# =============================== 7个核心 API 接口 ================================
# ================================================================================

from .external_api import (
    # 核心功能1: 搜索演员作品
    search_actor_works,
    # 核心功能2: 获取作品详情
    get_video_detail,
    # 核心功能3: 下载作品图片
    download_video_images,
    # 核心功能4: 标签搜索
    search_videos_by_tags,
    # 核心功能5: 获取用户清单
    get_user_lists,
    # 核心功能6: 获取清单作品
    get_list_works,
    # 核心功能7: 登录
    login,
)

# 其他 API 接口
from .external_api import (
    search_videos,
    get_video_by_code,
    get_movie_magnets,
    search_actor,
    get_actor_works,
    get_tag_works,
    search_by_tags,
    convert_to_standard_format,
    get_stats,
    get_supported_platforms,
    set_default_platform,
    get_adapter,
)

# 工具类
from .crypto_utils import CryptoUtils, DEFAULT_KEY
from .login import JavdbLogin, login as _login_internal, ensure_login
from .auto_login import AutoLogin, auto_login as _auto_login_internal
from .platform import Platform, add_platform_prefix, get_platform_by_name, remove_platform_prefix

__all__ = [
    # 核心类
    'JavdbAPI',
    
    # 适配器
    'AdapterFactory',
    'BaseAdapter',
    'JavdbAdapter',
    
    # ==================== 7个核心 API 接口 ====================
    'search_actor_works',      # 核心功能1: 搜索演员作品
    'get_video_detail',        # 核心功能2: 获取作品详情
    'download_video_images',   # 核心功能3: 下载作品图片
    'search_videos_by_tags',   # 核心功能4: 标签搜索
    'get_user_lists',          # 核心功能5: 获取用户清单
    'get_list_works',          # 核心功能6: 获取清单作品
    'login',                   # 核心功能7: 登录
    
    # 其他 API 接口
    'search_videos',
    'get_video_by_code',
    'get_movie_magnets',
    'search_actor',
    'get_actor_works',
    'get_tag_works',
    'search_by_tags',
    'convert_to_standard_format',
    'get_stats',
    'get_supported_platforms',
    'set_default_platform',
    'get_adapter',
    
    # 工具类
    'CryptoUtils',
    'DEFAULT_KEY',
    'JavdbLogin',
    'AutoLogin',
    'Platform',
    'add_platform_prefix',
    'get_platform_by_name',
    'remove_platform_prefix',
]
