"""
工具函数模块
提供数据导出、图片下载等功能
"""

import json
import re
import time
from pathlib import Path
from typing import List, Dict, Any
from urllib.parse import urlparse
from curl_cffi import requests
from bs4 import BeautifulSoup


def _request_timeout() -> int:
    """读取配置里的请求超时，避免散落的硬编码"""
    import config
    return config.JAVDB.get('timeout', 30)


def sanitize_filename(name: str, fallback: str = 'unnamed') -> str:
    """
    清理来自网页抓取的文件/目录名：剥掉路径成分，替换非法字符。
    防止演员名/文件名含 `/` 或 `..` 时写出目标目录。
    """
    name = Path(str(name)).name
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', name).strip().strip('.')
    return name or fallback


def url_ext(url: str, default: str = 'jpg') -> str:
    """从 URL 提取扩展名（先去 query 再取 suffix），异常值回退 default"""
    ext = Path(urlparse(url).path).suffix.lstrip('.')
    return ext if ext and len(ext) <= 5 and ext.isalnum() else default


class JSONExporter:
    """JSON 数据导出器"""
    
    def __init__(self, output_dir: str = None):
        if output_dir is None:
            import config
            output_dir = config.OUTPUT_DIR['json']
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def save_actor_works(self, actor_name: str, actor_id: str, 
                         works: List[Dict], actor_url: str) -> Dict:
        """
        保存演员作品数据
        
        Args:
            actor_name: 演员名字
            actor_id: 演员ID
            works: 作品列表
            actor_url: 演员URL
            
        Returns:
            导出数据字典
        """
        data = {
            "actor_name": actor_name,
            "actor_id": actor_id,
            "actor_url": actor_url,
            "works": works,
            "count": len(works)
        }
        
        filename = self.output_dir / f"{sanitize_filename(actor_name)}_works.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return data


class ImageDownloader:
    """图片下载器"""
    
    def __init__(self, session: requests.Session):
        self.session = session
    
    def download_thumbnails(self, code: str, image_urls: List[str], 
                           output_dir: str = None):
        """
        下载缩略图
        
        Args:
            code: 番号
            image_urls: 图片URL列表
            output_dir: 输出目录
        """
        if output_dir is None:
            import config
            output_dir = config.OUTPUT_DIR['images']
        video_dir = Path(output_dir) / sanitize_filename(code)
        video_dir.mkdir(parents=True, exist_ok=True)

        for i, url in enumerate(image_urls):
            try:
                response = self.session.get(url, timeout=_request_timeout())
                if response.status_code == 200:
                    ext = url_ext(url)
                    file_path = video_dir / f"{i:03d}.{ext}"
                    with open(file_path, 'wb') as f:
                        f.write(response.content)
                time.sleep(0.1)
            except Exception as e:
                print(f"下载失败 {url}: {e}")
    
    def download_images(self, video_id: str, image_urls: List[Dict[str, str]], 
                       output_dir: str = "output/images",
                       headers: Dict[str, str] = None) -> Dict[str, Any]:
        """
        通用图片下载方法（支持带 Referer 等请求头）
        
        Args:
            video_id: 视频 ID 或番号
            image_urls: 图片信息列表，每项包含 'url' 和可选的 'filename'
                例如: [
                    {'url': 'https://.../cover.jpg', 'filename': 'cover.jpg'},
                    {'url': 'https://.../sample1.jpg', 'filename': 'sample_01.jpg'},
                ]
            output_dir: 输出目录
            headers: 可选的自定义请求头（如 Referer）
            
        Returns:
            下载结果统计
            {
                'downloaded': 成功下载数量,
                'total': 总数量,
                'success_rate': 成功率,
                'download_dir': 下载目录,
                'files': [下载的文件路径列表]
            }
        """
        if output_dir is None:
            import config
            output_dir = config.OUTPUT_DIR['images']
        video_dir = Path(output_dir) / sanitize_filename(video_id)
        video_dir.mkdir(parents=True, exist_ok=True)
        
        downloaded = 0
        files = []
        request_headers = headers or {}
        
        for i, img_info in enumerate(image_urls):
            url = img_info.get('url', '')
            if not url:
                continue
                
            # 使用自定义文件名或自动生成；filename 可能来自网页数据，必须消毒
            filename = img_info.get('filename')
            if filename:
                filename = sanitize_filename(filename)
            else:
                filename = f"{i:03d}.{url_ext(url)}"

            file_path = video_dir / filename
            
            try:
                response = self.session.get(url, headers=request_headers, timeout=_request_timeout())
                if response.status_code == 200:
                    with open(file_path, 'wb') as f:
                        f.write(response.content)
                    downloaded += 1
                    files.append(str(file_path))
                    print(f"  ✅ 下载成功: {filename}")
                else:
                    print(f"  ⚠️ 下载失败 {filename}: HTTP {response.status_code}")
                time.sleep(0.1)
            except Exception as e:
                print(f"  ❌ 下载失败 {filename}: {e}")
        
        return {
            'downloaded': downloaded,
            'total': len(image_urls),
            'success_rate': round(downloaded / len(image_urls) * 100, 1) if image_urls else 0,
            'download_dir': str(video_dir),
            'files': files
        }


class MagnetExporter:
    """磁力链接导出器"""
    
    def __init__(self, output_dir: str = None):
        if output_dir is None:
            import config
            output_dir = config.OUTPUT_DIR['magnets']
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def save_magnets(self, works: List[Dict], filename: str):
        """
        保存磁力链接
        
        Args:
            works: 作品列表
            filename: 文件名
        """
        filepath = self.output_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            for work in works:
                f.write(f"{work.get('code', 'N/A')} - {work.get('title', 'N/A')}\n")
                for magnet in work.get('magnets', []):
                    f.write(f"  {magnet.get('magnet', '')}\n")
                    f.write(f"  大小: {magnet.get('size_text', 'N/A')}\n")
                f.write("\n")


class DataProcessor:
    """数据处理器"""
    
    @staticmethod
    def extract_hd_thumbnails(video_id: str, soup: BeautifulSoup) -> List[str]:
        """
        提取高清缩略图
        
        Args:
            video_id: 视频ID
            soup: BeautifulSoup对象
            
        Returns:
            图片URL列表（自动转换为高清图URL）
        """
        images = []
        
        # 尝试获取高清图
        hd_items = soup.select('.preview-images img')
        if hd_items:
            for img in hd_items:
                src = img.get('data-src') or img.get('src')
                if src:
                    # 将小图URL转换为高清图URL
                    # _s_ (small) -> _l_ (large)
                    hd_src = src.replace('_s_', '_l_')
                    images.append(hd_src)
        
        # 如果没有高清图，尝试普通图
        if not images:
            items = soup.select('.item-images img')
            for img in items:
                src = img.get('data-src') or img.get('src')
                if src:
                    # 同样转换为高清图URL
                    hd_src = src.replace('_s_', '_l_')
                    images.append(hd_src)
        
        return images
    
    @staticmethod
    def merge_video_detail(work: Dict, detail: Dict) -> Dict:
        """
        合并作品基础信息和详情
        
        Args:
            work: 基础信息
            detail: 详情信息
            
        Returns:
            合并后的数据
        """
        merged = work.copy()
        merged.update(detail)
        return merged
