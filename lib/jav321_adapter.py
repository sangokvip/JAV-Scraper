"""
JAV321 平台适配器
负责将 JAV321 数据抓取并清洗转换为系统标准格式
"""

import os
import sys
import time
import requests
import concurrent.futures
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from .base_adapter import BaseAdapter
from .platform import Platform

def normalize_url(url: str, base_url: str = "https://www.jav321.com") -> str:
    if not url:
        return ""
    url = url.strip()
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return urljoin(base_url, url)
    return url

class Jav321Adapter(BaseAdapter):
    """JAV321 平台适配器"""
    
    def __init__(self, existing_tags: List[Dict] = None, proxies: dict = None):
        super().__init__(existing_tags)
        self.platform = Platform.JAV321
        self.proxies = proxies
        self.base_url = "https://www.jav321.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
        }
    
    def get_platform(self) -> Platform:
        """返回平台类型"""
        return self.platform

    def _request_get(self, url: str, timeout: int = 6) -> Optional[requests.Response]:
        """带代理降级容灾的 GET 请求"""
        # 1. 尝试使用代理
        if self.proxies:
            try:
                r = requests.get(url, headers=self.headers, proxies=self.proxies, timeout=timeout, allow_redirects=True)
                if r.status_code == 200:
                    return r
            except Exception as e:
                print(f"[JAV321 GET] 代理请求异常: {e}，正在尝试无代理直连...")
        
        # 2. 尝试无代理直连
        try:
            r = requests.get(url, headers=self.headers, timeout=timeout, allow_redirects=True)
            if r.status_code == 200:
                return r
        except Exception as e:
            print(f"[JAV321 GET] 直连请求异常: {e}")
        return None

    def _request_post(self, url: str, data: dict, timeout: int = 6) -> Optional[requests.Response]:
        """带代理降级容灾的 POST 请求"""
        # 1. 尝试使用代理
        if self.proxies:
            try:
                r = requests.post(url, headers=self.headers, data=data, proxies=self.proxies, timeout=timeout, allow_redirects=True)
                if r.status_code == 200:
                    return r
            except Exception as e:
                print(f"[JAV321 POST] 代理请求异常: {e}，正在尝试无代理直连...")
        
        # 2. 尝试无代理直连
        try:
            r = requests.post(url, headers=self.headers, data=data, timeout=timeout, allow_redirects=True)
            if r.status_code == 200:
                return r
        except Exception as e:
            print(f"[JAV321 POST] 直连请求异常: {e}")
        return None

    def _parse_html(self, html: str, final_url: str, fallback_code: str) -> Optional[Dict[str, Any]]:
        """解析 JAV321 HTML 页面内容"""
        soup = BeautifulSoup(html, "html.parser")
        
        h3 = soup.find("h3")
        title = h3.text.strip() if h3 else ""
        if not title:
            # 页面不含标题，解析失败
            return None
        
        video_id = final_url.rstrip("/").split("/")[-1]
        
        # 辅助函数：提取 b 标签后面的纯文本兄弟节点
        def get_clean_sibling_text(b_tag) -> str:
            siblings_text = []
            curr = b_tag.next_sibling
            while curr:
                if curr.name == "b" or curr.name == "br" or (curr.name == "div" and "col-md" not in curr.get("class", [])):
                    break
                if isinstance(curr, str):
                    siblings_text.append(curr.strip())
                elif curr.name == "a":
                    siblings_text.append(curr.text.strip())
                curr = curr.next_sibling
            value = "".join(siblings_text).strip()
            if value.startswith(":") or value.startswith("："):
                value = value[1:].strip()
            return value

        # 辅助函数：提取 b 标签随后的 a 标签列表文本
        def get_sibling_a_texts(b_tag) -> List[str]:
            curr = b_tag.next_sibling
            items = []
            while curr:
                if curr.name == "b" or curr.name == "br" or (curr.name == "div" and "col-md" not in curr.get("class", [])):
                    break
                if curr.name == "a":
                    items.append(curr.text.strip())
                curr = curr.next_sibling
            return [i for i in items if i]

        code = fallback_code
        date = ""
        series = ""
        maker = ""
        actors = []
        tags = []
        
        for b in soup.find_all("b"):
            key_clean = b.text.strip().replace(":", "").replace("：", "").strip()
            
            # 匹配演员
            if any(k in key_clean for k in ["出演者", "出演", "女优", "女優", "Cast", "cast"]):
                actors = get_sibling_a_texts(b)
            # 匹配标签
            elif any(k in key_clean for k in ["ジャンル", "类型", "类别", "标签", "Genre", "genre"]):
                tags = get_sibling_a_texts(b)
            # 匹配片商
            elif any(k in key_clean for k in ["メーカー", "制作商", "制作者", "片商", "Maker", "Studio", "maker", "studio"]):
                maker_list = get_sibling_a_texts(b)
                maker = maker_list[0] if maker_list else get_clean_sibling_text(b)
            # 匹配番号
            elif any(k in key_clean for k in ["品番", "番号", "Code", "code"]):
                code = get_clean_sibling_text(b) or fallback_code
            # 匹配日期
            elif any(k in key_clean for k in ["配信开始日", "配信開始日", "发行日期", "发布日期", "Release", "date"]):
                date = get_clean_sibling_text(b)
            # 匹配系列
            elif any(k in key_clean for k in ["シリーズ", "系列", "Series", "series"]):
                series = get_clean_sibling_text(b)

        # 提取海报大图
        cover_url = ""
        thumbnail_images = []
        for img in soup.find_all("img"):
            src = img.get("src")
            if not src:
                continue
            src_norm = normalize_url(src, self.base_url)
            
            # 大海报常以 pl.jpg 结尾
            if src.endswith("pl.jpg"):
                cover_url = src_norm
            # 剧照通常包含 jp-
            elif "jp-" in src and src.endswith(".jpg"):
                thumbnail_images.append(src_norm)
                
        # 兜底海报逻辑：若找不到 pl.jpg，则选取 ps.jpg 或包含番号的第一个有效大图
        if not cover_url:
            for img in soup.find_all("img"):
                src = img.get("src", "")
                if src.endswith("ps.jpg") or ("/video/" in src and src.endswith(".jpg")):
                    cover_url = normalize_url(src, self.base_url)
                    break
        
        # 提取磁力链接
        magnets = []
        for a in soup.find_all("a"):
            href = a.get("href", "")
            if href.startswith("magnet:"):
                magnets.append(href)

        # 提取预览视频
        preview_video = ""
        video_tag = soup.find("video")
        if video_tag:
            source_tag = video_tag.find("source")
            v_src = source_tag.get("src") if source_tag else video_tag.get("src")
            if v_src:
                preview_video = normalize_url(v_src, self.base_url)

        return {
            "video_id": video_id,
            "code": code,
            "title": title,
            "date": date,
            "tags": tags,
            "actors": actors,
            "maker": maker,
            "series": series,
            "magnets": magnets,
            "thumbnail_images": thumbnail_images,
            "preview_video": preview_video,
            "cover_url": cover_url
        }

    def get_video_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """根据番号获取视频详情"""
        search_url = f"{self.base_url}/search"
        # 统一使用大写以获取最佳检索匹配度
        data = {"sn": code.upper()}
        
        r = self._request_post(search_url, data)
        if not r:
            return None
        
        return self._parse_html(r.text, r.url, code)

    def get_video_detail(self, video_id: str) -> Optional[Dict[str, Any]]:
        """获取视频详情"""
        detail_url = f"{self.base_url}/video/{video_id}"
        r = self._request_get(detail_url)
        if not r:
            return None
        
        # fallback_code 先用其 video_id 代替，解析时若能抓取到品番会进行覆盖
        return self._parse_html(r.text, r.url, video_id)

    def search_videos(self, keyword: str, page: int = 1, max_pages: int = 1) -> Dict[str, Any]:
        """搜索视频 (通过 get_video_by_code 模拟)"""
        detail = self.get_video_by_code(keyword)
        videos = []
        if detail:
            videos.append({
                "video_id": detail["video_id"],
                "code": detail["code"],
                "title": detail["title"],
                "date": detail["date"],
                "tags": detail["tags"],
                "actors": detail["actors"],
                "cover_url": detail["cover_url"],
                "rating": ""
            })
        return {
            "page": page,
            "has_next": False,
            "total_pages": 1 if videos else 0,
            "videos": videos
        }

    def search_actor(self, actor_name: str) -> List[Dict[str, Any]]:
        return []

    def get_actor_works(self, actor_id: str, page: int = 1, max_pages: int = 1) -> Dict[str, Any]:
        return {"page": page, "has_next": False, "works": []}

    def get_tag_works(self, tag_id: str, page: int = 1, max_pages: int = 1) -> Dict[str, Any]:
        return {"page": page, "has_next": False, "works": []}

    def download_video_images(self, video_id: str, download_dir: str) -> Tuple[int, int]:
        """下载预览缩略图到本地"""
        detail = self.get_video_detail(video_id)
        if not detail:
            return 0, 0
        
        thumbnail_images = detail.get("thumbnail_images", [])
        if not thumbnail_images:
            return 0, 0

        video_dir = Path(download_dir) / video_id
        video_dir.mkdir(parents=True, exist_ok=True)
        
        success_count = 0
        
        def download_single(idx: int, img_url: str) -> bool:
            # 同样实施下载代理容灾
            try:
                headers = {"User-Agent": self.headers["User-Agent"]}
                if self.proxies:
                    try:
                        r = requests.get(img_url, headers=headers, proxies=self.proxies, timeout=10)
                        if r.status_code == 200:
                            ext = img_url.split('.')[-1].split('?')[0] or 'jpg'
                            file_path = video_dir / f"{idx:03d}.{ext}"
                            with open(file_path, 'wb') as f:
                                f.write(r.content)
                            return True
                    except Exception:
                        pass # 代理下载失败， fallback 到直连下载
                
                # 直连下载
                r = requests.get(img_url, headers=headers, timeout=10)
                if r.status_code == 200:
                    ext = img_url.split('.')[-1].split('?')[0] or 'jpg'
                    file_path = video_dir / f"{idx:03d}.{ext}"
                    with open(file_path, 'wb') as f:
                        f.write(r.content)
                    return True
            except Exception as e:
                print(f"[JAV321 Download] 下载图片失败 {img_url}: {e}")
            return False

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(download_single, i, url): url for i, url in enumerate(thumbnail_images)}
            for future in concurrent.futures.as_completed(futures):
                if future.result():
                    success_count += 1
                    
        return success_count, len(thumbnail_images)

    def convert_to_standard_format(self, videos: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
        """转换为系统标准格式"""
        return self._convert_videos_to_standard(videos)
