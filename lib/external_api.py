"""
统一的外部 API 接口
提供简洁的 API 调用接口，自动选择默认适配器

================================================================================
================================ 核心 API 接口 =================================
================================================================================

【7个核心功能】按重要性排序：

1. search_actor_works(actor_id, start=0, end=20, platform=None)
   搜索演员的作品ID列表（支持传入起始个数和结束个数）
   - platform: 'javdb'(默认) 或 'javbus'

2. get_video_detail(video_id, platform=None)
   通过作品ID获取作品的详细信息（标题、标签、作者、磁力链接等）
   - platform: 'javdb'(默认) 或 'javbus'

3. download_video_images(video_id, output_dir, platform=None)
   通过作品ID获取作品的高清预览图和封面并下载
   - platform: 'javdb'(默认) 或 'javbus'

4. search_videos_by_tags(tag_names, start=0, end=20, platform=None)
   通过标签的内容搜索作品ID列表，支持多个标签同时搜索
   - tag_names: 标签名称列表，如 ['美少女', '水手服']
   - platform: 'javdb'(默认) 或 'javbus'

5. get_user_lists()
   搜索已登录用户的所有清单名称（仅javdb）

6. get_list_works(list_id, start=0, end=20)
   在用户的某清单中搜索所有作品ID列表（支持传入起始个数和结束个数）（仅javdb）

7. login()
   支持登录（仅javdb）
"""

import os
import sys
import json
import time
from typing import Dict, List, Any, Optional
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from .platform import Platform
from .adapter_factory import AdapterFactory
from .base_adapter import BaseAdapter
from javdb_api import JavdbAPI


# 配置文件路径 (区分可写用户配置与内嵌默认配置)
from config import DATA_DIR, BUNDLE_DIR
CONFIG_FILE_USER = DATA_DIR / "third_party_config.json"
CONFIG_FILE_BUNDLE = BUNDLE_DIR / "third_party_config.json"

# 默认平台
DEFAULT_PLATFORM = Platform.JAVDB


def load_config() -> Dict[str, Any]:
    """加载配置文件"""
    config_file = CONFIG_FILE_USER if CONFIG_FILE_USER.exists() else CONFIG_FILE_BUNDLE
    if config_file.exists():
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "default_adapter": "javdb",
        "adapters": {
            "javdb": {
                "enabled": True,
                "domain_index": 0
            }
        }
    }


