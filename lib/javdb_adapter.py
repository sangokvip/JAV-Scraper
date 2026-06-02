"""
JAVDB 平台适配器
负责将 JAVDB API 数据转换为系统标准格式
"""

import os
import sys
import time
import requests
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from urllib.parse import urljoin

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from bs4 import BeautifulSoup
from .base_adapter import BaseAdapter
from .platform import Platform
from javdb_api import JavdbAPI


class JavdbAdapter(BaseAdapter):
    """JAVDB 平台适配器"""
    
    def __init__(self, existing_tags: List[Dict] = None, domain_index: int = 0, proxies: dict = None):
        super().__init__(existing_tags)
        self.platform = Platform.JAVDB
        self.proxies = proxies
        self.api = JavdbAPI(domain_index=domain_index, proxies=proxies)
    
    def get_platform(self) -> Platform:
        """返回平台类型"""
        return self.platform
    
    def search_videos(self, keyword: str, page: int = 1, max_pages: int = 1) -> Dict[str, Any]:
        """
        搜索视频
        
        Args:
            keyword: 搜索关键词
            page: 起始页码
            max_pages: 最大搜索页数
            
        Returns:
            包含分页信息和视频列表的字典
        """
        results = []
        current_page = page
        has_next = True
        
        while current_page < page + max_pages and has_next:
            try:
                result = self.api.search_videos(keyword, page=current_page)
                
                if not result or not result.get('videos'):
                    has_next = False
                    break
                
                for video in result.get('videos', []):
                    results.append({
                        "video_id": video.get("video_id"),
                        "code": video.get("code", ""),
                        "title": video.get("title", ""),
                        "date": video.get("date", ""),
                        "tags": [],  # 搜索结果不包含标签
                        "actors": [],  # 搜索结果不包含演员
                        "cover_url": video.get("cover_url", ""),
                        "rating": video.get("rating", "")
                    })
                
                has_next = result.get("has_next", False)
                
                if has_next and current_page < page + max_pages - 1:
                    current_page += 1
                    time.sleep(0.5)  # 避免请求过快
                else:
                    break
                
            except Exception as e:
                print(f"搜索失败: {e}")
                has_next = False
                break
        
        return {
            "page": page,
            "has_next": has_next,
            "total_pages": None,  # JAVDB 不返回总页数
            "videos": results
        }
    
    def get_video_detail(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        获取视频详情
        
        Args:
            video_id: 视频原始ID
            
        Returns:
            视频详情字典
        """
        try:
            detail = self.api.get_video_detail(video_id, download_images=False)
            
            return {
                "video_id": detail.get("video_id"),
                "code": detail.get("code", ""),
                "title": detail.get("title", ""),
                "date": detail.get("date", ""),
                "tags": detail.get("tags", []),
                "actors": detail.get("actors", []),
                "actor_refs": detail.get("actor_refs", []),
                "series": detail.get("series", ""),
                "magnets": detail.get("magnets", []),
                "thumbnail_images": detail.get("thumbnail_images", []),
                "preview_video": detail.get("preview_video", ""),
                "cover_url": detail.get("thumbnail_images", [""])[0] if detail.get("thumbnail_images") else ""
            }
        except Exception as e:
            print(f"获取视频详情失败: {e}")
            return None
    
    def get_video_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """
        根据番号获取视频详情
        
        Args:
            code: 番号
            
        Returns:
            视频详情字典
        """
        try:
            detail = self.api.get_video_by_code(code, download_images=False)
            
            if not detail:
                return None
            
            return {
                "video_id": detail.get("video_id"),
                "code": detail.get("code", ""),
                "title": detail.get("title", ""),
                "date": detail.get("date", ""),
                "tags": detail.get("tags", []),
                "actors": detail.get("actors", []),
                "actor_refs": detail.get("actor_refs", []),
                "series": detail.get("series", ""),
                "magnets": detail.get("magnets", []),
                "thumbnail_images": detail.get("thumbnail_images", []),
                "preview_video": detail.get("preview_video", ""),
                "cover_url": detail.get("thumbnail_images", [""])[0] if detail.get("thumbnail_images") else ""
            }
        except Exception as e:
            print(f"根据番号获取视频失败: {e}")
            return None
    
    def search_actor(self, actor_name: str) -> List[Dict[str, Any]]:
        """
        搜索演员
        
        Args:
            actor_name: 演员名字
            
        Returns:
            演员列表
        """
        try:
            actors = self.api.search_actor(actor_name)
            normalized_actors = []
            for actor in actors or []:
                if not isinstance(actor, dict):
                    continue
                actor_id = str(actor.get("actor_id") or actor.get("id") or "").strip()
                name = str(actor.get("actor_name") or actor.get("name") or "").strip()
                if not actor_id:
                    continue
                normalized_actors.append({
                    **actor,
                    "id": actor_id,
                    "name": name,
                    "actor_id": actor_id,
                    "actor_name": name,
                    "actor_url": actor.get("actor_url") or actor.get("url") or "",
                })
            return normalized_actors
        except Exception as e:
            print(f"搜索演员失败: {e}")
            return []
    
    def get_actor_works(self, actor_id: str, page: int = 1, max_pages: int = 1) -> Dict[str, Any]:
        """
        获取演员作品
        
        Args:
            actor_id: 演员ID
            page: 起始页码
            max_pages: 最大页数
            
        Returns:
            作品列表和分页信息
        """
        try:
            all_works = []
            current_page = page
            has_next = True
            
            while has_next and current_page < page + max_pages:
                result = self.api.get_actor_works_by_page(actor_id, page=current_page)
                
                for work in result.get("works", []):
                    all_works.append({
                        "video_id": work.get("video_id"),
                        "code": work.get("code", ""),
                        "title": work.get("title", ""),
                        "date": work.get("date", ""),
                        "rating": work.get("rating", ""),
                        "tags": [],
                        "actors": [],
                        "cover_url": work.get("cover_url", "")
                    })
                
                has_next = result.get("has_next", False)
                current_page += 1
                
                if has_next:
                    time.sleep(0.5)
            
            return {
                "page": page,
                "has_next": has_next,
                "works": all_works
            }
        except Exception as e:
            print(f"获取演员作品失败: {e}")
            return {"page": page, "has_next": False, "works": []}
    
    def get_actor_works_full(self, actor_id: str, page: int = 1, max_pages: int = 1) -> Dict[str, Any]:
        """
        获取演员作品（包含完整详情）
        
        Args:
            actor_id: 演员ID
            page: 起始页码
            max_pages: 最大页数
            
        Returns:
            作品列表和分页信息（包含完整详情）
        """
        try:
            result = self.get_actor_works(actor_id, page, max_pages)
            
            full_works = []
            for work in result["works"]:
                try:
                    detail = self.get_video_detail(work["video_id"])
                    if detail:
                        full_works.append(detail)
                    else:
                        full_works.append(work)
                except Exception as e:
                    full_works.append(work)
                time.sleep(0.5)
            
            result["works"] = full_works
            return result
        except Exception as e:
            print(f"获取演员作品详情失败: {e}")
            return {"page": page, "has_next": False, "works": []}
    
    def get_tag_works(self, tag_id: str, page: int = 1, max_pages: int = 1) -> Dict[str, Any]:
        """
        获取标签作品
        
        Args:
            tag_id: 标签ID
            page: 起始页码
            max_pages: 最大页数
            
        Returns:
            作品列表和分页信息
        """
        try:
            all_works = []
            current_page = page
            has_next = True
            
            while has_next and current_page < page + max_pages:
                result = self.api.get_tag_works_by_page(tag_id, page=current_page)
                
                for work in result.get("works", []):
                    all_works.append({
                        "video_id": work.get("video_id"),
                        "code": work.get("code", ""),
                        "title": work.get("title", ""),
                        "date": work.get("date", ""),
                        "rating": work.get("rating", ""),
                        "tags": [],
                        "actors": [],
                        "cover_url": work.get("cover_url", "")
                    })
                
                has_next = result.get("has_next", False)
                current_page += 1
                
                if has_next:
                    time.sleep(0.5)
            
            return {
                "page": page,
                "has_next": has_next,
                "works": all_works
            }
        except Exception as e:
            print(f"获取标签作品失败: {e}")
            return {"page": page, "has_next": False, "works": []}
    
    def search_by_tags(self, page: int = 1, max_pages: int = 1, **tag_params) -> Dict[str, Any]:
        """
        多标签组合搜索
        
        Args:
            page: 起始页码
            max_pages: 最大页数
            **tag_params: 标签参数，如 c1=23, c3=78
            
        Returns:
            作品列表和分页信息
        """
        try:
            all_works = []
            current_page = page
            has_next = True
            
            while has_next and current_page < page + max_pages:
                result = self.api.search_by_tags(page=current_page, **tag_params)
                
                for work in result.get("works", []):
                    all_works.append({
                        "video_id": work.get("video_id"),
                        "code": work.get("code", ""),
                        "title": work.get("title", ""),
                        "date": work.get("date", ""),
                        "rating": work.get("rating", ""),
                        "tags": [],
                        "actors": [],
                        "cover_url": work.get("cover_url", "")
                    })
                
                has_next = result.get("has_next", False)
                current_page += 1
                
                if has_next:
                    time.sleep(0.5)
            
            return {
                "page": page,
                "has_next": has_next,
                "tag_params": tag_params,
                "works": all_works
            }
        except Exception as e:
            print(f"标签搜索失败: {e}")
            return {"page": page, "has_next": False, "tag_params": tag_params, "works": []}
    
    def download_video_images(self, video_id: str, download_dir: str) -> Tuple[int, int]:
        """
        下载视频缩略图到本地
        
        Args:
            video_id: 视频ID
            download_dir: 下载目录
            
        Returns:
            (成功下载数, 总数)
        """
        try:
            detail = self.api.get_video_detail(video_id, download_images=True)
            
            thumbnail_images = detail.get("thumbnail_images", [])
            if not thumbnail_images:
                return 0, 0
            
            # 创建下载目录
            video_dir = Path(download_dir) / video_id
            video_dir.mkdir(parents=True, exist_ok=True)
            
            success_count = 0
            
            for i, img_url in enumerate(thumbnail_images):
                try:
                    response = requests.get(img_url, timeout=30, proxies=self.proxies)
                    if response.status_code == 200:
                        ext = img_url.split('.')[-1].split('?')[0] or 'jpg'
                        file_path = video_dir / f"{i:03d}.{ext}"
                        with open(file_path, 'wb') as f:
                            f.write(response.content)
                        success_count += 1
                except Exception as e:
                    print(f"下载图片失败 {img_url}: {e}")
            
            return success_count, len(thumbnail_images)
        except Exception as e:
            print(f"下载视频图片失败: {e}")
            return 0, 0
    
    def convert_to_standard_format(self, videos: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
        """
        将平台数据转换为系统标准格式
        
        Args:
            videos: 平台原始数据列表
            
        Returns:
            标准格式的视频和标签数据
        """
        return self._convert_videos_to_standard(videos)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取请求统计
        
        Returns:
            请求统计信息
        """
        return self.api.get_stats()