def save_config(config: Dict[str, Any]):
    """保存配置文件"""
    with open(CONFIG_FILE_USER, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def get_adapter(platform_name: str = None) -> BaseAdapter:
    """
    获取指定平台的适配器
    
    Args:
        platform_name: 平台名称，如果为None则使用默认平台
        
    Returns:
        适配器实例
    """
    if platform_name is None:
        config = load_config()
        platform_name = config.get("default_adapter", "javdb")
    
    return AdapterFactory.get_adapter_by_name(platform_name)


# ================================================================================
# =============================== 7个核心 API 接口 ================================
# ================================================================================


def search_actor_works(actor_id: str, start: int = 0, end: int = 20, 
                       platform: str = None) -> List[Dict[str, Any]]:
    """
    【核心功能1】搜索演员的作品ID列表
    
    支持传入起始个数和结束个数，返回指定范围的作品列表
    
    Args:
        actor_id: 演员ID
        start: 起始个数（从0开始）
        end: 结束个数（不包含）
        platform: 平台名称，'javdb'(默认) 或 'javbus'
        
    Returns:
        作品列表，每个作品包含 video_id, code, title, date 等
        
    Example:
        >>> # 获取演员前20个作品
        >>> works = search_actor_works("0R1n3", start=0, end=20)
        >>> for work in works:
        ...     print(f"{work['code']}: {work['title']}")
        
        >>> # 获取第21-40个作品
        >>> works = search_actor_works("0R1n3", start=20, end=40)
        
        >>> # 使用 JavBus 平台
        >>> works = search_actor_works("star_id", start=0, end=20, platform="javbus")
    """
    adapter = get_adapter(platform)
    
    # 计算需要的页数（假设每页约40个作品）
    page_size = 40
    start_page = start // page_size + 1
    end_page = (end - 1) // page_size + 1
    max_pages = end_page - start_page + 1
    
    # 获取作品
    result = adapter.get_actor_works(actor_id, page=start_page, max_pages=max_pages)
    works = result.get('works', [])
    
    # 计算在返回结果中的切片位置
    start_offset = start % page_size
    end_offset = start_offset + (end - start)
    
    return works[start_offset:end_offset]


def get_video_detail(video_id: str, platform: str = None) -> Optional[Dict[str, Any]]:
    """
    【核心功能2】通过作品ID获取作品的详细信息
    
    获取作品的完整信息，包括标题、标签、作者、磁力链接等
    
    Args:
        video_id: 作品ID
        platform: 平台名称，'javdb'(默认) 或 'javbus'
        
    Returns:
        作品详情字典，包含以下字段：
        - video_id: 作品ID
        - code: 番号
        - title: 标题
        - date: 发布日期
        - tags: 标签列表
        - actors: 演员列表
        - series: 系列名称
        - magnets: 磁力链接列表
        - thumbnail_images: 预览图URL列表
        - cover_url: 封面图URL
        失败返回 None
        
    Example:
        >>> detail = get_video_detail("YwG8Ve")
        >>> print(f"标题: {detail['title']}")
        >>> print(f"演员: {', '.join(detail['actors'])}")
        >>> print(f"标签: {', '.join(detail['tags'])}")
        >>> print(f"磁力链接: {len(detail['magnets'])} 个")
        
        >>> # 使用 JavBus 平台
        >>> detail = get_video_detail("SSIS-865", platform="javbus")
    """
    adapter = get_adapter(platform)
    return adapter.get_video_detail(video_id)


def download_video_images(video_id: str, output_dir: str = "output/images", 
                          platform: str = None) -> Dict[str, Any]:
    """
    【核心功能3】通过作品ID获取作品的高清预览图和封面并下载
    
    下载作品的所有预览图和封面图
    
    Args:
        video_id: 作品ID
        output_dir: 输出目录，默认为 "output/images"
        platform: 平台名称，'javdb'(默认) 或 'javbus'
        
    Returns:
        下载结果字典，包含：
        - downloaded: 成功下载数量
        - total: 总数量
        - success_rate: 成功率（百分比）
        - download_dir: 下载目录路径
        - files: 下载的文件路径列表
        
    Example:
        >>> result = download_video_images("YwG8Ve", output_dir="./images")
        >>> print(f"下载完成: {result['downloaded']}/{result['total']}")
        >>> print(f"保存位置: {result['download_dir']}")
        
        >>> # 使用 JavBus 平台
        >>> result = download_video_images("SSIS-865", platform="javbus")
    """
    adapter = get_adapter(platform)
    
    # 先获取视频详情
    detail = adapter.get_video_detail(video_id)
    if not detail:
        return {
            'downloaded': 0,
            'total': 0,
            'success_rate': 0,
            'download_dir': '',
            'files': [],
            'error': '获取视频详情失败'
        }
    
    # 准备图片URL列表
    image_urls = []
    
    # 添加封面图
    if detail.get('cover_url'):
        image_urls.append({
            'url': detail['cover_url'],
            'filename': 'cover.jpg'
        })
    
    # 添加预览图
    if detail.get('thumbnail_images'):
        for i, url in enumerate(detail['thumbnail_images']):
            image_urls.append({
                'url': url,
                'filename': f'preview_{i:03d}.jpg'
            })
    
    # 使用通用下载方法
    from javdb_api import download_video_images as _download_images
    
    # 构建 Referer 头
    headers = {'Referer': f"https://javdb.com/v/{video_id}"}
    
    return _download_images(
        video_id=detail.get('code', video_id),
        image_urls=image_urls,
        output_dir=output_dir,
        headers=headers
    )


def search_videos_by_tags(tag_names: List[str], start: int = 0, end: int = 20,
                          platform: str = None) -> List[Dict[str, Any]]:
    """
    【核心功能4】通过标签的内容搜索作品ID列表
    
    支持多个标签同时搜索，返回同时包含所有标签的作品
    
    Args:
        tag_names: 标签名称列表，如 ['美少女', '水手服']
        start: 起始个数（从0开始）
        end: 结束个数（不包含）
        platform: 平台名称，'javdb'(默认) 或 'javbus'
        
    Returns:
        作品列表，每个作品包含 video_id, code, title, date 等
        
    Note:
        - JavBus 不支持标签搜索，使用 JavBus 时会返回空列表
        - 标签名称支持简体中文自动转换为繁体中文
        
    Example:
        >>> # 单标签搜索
        >>> works = search_videos_by_tags(["美少女"], start=0, end=20)
        
        >>> # 多标签组合搜索（同时包含所有标签）
        >>> works = search_videos_by_tags(["美少女", "水手服"], start=0, end=20)
        
        >>> # 获取第21-40个结果
        >>> works = search_videos_by_tags(["美少女"], start=20, end=40)
    """
    adapter = get_adapter('javdb')
    
    # 使用标签管理器将标签名称转换为ID
    from .tag_manager import get_tag_by_name
    
    # 构建标签参数字典
    tag_params = {}
    for tag_name in tag_names:
        tag_info = get_tag_by_name(tag_name)
        if tag_info:
            tag_params[tag_info['category']] = tag_info['tag_id']
        else:
            print(f"警告: 未找到标签 '{tag_name}'")
    
    if not tag_params:
        return []
    
    # 计算需要的页数（假设每页约40个作品）
    page_size = 40
    start_page = start // page_size + 1
    end_page = (end - 1) // page_size + 1
    max_pages = end_page - start_page + 1
    
    # 执行搜索
    result = adapter.search_by_tags(page=start_page, max_pages=max_pages, **tag_params)
    works = result.get('works', [])
    
    # 计算在返回结果中的切片位置
    start_offset = start % page_size
    end_offset = start_offset + (end - start)
    
    return works[start_offset:end_offset]


def get_user_lists() -> List[Dict[str, Any]]:
    """
    【核心功能5】搜索已登录用户的所有清单名称
    
    获取当前登录用户的所有清单（想看、看过、自定义清单等）
    
    Returns:
        清单列表，每个清单包含：
        - list_id: 清单ID
        - list_name: 清单名称
        - list_url: 清单URL
        - video_count: 视频数量
        
    Note:
        - 此功能仅支持 JAVDB 平台
        - 需要先登录才能使用
        
    Example:
        >>> lists = get_user_lists()
        >>> for lst in lists:
        ...     print(f"{lst['list_name']}: {lst['video_count']} 个作品")
    """
    # 此功能仅支持 JAVDB
    adapter = get_adapter('javdb')
    
    # 使用 JAVDB API 获取所有清单
    api = JavdbAPI()
    result = api.get_user_lists_all(max_pages=100)
    
    return result


def get_list_works(list_id: str, start: int = 0, end: int = 20) -> List[Dict[str, Any]]:
    """
    【核心功能6】在用户的某清单中搜索所有作品ID列表
    
    获取指定清单中的作品列表，支持传入起始个数和结束个数
    
    Args:
        list_id: 清单ID
        start: 起始个数（从0开始）
        end: 结束个数（不包含）
        
    Returns:
        作品列表，每个作品包含 video_id, code, title, date 等
        
    Note:
        - 此功能仅支持 JAVDB 平台
        - 需要先登录才能使用
        
    Example:
        >>> # 获取清单前20个作品
        >>> works = get_list_works("0W97k", start=0, end=20)
        
        >>> # 获取第21-40个作品
        >>> works = get_list_works("0W97k", start=20, end=40)
    """
    # 此功能仅支持 JAVDB
    api = JavdbAPI()
    
    # 计算需要的页数（假设每页约40个作品）
    page_size = 40
    start_page = start // page_size + 1
    end_page = (end - 1) // page_size + 1
    max_pages = end_page - start_page + 1
    
    # 获取清单作品
    all_works = []
    current_page = start_page
    
    while current_page <= start_page + max_pages - 1:
        result = api.get_list_detail(list_id, page=current_page)
        works = result.get('works', [])
        all_works.extend(works)
        
        if not result.get('has_next', False):
            break
        
        current_page += 1
        time.sleep(0.5)
    
    # 计算在返回结果中的切片位置
    start_offset = start % page_size
    end_offset = start_offset + (end - start)
    
    return all_works[start_offset:end_offset]


def login() -> bool:
    """
    【核心功能7】支持登录
    
    引导用户完成 JAVDB 登录流程，保存登录凭证
    
    Returns:
        登录是否成功
        
    Note:
        - 此功能仅支持 JAVDB 平台
        - 会打开浏览器引导用户完成登录
        - 登录凭证会保存到 cookies.json
        
    Example:
        >>> success = login()
        >>> if success:
        ...     print("登录成功")
        ... else:
        ...     print("登录失败")
    """
    # 此功能仅支持 JAVDB
    from .auto_login import auto_login
    return auto_login()


# ================================================================================
# ============================ 其他辅助 API 接口 ==================================
# ================================================================================


def search_videos(keyword: str, max_pages: int = 1, platform: str = None,
                   movie_type: str = None, **kwargs) -> List[Dict[str, Any]]:
    """
    搜索视频
    
    Args:
        keyword: 搜索关键词
        max_pages: 最大搜索页数
        platform: 平台名称，默认使用配置中的默认平台
        movie_type: 影片类型，仅 JavBus 支持 ('normal'/'uncensored')
        **kwargs: 其他平台特定参数
        
    Returns:
        视频列表
        
    Example:
        >>> videos = search_videos("SSIS", max_pages=2)
        >>> for video in videos:
        ...     print(f"{video['code']}: {video['title']}")
        
        >>> # JavBus 搜索无码影片
        >>> videos = search_videos("SSIS", platform="javbus", movie_type="uncensored")
    """
    adapter = get_adapter(platform)
    
    # 如果适配器支持 movie_type 参数
    if movie_type is not None:
        return adapter.search_videos(keyword, max_pages, movie_type=movie_type, **kwargs)
    
    return adapter.search_videos(keyword, max_pages, **kwargs)


def get_video_by_code(code: str, platform: str = None, 
                      movie_type: str = None) -> Optional[Dict[str, Any]]:
    """
    根据番号获取视频详情
    
    Args:
        code: 番号（如 MIDA-583）
        platform: 平台名称
        movie_type: 影片类型，仅 JavBus 支持 ('normal'/'uncensored')
        
    Returns:
        视频详情字典，失败返回None
        
    Example:
        >>> detail = get_video_by_code("MIDA-583")
        >>> print(detail['title'])
        
        >>> # JavBus 获取无码影片
        >>> detail = get_video_by_code("SSIS-865", platform="javbus", movie_type="uncensored")
    """
    adapter = get_adapter(platform)
    
    # JAVDB 适配器有特殊方法
    if hasattr(adapter, 'get_video_by_code'):
        return adapter.get_video_by_code(code)
    
    return None


def get_movie_magnets(video_id: str, platform: str = None, 
                      sort_by: str = 'size', sort_order: str = 'desc',
                      **kwargs) -> List[Dict[str, Any]]:
    """
    获取影片磁力链接
    
    Args:
        video_id: 视频ID/番号
        platform: 平台名称
        sort_by: 排序方式 'size'(大小) 或 'date'(日期)
        sort_order: 排序顺序 'asc'(升序) 或 'desc'(降序)
        **kwargs: 其他参数
        
    Returns:
        磁力链接列表
    """
    adapter = get_adapter(platform)
    detail = adapter.get_video_detail(video_id)
    if detail and 'magnets' in detail:
        return detail['magnets']
    
    return []


def search_actor(actor_name: str, platform: str = None) -> List[Dict[str, Any]]:
    """
    搜索演员
    
    Args:
        actor_name: 演员名字
        platform: 平台名称
        
    Returns:
        演员列表
        
    Example:
        >>> actors = search_actor("井上もも")
        >>> for actor in actors:
        ...     print(f"{actor['actor_name']}: {actor['actor_id']}")
    """
    adapter = get_adapter(platform)
    return adapter.search_actor(actor_name)


def get_actor_works(actor_id: str, page: int = 1, max_pages: int = 1, 
                    full_detail: bool = False, platform: str = None) -> Dict[str, Any]:
    """
    获取演员作品（分页方式）
    
    Args:
        actor_id: 演员ID
        page: 起始页码
        max_pages: 最大页数
        full_detail: 是否获取完整详情
        platform: 平台名称
        
    Returns:
        作品列表和分页信息
        
    Example:
        >>> result = get_actor_works("0R1n3", max_pages=2)
        >>> for work in result['works']:
        ...     print(f"{work['code']}: {work['title']}")
    """
    adapter = get_adapter(platform)
    
    # JAVDB 适配器有特殊方法
    if full_detail and hasattr(adapter, 'get_actor_works_full'):
        return adapter.get_actor_works_full(actor_id, page, max_pages)
    
    return adapter.get_actor_works(actor_id, page, max_pages)


def get_tag_works(tag_id: str, page: int = 1, max_pages: int = 1, 
                  platform: str = None) -> Dict[str, Any]:
    """
    获取标签作品
    
    Args:
        tag_id: 标签ID
        page: 起始页码
        max_pages: 最大页数
        platform: 平台名称
        
    Returns:
        作品列表和分页信息
    """
    adapter = get_adapter(platform)
    return adapter.get_tag_works(tag_id, page, max_pages)


def search_by_tags(page: int = 1, max_pages: int = 1, platform: str = None, 
                   **tag_params) -> Dict[str, Any]:
    """
    多标签组合搜索（通过标签ID）
    
    Args:
        page: 起始页码
        max_pages: 最大页数
        platform: 平台名称
        **tag_params: 标签参数，如 c1=23, c3=78
        
    Returns:
        作品列表和分页信息
        
    Example:
        >>> result = search_by_tags(c1=23, c3=78)
        >>> for work in result['works']:
        ...     print(f"{work['code']}: {work['title']}")
    """
    adapter = get_adapter(platform)
    
    # JAVDB 适配器有特殊方法
    if hasattr(adapter, 'search_by_tags'):
        return adapter.search_by_tags(page, max_pages, **tag_params)
    
    return {"page": page, "has_next": False, "works": []}


def convert_to_standard_format(videos: List[Dict[str, Any]], 
                                platform: str = None) -> Dict[str, List[Dict]]:
    """
    将平台数据转换为系统标准格式
    
    Args:
        videos: 视频数据列表
        platform: 平台名称
        
    Returns:
        标准格式的视频和标签数据
        
    Example:
        >>> videos = search_videos("SSIS")
        >>> data = convert_to_standard_format(videos)
        >>> print(f"视频数: {len(data['videos'])}")
        >>> print(f"标签数: {len(data['tags'])}")
    """
    adapter = get_adapter(platform)
    return adapter.convert_to_standard_format(videos)


def get_stats(platform: str = None) -> Dict[str, Any]:
    """
    获取请求统计
    
    Args:
        platform: 平台名称
        
    Returns:
        请求统计信息
    """
    adapter = get_adapter(platform)
    
    if hasattr(adapter, 'get_stats'):
        return adapter.get_stats()
    
    return {}


def get_supported_platforms() -> List[str]:
    """
    获取支持的平台列表
    
    Returns:
        平台名称列表
    """
    platforms = AdapterFactory.get_supported_platforms()
    return [p.value for p in platforms]


def set_default_platform(platform_name: str):
    """
    设置默认平台
    
    Args:
        platform_name: 平台名称
    """
    config = load_config()
    config["default_adapter"] = platform_name
    save_config(config)
