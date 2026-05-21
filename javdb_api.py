"""
JAVDB API 核心模块
提供视频、演员、Tag 搜索和数据抓取功能

对外暴露的主要接口:
- get_video_detail: 抓取作品页全量信息
- get_video_by_code: 根据code搜索并获取详情
- get_actor_works_by_page: 获取演员作品（分页，只返回code等基础信息）
- get_actor_works_full_by_page: 获取演员作品全量信息（分页）
- get_tag_works_by_page: 获取Tag作品（分页，只返回code等基础信息）
- get_tag_works_full_by_page: 获取Tag作品全量信息（分页）
- search_by_tags: 多类标签组合搜索（基础信息）
- search_by_tags_full: 多类标签组合搜索（全量信息）
- search_actor: 搜索演员
- scrape_actor_full: 全量抓取演员所有信息

标签管理模块 (tag_manager):
- get_tag_by_name: 通过标签名称获取标签信息（支持简体自动转繁体）
- get_tag_by_id: 通过标签ID获取标签信息
- search_tags_by_keyword: 通过关键词模糊搜索标签（支持简体自动转繁体）
- convert_to_traditional: 简体转换为繁体
- TagManager: 标签管理器类

图片下载模块:
- download_video_images: 通用图片下载方法（支持自定义请求头）
- download_video_detail_images: 获取视频详情并下载所有缩略图

使用示例:
    # 通过标签名称获取标签ID（自动处理简繁转换）
    >>> tag = get_tag_by_name("美少女")
    >>> print(tag['id'])  # c1=23
    
    # 通过标签ID获取标签名称
    >>> tag = get_tag_by_id("c1=23")
    >>> print(tag['name'])  # 美少女
    
    # 模糊搜索标签
    >>> tags = search_tags_by_keyword("女")
    >>> for tag in tags:
    ...     print(f"{tag['name']}: {tag['id']}")
"""

import re
import json
import time
from typing import List, Dict, Optional, Any
from urllib.parse import urljoin, quote
from pathlib import Path
from datetime import datetime

from curl_cffi import requests
from bs4 import BeautifulSoup

import config
from utils import JSONExporter, ImageDownloader, MagnetExporter, DataProcessor


class JavdbAPI:
    """
    JAVDB API 客户端
    
    提供以下功能：
    - 视频详情抓取（番号、标题、磁力链接、Tags、缩略图等）
    - 演员搜索和作品抓取（支持分页）
    - Tag 搜索和作品抓取（支持分页）
    - 根据番号搜索获取详情
    - 缩略图下载（自动使用高清图）
    
    示例:
        >>> api = JavdbAPI()
        >>> detail = api.get_video_detail("YwG8Ve", download_images=True)
        >>> print(detail['code'])  # MIDA-583
    """
    
    def __init__(self, domain_index: int = 0):
        """
        初始化 API 客户端
        
        Args:
            domain_index: 域名索引，用于自动切换域名
        """
        self.domain_index = domain_index
        self.session = requests.Session()
        self.session.headers.update(config.HEADERS)
        
        self._load_cookies()
        
        self.request_count = 0
        self.success_count = 0
        
        self.image_downloader = ImageDownloader(self.session)
        self.json_exporter = JSONExporter()
        self.magnet_exporter = MagnetExporter()
        
        # 初始化标签管理器（延迟加载）
        self._tag_manager = None
    
    @property
    def tag_manager(self):
        """获取标签管理器实例（延迟加载）"""
        if self._tag_manager is None:
            from lib.tag_manager import TagManager
            self._tag_manager = TagManager()
        return self._tag_manager
    
    def _resolve_tag_params(self, **params) -> Dict[str, int]:
        """
        解析标签参数，将标签名称转换为标签ID
        
        支持三种格式：
        1. 直接指定ID: c1=23, c3=78
        2. 通过名称查找（带分类前缀）: tag_主題="美少女", tag_服裝="水手服"
        3. 直接标签名称（最简单）: 淫亂真實="", 美少女="", 水手服=""
           或 tags=["淫亂真實", "水手服"]
        
        Args:
            **params: 标签参数
            
        Returns:
            转换后的标签参数字典
        """
        result = {}
        
        # 处理 tags 参数（列表格式）
        if 'tags' in params and isinstance(params['tags'], list):
            for tag_name in params['tags']:
                self._resolve_single_tag(tag_name, result)
            return result
        
        for key, value in params.items():
            if key.startswith('c') and key[1:].isdigit():
                # 直接指定ID格式: c1=23
                result[key] = int(value) if isinstance(value, str) else value
            elif key.startswith('tag_'):
                # 通过名称查找格式: tag_主題="美少女"
                tag_name = value if value else key[4:]  # 如果值为空，使用key的后缀作为标签名
                self._resolve_single_tag(tag_name, result)
            elif key in ['tags', 'page', 'download_images', 'max_pages']:
                # 保留特殊参数，不处理
                continue
            else:
                # 其他情况：key 可能是标签名称
                # 例如: 淫亂真實="", 美少女=""
                tag_name = key if not value else value
                self._resolve_single_tag(tag_name, result)
        
        return result
    
    def _resolve_single_tag(self, tag_name: str, result: Dict[str, int]):
        """
        解析单个标签名称并添加到结果中
        
        Args:
            tag_name: 标签名称
            result: 结果字典
        """
        # 查找标签
        tag_info = self.tag_manager.get_tag_by_name(tag_name)
        if tag_info:
            category = tag_info['category']
            tag_id = tag_info['tag_id']
            result[category] = tag_id
            print(f"✓ 找到标签 '{tag_name}' -> {category}={tag_id}")
        else:
            # 尝试搜索相似标签
            similar_tags = self.tag_manager.search_tags_by_keyword(tag_name)
            if similar_tags:
                tag_info = similar_tags[0]
                category = tag_info['category']
                tag_id = tag_info['tag_id']
                result[category] = tag_id
                print(f"⚠ 未找到精确匹配 '{tag_name}'，使用相似标签 '{tag_info['name']}' -> {category}={tag_id}")
            else:
                raise ValueError(f"未找到标签: '{tag_name}'，请检查标签名称是否正确")
    
    @property
    def base_url(self) -> str:
        """获取当前基础 URL"""
        return f"https://{config.JAVDB['domains'][self.domain_index]}"
    
    def _load_cookies(self):
        """从文件加载 cookies"""
        cookie_path = Path(config.COOKIE_FILE)
        if cookie_path.exists():
            try:
                with open(cookie_path, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                    self.session.cookies.update(cookies)
            except Exception as e:
                pass
    
    def _get_full_url(self, path: str) -> str:
        """获取完整 URL"""
        if path.startswith('http'):
            return path
        return urljoin(self.base_url, path)
    
    def _switch_domain(self):
        """切换到下一个域名"""
        self.domain_index = (self.domain_index + 1) % len(config.JAVDB['domains'])
    
    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        """
        发送 HTTP 请求，支持自动重试和域名切换
        
        Args:
            method: 请求方法 (get/post)
            path: 请求路径
            **kwargs: 其他请求参数
            
        Returns:
            响应对象
        """
        url = self._get_full_url(path)
        kwargs.setdefault('timeout', config.JAVDB['timeout'])
        kwargs.setdefault('allow_redirects', True)
        
        last_exception = None
        
        for retry in range(config.JAVDB['retry_times']):
            try:
                self.request_count += 1
                
                if method.lower() == 'get':
                    response = self.session.get(url, **kwargs)
                else:
                    response = self.session.post(url, **kwargs)
                
                if response.status_code == 200:
                    self.success_count += 1
                    return response
                
                if response.status_code in [403, 503]:
                    self._switch_domain()
                    url = self._get_full_url(path)
                    continue
                
                response.raise_for_status()
                
            except Exception as e:
                last_exception = e
                time.sleep(2)
        
        raise Exception(f"请求失败: {last_exception}")
    
    def get(self, path: str, **kwargs) -> requests.Response:
        """发送 GET 请求"""
        return self.request('get', path, **kwargs)
    
    def get_stats(self) -> Dict:
        """获取请求统计"""
        return {
            'request_count': self.request_count,
            'success_count': self.success_count,
            'success_rate': f"{(self.success_count / self.request_count * 100):.1f}%" if self.request_count > 0 else "0%",
        }
    
    # ==================== 视频详情 ====================
    
    def get_video_detail(self, video_id: str, download_images: bool = False) -> Dict:
        """
        抓取作品页全量信息
        
        Args:
            video_id: 视频 ID (如 YwG8Ve)
            download_images: 是否下载缩略图（自动使用高清图）
            
        Returns:
            包含番号、标题、磁力链接、Tags、缩略图等信息的字典
            
            返回格式:
            {
                'video_id': 'YwG8Ve',
                'code': 'MIDA-583',
                'title': '作品标题',
                'tags': ['美少女電影', '單體作品', ...],
                'series': '系列名',
                'actors': ['井上もも'],
                'magnets': [
                    {'magnet': 'magnet:...', 'size_text': '5.27GB', 'size_mb': 5396.48}
                ],
                'thumbnail_images': [
                    'https://c0.jdbstatic.com/samples/yw/YwG8Ve_l_0.jpg',
                    ...
                ],
                'preview_video': '',
                'url': 'https://javdb.com/v/YwG8Ve'
            }
        """
        response = self.get(f'/v/{video_id}')
        soup = BeautifulSoup(response.text, 'lxml')
        
        title = self._extract_title(soup)
        code = self._extract_code(soup)
        date = self._extract_date(soup)
        tags = self._extract_tags(soup)
        series = self._extract_series(soup)
        actor_entries = self._extract_actor_entries(soup)
        actors = [entry.get("actor_name", "") for entry in actor_entries if entry.get("actor_name")]
        actor_refs = [entry for entry in actor_entries if entry.get("actor_id")]
        magnets = self._extract_magnets(soup)
        thumbnail_images = DataProcessor.extract_hd_thumbnails(video_id, soup)
        preview_video = self._extract_preview_video(soup)
        
        cover_url = ""
        if thumbnail_images and len(thumbnail_images) > 0:
            cover_url = thumbnail_images[0]
        
        result = {
            'video_id': video_id,
            'title': title,
            'code': code,
            'date': date,
            'tags': tags,
            'series': series,
            'actors': actors,
            'actor_refs': actor_refs,
            'magnets': magnets,
            'thumbnail_images': thumbnail_images,
            'preview_video': preview_video,
            'cover_url': cover_url,
            'url': response.url,
        }
        
        if download_images and thumbnail_images and code:
            self.image_downloader.download_thumbnails(code, thumbnail_images)
        
        return result
    
    def get_video_by_code(self, code: str, download_images: bool = False) -> Optional[Dict]:
        """
        根据番号搜索并获取作品全量信息
        
        搜索code，模糊匹配到的第一个结果就是
        
        Args:
            code: 番号 (如 MIDA-583, SSIS-001)
            download_images: 是否下载缩略图
            
        Returns:
            视频详情字典，如果未找到返回 None
        """
        encoded_code = quote(code)
        url = f"/search?q={encoded_code}"
        
        response = self.get(url)
        soup = BeautifulSoup(response.text, 'lxml')
        
        items = soup.select('div.item a')
        if not items:
            return None
        
        first_item = items[0]
        work = self._parse_work_item(first_item)
        
        if not work:
            return None
        
        return self.get_video_detail(work['video_id'], download_images)
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """提取标题"""
        selectors = ['h1.title', '.video-title', 'h1', 'title']
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                title = elem.get_text(strip=True)
                title = re.sub(r'\|.*$', '', title)
                return title
        return ""
    
    def _extract_code(self, soup: BeautifulSoup) -> str:
        """提取番号（字母+数字+中划线）"""
        copy_btn = soup.select_one('.panel-block.first-block .copy-to-clipboard')
        if copy_btn:
            code = copy_btn.get('data-clipboard-text', '')
            if code and re.match(r'^[A-Z]+-?\d+$', code, re.I):
                return code.upper()
        
        title_elem = soup.select_one('h1.title, .video-title')
        if title_elem:
            text = title_elem.get_text(strip=True)
            match = re.search(r'([A-Z]{2,6}-?\d{2,5})', text, re.I)
            if match:
                return match.group(1).upper()
        
        return ""
    
    def _extract_tags(self, soup: BeautifulSoup) -> List[str]:
        """提取 Tags（類別）"""
        tags = []
        
        tag_sections = soup.select('.panel-block')
        for section in tag_sections:
            strong_elem = section.select_one('strong')
            if strong_elem and '類別' in strong_elem.get_text():
                tag_links = section.select('a')
                for tag_link in tag_links:
                    tag_name = tag_link.get_text(strip=True)
                    if tag_name:
                        tags.append(tag_name)
                break
        
        return tags
    
    def _extract_series(self, soup: BeautifulSoup) -> str:
        """提取系列"""
        tag_sections = soup.select('.panel-block')
        for section in tag_sections:
            strong_elem = section.select_one('strong')
            if strong_elem and '系列' in strong_elem.get_text():
                series_link = section.select_one('a')
                if series_link:
                    return series_link.get_text(strip=True)
        return ""
    
    def _extract_date(self, soup: BeautifulSoup) -> str:
        """提取日期"""
        tag_sections = soup.select('.panel-block')
        for section in tag_sections:
            strong_elem = section.select_one('strong')
            if strong_elem and '日期' in strong_elem.get_text():
                date_text = section.get_text(strip=True)
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', date_text)
                if date_match:
                    return date_match.group(1)
        return ""
    
    def _extract_actor_entries(self, soup: BeautifulSoup) -> List[Dict]:
        """提取演员列表及演员页 ID。"""
        actor_entries = []
        
        tag_sections = soup.select('.panel-block')
        for section in tag_sections:
            strong_elem = section.select_one('strong')
            if strong_elem and '演員' in strong_elem.get_text():
                actor_links = section.select('a')
                for actor_link in actor_links:
                    actor_name = actor_link.get_text(strip=True)
                    if not actor_name or actor_name in ['♀', '♂']:
                        continue

                    href = str(actor_link.get('href') or '').strip()
                    match = re.search(r'/actors/([^/?#]+)', href)
                    actor_id = match.group(1) if match else ''
                    entry = {
                        'id': actor_id,
                        'actor_id': actor_id,
                        'name': actor_name,
                        'actor_name': actor_name,
                        'actor_url': urljoin(self.base_url, href) if href else '',
                    }
                    actor_entries.append(entry)
                break
        
        return actor_entries

    def _extract_actors(self, soup: BeautifulSoup) -> List[str]:
        """提取演员名称列表。"""
        return [
            entry.get('actor_name', '')
            for entry in self._extract_actor_entries(soup)
            if entry.get('actor_name')
        ]
    
    def _extract_magnets(self, soup: BeautifulSoup) -> List[Dict]:
        """提取磁力链接"""
        magnets = []
        container = soup.select_one('#magnets-content')
        if not container:
            return magnets
        
        items = container.select('.item')
        for item in items:
            try:
                copy_btn = item.select_one('.copy-to-clipboard')
                if not copy_btn:
                    continue
                
                magnet = copy_btn.get('data-clipboard-text', '')
                if not magnet or not magnet.startswith('magnet:'):
                    continue
                
                meta = item.select_one('.meta')
                size_text = meta.get_text(strip=True) if meta else "未知大小"
                size_mb = self._parse_size(size_text)
                
                magnets.append({
                    'magnet': magnet,
                    'size_text': size_text,
                    'size_mb': size_mb,
                })
            except:
                continue
        
        magnets.sort(key=lambda x: x['size_mb'], reverse=True)
        return magnets
    
    def _extract_preview_video(self, soup: BeautifulSoup) -> str:
        """提取预览视频链接"""
        for selector, attr_names in (
            ('video source', ('src', 'data-src')),
            ('video', ('src', 'data-src')),
            ('.preview-video video source', ('src', 'data-src')),
            ('.preview-video video', ('src', 'data-src')),
            ('.video-preview video source', ('src', 'data-src')),
            ('.video-preview video', ('src', 'data-src')),
            ('source[type=\"application/x-mpegURL\"]', ('src', 'data-src')),
            ('source[type^=\"video/\"]', ('src', 'data-src')),
            ('[data-url]', ('data-url',)),
        ):
            for node in soup.select(selector):
                for attr_name in attr_names:
                    src = str(node.get(attr_name, '') or '').strip()
                    if not src:
                        continue
                    if src.startswith('//'):
                        return f'https:{src}'
                    if src.startswith('/'):
                        return urljoin(self.base_url, src)
                    return src

        return ""
    
    def _parse_size(self, size_text: str) -> float:
        """解析文件大小为 MB"""
        match = re.search(r'([\d.]+)\s*(GB|MB)', size_text, re.I)
        if not match:
            return 0
        size = float(match[1])
        unit = match[2].upper()
        return size * 1024 if unit == 'GB' else size
    
    # ==================== 演员搜索 ====================
    
    def search_actor(self, actor_name: str) -> List[Dict]:
        """
        搜索演员
        
        Args:
            actor_name: 演员名字
            
        Returns:
            演员列表，每个演员包含 name, actor_id, url
        """
        normalized_actor_name = str(actor_name or "").strip()
        encoded_name = quote(normalized_actor_name)
        url = f"/search?q={encoded_name}&f=actor"
        
        response = self.get(url)
        soup = BeautifulSoup(response.text, 'lxml')
        
        actors = []
        actor_items = soup.select('.actor-box, .actors .item, a[href^="/actors/"]')
        seen_actor_ids = set()
        
        for item in actor_items:
            try:
                link_elem = item if getattr(item, "name", "") == "a" else item.select_one('a[href^="/actors/"]')
                if not link_elem:
                    continue
                
                href = link_elem.get('href', '')
                title = link_elem.get('title', '')
                
                if not href.startswith('/actors'):
                    continue
                
                actor_id_match = re.search(r'/actors/([a-zA-Z0-9_-]+)', href)
                if not actor_id_match:
                    continue
                
                actor_id = actor_id_match.group(1)
                if actor_id in seen_actor_ids:
                    continue
                
                raw_names = []
                if title:
                    raw_names.extend(title.split(','))
                text_name = link_elem.get_text(" ", strip=True)
                if text_name:
                    raw_names.extend(text_name.split(','))
                img_elem = link_elem.select_one('img')
                if img_elem:
                    raw_names.extend(str(img_elem.get('alt') or '').split(','))
                names = []
                for raw_name in raw_names:
                    name = str(raw_name or "").strip()
                    if name and name not in names:
                        names.append(name)
                
                matched_name = None
                for name in names:
                    if name == normalized_actor_name:
                        matched_name = name
                        break
                if not matched_name and names:
                    matched_name = names[0]
                if not matched_name:
                    continue
                
                seen_actor_ids.add(actor_id)
                actors.append({
                    'id': actor_id,
                    'name': matched_name,
                    'actor_name': matched_name,
                    'actor_id': actor_id,
                    'actor_url': urljoin(self.base_url, href),
                    'aliases': names,
                })
            except:
                continue
        
        exact_name = normalized_actor_name.casefold()
        actors.sort(key=lambda item: 0 if str(item.get('actor_name') or '').casefold() == exact_name else 1)
        return actors
    
    # ==================== 演员作品（分页） ====================
    
    def get_actor_works_by_page(self, actor_id: str, page: int = 1) -> Dict:
        """
        获取演员作品的code等基础信息（单页）
        
        Args:
            actor_id: 演员 ID
            page: 页码（从1开始）
            
        Returns:
            {
                'page': 1,
                'has_next': True,
                'works': [
                    {
                        'video_id': 'YwG8Ve',
                        'code': 'MIDA-583',
                        'title': '作品标题',
                        'date': '2026-03-04',
                        'rating': '4.57分',
                        'url': 'https://javdb.com/v/YwG8Ve'
                    },
                    ...
                ]
            }
        """
        if page == 1:
            url = f"/actors/{actor_id}"
        else:
            url = f"/actors/{actor_id}?page={page}"
        
        response = self.get(url)
        soup = BeautifulSoup(response.text, 'lxml')
        
        works = []
        items = soup.select('div.item a')
        
        for item in items:
            try:
                work = self._parse_work_item(item)
                if work:
                    works.append(work)
            except:
                continue
        
        next_btn = soup.select_one('nav.pagination a[rel="next"]')
        has_next = next_btn is not None
        
        return {
            'page': page,
            'has_next': has_next,
            'works': works,
        }
    
    def get_actor_works_full_by_page(self, actor_id: str, page: int = 1, 
                                      download_images: bool = False) -> Dict:
        """
        获取演员作品的全量信息（单页）
        
        Args:
            actor_id: 演员 ID
            page: 页码（从1开始）
            download_images: 是否下载缩略图
            
        Returns:
            {
                'page': 1,
                'has_next': True,
                'works': [
                    {
                        'video_id': 'YwG8Ve',
                        'code': 'MIDA-583',
                        'title': '作品标题',
                        'tags': [...],
                        'actors': [...],
                        'magnets': [...],
                        'thumbnail_images': [...],
                        ...
                    },
                    ...
                ]
            }
        """
        result = self.get_actor_works_by_page(actor_id, page)
        
        full_works = []
        for work in result['works']:
            try:
                detail = self.get_video_detail(work['video_id'], download_images)
                full_work = DataProcessor.merge_video_detail(work, detail)
                full_works.append(full_work)
            except:
                full_works.append(work)
            time.sleep(config.JAVDB['sleep_time'])
        
        result['works'] = full_works
        return result
    
    def get_actor_works(self, actor_id: str, max_pages: int = 10, 
                        get_details: bool = False, download_images: bool = False) -> List[Dict]:
        """
        获取演员的所有作品（多页）
        
        Args:
            actor_id: 演员 ID
            max_pages: 最大爬取页数
            get_details: 是否获取详情
            download_images: 是否下载缩略图
            
        Returns:
            作品列表
        """
        works = []
        page = 1
        has_next = True
        
        while has_next and page <= max_pages:
            if get_details:
                result = self.get_actor_works_full_by_page(actor_id, page, download_images)
            else:
                result = self.get_actor_works_by_page(actor_id, page)
            
            works.extend(result['works'])
            has_next = result['has_next']
            
            if has_next:
                page += 1
                time.sleep(config.JAVDB['sleep_time'])
        
        for i, work in enumerate(works, 1):
            work['rank'] = i
        
        return works
    
    def get_actor_works_with_tags(self, actor_id: str, tag_names: List[str] = None,
                                tag_ids: List[str] = None, max_pages: int = 10,
                                get_details: bool = False, download_images: bool = False,
                                save_temp: bool = True, temp_file: str = None) -> Dict:
        """
        获取演员的所有作品并按标签筛选
        
        原理: 先获取演员的所有作品全量信息，保存到临时文件，然后筛选出带有指定标签的作品
        
        Args:
            actor_id: 演员 ID
            tag_names: 标签名称列表（如 ['水手服', '美少女']）
            tag_ids: 标签ID列表（如 ['c1=23', 'c3=78']），与 tag_names 二选一
            max_pages: 最大爬取页数
            get_details: 是否获取详情
            download_images: 是否下载缩略图
            save_temp: 是否保存临时文件
            temp_file: 临时文件路径，如果为 None 则自动生成
            
        Returns:
            {
                'total_works': 总作品数,
                'filtered_works': 筛选后的作品数,
                'works': 筛选后的作品列表,
                'tags': 使用的标签,
                'temp_file': 临时文件路径
            }
        """
        import json
        from pathlib import Path
        
        # 标准化标签参数
        if tag_ids:
            tags = tag_ids
        elif tag_names:
            tags = tag_names
        else:
            tags = []
        
        # 生成临时文件路径
        if not temp_file:
            temp_file = f"temp_actor_{actor_id}_works.json"
        
        temp_path = Path(temp_file)
        
        # 检查临时文件是否存在
        if temp_path.exists():
            print(f"从临时文件加载: {temp_file}")
            with open(temp_path, 'r', encoding='utf-8') as f:
                all_works = json.load(f)
            all_works = all_works.get('works', [])
        else:
            # 获取所有作品
            # 如果需要标签筛选，必须获取详细信息（因为基础信息中没有标签）
            need_details = get_details or (tags and len(tags) > 0)
            print(f"获取演员 {actor_id} 的所有作品...")
            all_works = self.get_actor_works(actor_id, max_pages, need_details, download_images)
            
            # 保存到临时文件
            if save_temp:
                temp_data = {
                    'actor_id': actor_id,
                    'total_works': len(all_works),
                    'works': all_works,
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
                }
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(temp_data, f, indent=2, ensure_ascii=False)
                print(f"已保存 {len(all_works)} 个作品到临时文件: {temp_file}")
        
        # 筛选作品
        if not tags:
            return {
                'total_works': len(all_works),
                'filtered_works': len(all_works),
                'works': all_works,
                'tags': [],
                'temp_file': str(temp_path) if temp_path.exists() else None
            }
        
        print(f"按标签筛选: {tags}")
        filtered_works = []
        
        for work in all_works:
            work_tags = work.get('tags', [])
            
            # 检查是否包含所有指定的标签
            if isinstance(work_tags, list):
                # 如果 tag_ids 格式是 ['c1=23', 'c3=78']
                if tag_ids:
                    tag_match = True
                    for tag_id in tag_ids:
                        tag_key, tag_value = tag_id.split('=')
                        found = False
                        for tag in work_tags:
                            tag_str = str(tag)
                            if tag_key == 'c1' and tag_value in tag_str:
                                found = True
                                break
                            elif tag_key == 'c2' and tag_value in tag_str:
                                found = True
                                break
                            elif tag_key == 'c3' and tag_value in tag_str:
                                found = True
                                break
                            elif tag_key == 'c4' and tag_value in tag_str:
                                found = True
                                break
                            elif tag_key == 'c5' and tag_value in tag_str:
                                found = True
                                break
                        if not found:
                            tag_match = False
                            break
                    if tag_match:
                        filtered_works.append(work)
                # 如果 tag_names 格式是 ['水手服', '美少女']
                elif tag_names:
                    tag_match = all(tag in str(work_tags) for tag in tag_names)
                    if tag_match:
                        filtered_works.append(work)
        
        print(f"筛选结果: {len(filtered_works)}/{len(all_works)} 个作品")
        
        return {
            'total_works': len(all_works),
            'filtered_works': len(filtered_works),
            'works': filtered_works,
            'tags': tags,
            'temp_file': str(temp_path) if temp_path.exists() else None
        }
    
    def _parse_work_item(self, item) -> Optional[Dict]:
        """解析作品项"""
        try:
            href = item.get('href', '')
            
            match = re.search(r'/v/([a-zA-Z0-9]+)', href)
            if not match:
                return None
            
            video_id = match.group(1)
            
            code = ""
            title = ""
            video_title_elem = item.select_one('.video-title')
            if video_title_elem:
                video_title_text = video_title_elem.get_text(strip=True)
                code_match = re.search(r'(FC2(?:-?PPV)?-?\d+|[A-Z]{2,6}-?\d{2,5})', video_title_text, re.I)
                if code_match:
                    code = code_match.group(1).upper()
                title = video_title_text
            
            date = ""
            meta_elem = item.select_one('.meta')
            if meta_elem:
                meta_text = meta_elem.get_text(strip=True)
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', meta_text)
                if date_match:
                    date = date_match.group(1)
            
            rating = ""
            rating_elem = item.select_one('.score, .rating')
            if rating_elem:
                rating = rating_elem.get_text(strip=True)
            
            cover_url = ""
            cover_elem = item.select_one('img.cover, img')
            if cover_elem:
                cover_url = cover_elem.get('src', '')
                cover_url = cover_elem.get('data-src', cover_url)
            
            result = {
                'video_id': video_id,
                'code': code,
                'title': title,
                'date': date,
                'rating': rating,
                'url': urljoin(self.base_url, href),
                'cover_url': cover_url
            }
            
            return result
        except:
            return None
    
    # ==================== Tag 作品（分页） ====================
    
    def get_tag_works_by_page(self, tag_id: str, page: int = 1) -> Dict:
        """
        获取Tag搜索结果的code等基础信息（单页）
        
        Args:
            tag_id: Tag ID
            page: 页码（从1开始）
            
        Returns:
            {
                'page': 1,
                'has_next': True,
                'works': [
                    {
                        'video_id': 'YwG8Ve',
                        'code': 'MIDA-583',
                        'title': '作品标题',
                        'date': '2026-03-04',
                        'rating': '4.57分',
                        'url': 'https://javdb.com/v/YwG8Ve'
                    },
                    ...
                ]
            }
        """
        if page == 1:
            url = f"/tags?c1={tag_id}"
        else:
            url = f"/tags?c1={tag_id}&page={page}"
        
        response = self.get(url)
        soup = BeautifulSoup(response.text, 'lxml')
        
        works = []
        items = soup.select('div.item a')
        
        for item in items:
            try:
                work = self._parse_work_item(item)
                if work:
                    works.append(work)
            except:
                continue
        
        next_btn = soup.select_one('nav.pagination a[rel="next"]')
        has_next = next_btn is not None
        
        return {
            'page': page,
            'has_next': has_next,
            'works': works,
        }
    
    def get_tag_works_full_by_page(self, tag_id: str, page: int = 1,
                                    download_images: bool = False) -> Dict:
        """
        获取Tag搜索结果的全量信息（单页）
        
        Args:
            tag_id: Tag ID
            page: 页码（从1开始）
            download_images: 是否下载缩略图
            
        Returns:
            {
                'page': 1,
                'has_next': True,
                'works': [
                    {
                        'video_id': 'YwG8Ve',
                        'code': 'MIDA-583',
                        'title': '作品标题',
                        'tags': [...],
                        'actors': [...],
                        'magnets': [...],
                        'thumbnail_images': [...],
                        ...
                    },
                    ...
                ]
            }
        """
        result = self.get_tag_works_by_page(tag_id, page)
        
        full_works = []
        for work in result['works']:
            try:
                detail = self.get_video_detail(work['video_id'], download_images)
                full_work = DataProcessor.merge_video_detail(work, detail)
                full_works.append(full_work)
            except:
                full_works.append(work)
            time.sleep(config.JAVDB['sleep_time'])
        
        result['works'] = full_works
        return result
    
    def get_tag_works(self, tag_id: str, max_pages: int = 10, 
                      get_details: bool = False, download_images: bool = False) -> List[Dict]:
        """
        获取某个 Tag 下的所有作品（多页）
        
        Args:
            tag_id: Tag ID
            max_pages: 最大爬取页数
            get_details: 是否获取详情
            download_images: 是否下载缩略图
            
        Returns:
            作品列表
        """
        works = []
        page = 1
        has_next = True
        
        while has_next and page <= max_pages:
            if get_details:
                result = self.get_tag_works_full_by_page(tag_id, page, download_images)
            else:
                result = self.get_tag_works_by_page(tag_id, page)
            
            works.extend(result['works'])
            has_next = result['has_next']
            
            if has_next:
                page += 1
                time.sleep(config.JAVDB['sleep_time'])
        
        for i, work in enumerate(works, 1):
            work['rank'] = i
        
        return works
    
    # ==================== 多类标签组合搜索 ====================
    
    def search_by_tags(self, page: int = 1, **tag_params) -> Dict:
        """
        多类标签组合搜索（基础信息）
        
        支持多类标签组合，如 c1=23&c3=78
        支持通过标签名称搜索，自动转换为标签ID
        
        Args:
            page: 页码
            **tag_params: 标签参数，支持两种格式：
                1. 直接指定ID: c1=23, c3=78
                2. 通过名称查找: tag_主題="美少女", tag_服裝="水手服"
                3. 简写格式: 主題="美少女", 服裝="水手服"（自动识别为标签名称）
            
        Returns:
            {
                'page': 1,
                'has_next': True,
                'tag_params': {'c1': 23, 'c3': 78},
                'works': [
                    {
                        'video_id': 'YwG8Ve',
                        'code': 'MIDA-583',
                        'title': '作品标题',
                        'date': '2026-03-04',
                        'rating': '4.57分',
                        'url': 'https://javdb.com/v/YwG8Ve'
                    },
                    ...
                ]
            }
            
        示例:
            # 方式1: 最简单 - 直接输入标签名称
            result = api.search_by_tags(page=1, **{"淫亂真實": ""})
            result = api.search_by_tags(page=1, **{"美少女": "", "水手服": ""})
            
            # 方式2: 使用 tags 参数传递列表
            result = api.search_by_tags(page=1, tags=["淫亂真實", "水手服"])
            
            # 方式3: 带分类前缀（更精确）
            result = api.search_by_tags(page=1, tag_主題="淫亂真實")
            
            # 方式4: 传统ID模式（仍然支持）
            result = api.search_by_tags(page=1, c1=23, c3=78)
        """
        # 解析标签参数（支持名称和ID多种格式）
        resolved_params = self._resolve_tag_params(**tag_params)
        
        # 构建 URL 参数
        params = []
        for key, value in resolved_params.items():
            if key.startswith('c') and value is not None:
                params.append(f"{key}={value}")
        
        if not params:
            raise ValueError("至少需要提供一个标签参数（如 c1=23 或 tag_主題='美少女'）")
        
        query_string = "&".join(params)
        
        if page == 1:
            url = f"/tags?{query_string}"
        else:
            url = f"/tags?{query_string}&page={page}"
        
        response = self.get(url)
        soup = BeautifulSoup(response.text, 'lxml')
        
        works = []
        items = soup.select('div.item a')
        
        for item in items:
            try:
                work = self._parse_work_item(item)
                if work:
                    works.append(work)
            except:
                continue
        
        next_btn = soup.select_one('nav.pagination a[rel="next"]')
        has_next = next_btn is not None
        
        return {
            'page': page,
            'has_next': has_next,
            'tag_params': resolved_params,
            'works': works,
        }
    
    def search_by_tags_full(self, page: int = 1, download_images: bool = False, 
                            **tag_params) -> Dict:
        """
        多类标签组合搜索（全量信息）
        
        支持多类标签组合，获取作品全量信息
        支持通过标签名称搜索，自动转换为标签ID
        
        Args:
            page: 页码
            download_images: 是否下载缩略图
            **tag_params: 标签参数，支持两种格式：
                1. 直接指定ID: c1=23, c3=78
                2. 通过名称查找: tag_主題="美少女", tag_服裝="水手服"
            
        Returns:
            {
                'page': 1,
                'has_next': True,
                'tag_params': {'c1': 23, 'c3': 78},
                'works': [
                    {
                        'video_id': 'YwG8Ve',
                        'code': 'MIDA-583',
                        'title': '作品标题',
                        'tags': [...],
                        'actors': [...],
                        'magnets': [...],
                        ...
                    },
                    ...
                ]
            }
            
        示例:
            # 方式1: 直接指定标签ID
            result = api.search_by_tags_full(page=1, c1=23, c3=78)
            
            # 方式2: 通过标签名称搜索（推荐）
            result = api.search_by_tags_full(page=1, tag_主題="淫亂真實")
            result = api.search_by_tags_full(page=1, tag_主題="美少女", tag_服裝="水手服")
        """
        result = self.search_by_tags(page, **tag_params)
        
        full_works = []
        for work in result['works']:
            try:
                detail = self.get_video_detail(work['video_id'], download_images)
                full_work = DataProcessor.merge_video_detail(work, detail)
                full_works.append(full_work)
            except:
                full_works.append(work)
            time.sleep(config.JAVDB['sleep_time'])
        
        result['works'] = full_works
        return result
    
    # ==================== 搜索功能 ====================
    
    def search_videos(self, keyword: str, page: int = 1) -> Dict:
        """
        搜索视频
        
        Args:
            keyword: 搜索关键词
            page: 页码
            
        Returns:
            {
                'page': 当前页码,
                'has_next': 是否有下一页,
                'total_pages': 总页数（如果知道）,
                'videos': 视频列表
            }
        """
        encoded_keyword = quote(keyword)
        url = f"/search?q={encoded_keyword}&page={page}"
        
        response = self.get(url)
        soup = BeautifulSoup(response.text, 'lxml')
        
        videos = []
        items = soup.select('div.item a')
        
        for item in items:
            try:
                work = self._parse_work_item(item)
                if work:
                    videos.append(work)
            except:
                continue
        
        # 检查是否有下一页
        next_btn = soup.select_one('nav.pagination a[rel="next"]')
        has_next = next_btn is not None
        
        return {
            'page': page,
            'has_next': has_next,
            'total_pages': None,
            'videos': videos
        }
    
    # ==================== 批量保存功能 ====================
    
    def save_actor_works(self, actor_name: str, max_pages: int = 10, 
                         download_images: bool = True) -> Dict:
        """
        抓取并保存演员所有作品（完整流程）
        
        Args:
            actor_name: 演员名字
            max_pages: 最大页数
            download_images: 是否下载缩略图
            
        Returns:
            完整数据字典
        """
        actors = self.search_actor(actor_name)
        if not actors:
            raise Exception(f"未找到演员: {actor_name}")
        
        actor = actors[0]
        
        works = self.get_actor_works(
            actor['actor_id'],
            max_pages=max_pages,
            get_details=True,
            download_images=download_images
        )
        
        export_data = self.json_exporter.save_actor_works(
            actor_name=actor['name'],
            actor_id=actor['actor_id'],
            works=works,
            actor_url=actor['url']
        )
        
        self.magnet_exporter.save_magnets(works, f"{actor_name}_magnets.txt")
        
        return export_data
    
    # ==================== 用户清单功能 ====================
    
    def get_want_watch_videos(self, page: int = 1) -> Dict:
        """
        获取用户的想看清单
        
        Args:
            page: 页码（从1开始）
            
        Returns:
            {
                'page': 1,
                'has_next': True,
                'works': [
                    {
                        'video_id': 'YwG8Ve',
                        'code': 'MIDA-583',
                        'title': '作品标题',
                        'date': '2026-03-04',
                        'rating': '4.57分',
                        'url': 'https://javdb.com/v/YwG8Ve'
                    },
                    ...
                ]
            }
        """
        url = f"/users/want_watch_videos"
        if page > 1:
            url = f"/users/want_watch_videos?page={page}"
        
        response = self.get(url)
        soup = BeautifulSoup(response.text, 'lxml')
        
        works = []
        items = soup.select('div.item a')
        
        for item in items:
            try:
                work = self._parse_work_item(item)
                if work:
                    works.append(work)
            except:
                continue
        
        next_btn = soup.select_one('nav.pagination a[rel="next"]')
        has_next = next_btn is not None
        
        return {
            'page': page,
            'has_next': has_next,
            'works': works,
        }
    
    def get_watched_videos(self, page: int = 1) -> Dict:
        """
        获取用户的看过清单
        
        Args:
            page: 页码（从1开始）
            
        Returns:
            {
                'page': 1,
                'has_next': True,
                'works': [
                    {
                        'video_id': 'YwG8Ve',
                        'code': 'MIDA-583',
                        'title': '作品标题',
                        'date': '2026-03-04',
                        'rating': '4.57分',
                        'url': 'https://javdb.com/v/YwG8Ve'
                    },
                    ...
                ]
            }
        """
        url = f"/users/watched_videos"
        if page > 1:
            url = f"/users/watched_videos?page={page}"
        
        response = self.get(url)
        soup = BeautifulSoup(response.text, 'lxml')
        
        works = []
        items = soup.select('div.item a')
        
        for item in items:
            try:
                work = self._parse_work_item(item)
                if work:
                    works.append(work)
            except:
                continue
        
        next_btn = soup.select_one('nav.pagination a[rel="next"]')
        has_next = next_btn is not None
        
        return {
            'page': page,
            'has_next': has_next,
            'works': works,
        }
    
    def get_user_lists(self, page: int = 1) -> Dict:
        """
        获取用户的清单列表（分页）
        
        Args:
            page: 页码（从1开始）
        
        Returns:
            {
                'page': 1,
                'has_next': True,
                'lists': [
                    {
                        'list_id': '0W97k',
                        'list_name': '我的收藏',
                        'list_url': 'https://javdb.com/users/list_detail?id=0W97k',
                        'video_count': 50
                    },
                    ...
                ]
            }
        """
        url = f"/users/lists"
        if page > 1:
            url = f"/users/lists?page={page}"
        
        response = self.get(url)
        soup = BeautifulSoup(response.text, 'lxml')
        
        lists = []
        list_items = soup.select('li.list-item')
        
        for item in list_items:
            try:
                link = item.select_one('a[href*="list_detail"]')
                if not link:
                    continue
                
                href = link.get('href', '')
                list_id = href.split('id=')[-1] if 'id=' in href else ''
                
                name_elem = item.select_one('.list-name')
                list_name = name_elem.get_text(strip=True) if name_elem else ''
                
                meta_elem = item.select_one('.meta')
                video_count = 0
                if meta_elem:
                    meta_text = meta_elem.get_text(strip=True)
                    count_match = re.search(r'(\d+)\s*部影片', meta_text)
                    if count_match:
                        video_count = int(count_match.group(1))
                
                lists.append({
                    'list_id': list_id,
                    'list_name': list_name,
                    'list_url': f"{self.base_url}{href}",
                    'video_count': video_count
                })
            except:
                continue
        
        next_btn = soup.select_one('nav.pagination a[rel="next"]')
        has_next = next_btn is not None
        
        return {
            'page': page,
            'has_next': has_next,
            'lists': lists,
        }
    
    def get_user_lists_all(self, max_pages: int = 100) -> List[Dict]:
        """
        获取用户的所有清单（自动翻页）
        
        Args:
            max_pages: 最大页数限制
            
        Returns:
            [
                {
                    'list_id': '0W97k',
                    'list_name': '我的收藏',
                    'list_url': 'https://javdb.com/users/list_detail?id=0W97k',
                    'video_count': 50
                },
                ...
            ]
        """
        all_lists = []
        page = 1
        
        while page <= max_pages:
            result = self.get_user_lists(page=page)
            all_lists.extend(result['lists'])
            
            if not result['has_next']:
                break
            
            page += 1
        
        return all_lists
    
    def get_list_detail(self, list_id: str, page: int = 1) -> Dict:
        """
        获取清单的详细内容
        
        Args:
            list_id: 清单ID（如 "0W97k"）
            page: 页码（从1开始）
            
        Returns:
            {
                'page': 1,
                'has_next': True,
                'list_id': '0W97k',
                'list_name': '我的收藏',
                'works': [
                    {
                        'video_id': 'YwG8Ve',
                        'code': 'MIDA-583',
                        'title': '作品标题',
                        'date': '2026-03-04',
                        'rating': '4.57分',
                        'url': 'https://javdb.com/v/YwG8Ve'
                    },
                    ...
                ]
            }
        """
        url = f"/users/list_detail?id={list_id}"
        if page > 1:
            url = f"/users/list_detail?id={list_id}&page={page}"
        
        response = self.get(url)
        soup = BeautifulSoup(response.text, 'lxml')
        
        list_name = ''
        breadcrumb_active = soup.select_one('nav.breadcrumb li.is-active a')
        if breadcrumb_active:
            list_name = breadcrumb_active.get_text(strip=True)
        
        works = []
        items = soup.select('div.item a')
        
        for item in items:
            try:
                work = self._parse_work_item(item)
                if work:
                    works.append(work)
            except:
                continue
        
        next_btn = soup.select_one('nav.pagination a[rel="next"]')
        has_next = next_btn is not None
        
        return {
            'page': page,
            'has_next': has_next,
            'list_id': list_id,
            'list_name': list_name,
            'works': works,
        }
    
    def get_want_watch_videos_all(self, max_pages: int = 100) -> List[Dict]:
        """
        获取用户想看清单的所有作品
        
        Args:
            max_pages: 最大页数限制
            
        Returns:
            作品列表
        """
        works = []
        page = 1
        has_next = True
        
        while has_next and page <= max_pages:
            result = self.get_want_watch_videos(page)
            works.extend(result['works'])
            has_next = result['has_next']
            
            if has_next:
                page += 1
                time.sleep(config.JAVDB['sleep_time'])
        
        return works
    
    def get_watched_videos_all(self, max_pages: int = 100) -> List[Dict]:
        """
        获取用户看过清单的所有作品
        
        Args:
            max_pages: 最大页数限制
            
        Returns:
            作品列表
        """
        works = []
        page = 1
        has_next = True
        
        while has_next and page <= max_pages:
            result = self.get_watched_videos(page)
            works.extend(result['works'])
            has_next = result['has_next']
            
            if has_next:
                page += 1
                time.sleep(config.JAVDB['sleep_time'])
        
        return works
    
    def get_list_detail_all(self, list_id: str, max_pages: int = 100) -> Dict:
        """
        获取清单的所有作品
        
        Args:
            list_id: 清单ID
            max_pages: 最大页数限制
            
        Returns:
            {
                'list_id': '0W97k',
                'list_name': '我的收藏',
                'works': [...]
            }
        """
        works = []
        page = 1
        has_next = True
        list_name = ''
        
        while has_next and page <= max_pages:
            result = self.get_list_detail(list_id, page)
            if page == 1:
                list_name = result.get('list_name', '')
            works.extend(result['works'])
            has_next = result['has_next']
            
            if has_next:
                page += 1
                time.sleep(config.JAVDB['sleep_time'])
        
        return {
            'list_id': list_id,
            'list_name': list_name,
            'works': works,
        }


# ==================== 便捷函数 ====================

def get_video_detail(video_id: str, download_images: bool = False) -> Dict:
    """
    抓取作品页全量信息
    
    Args:
        video_id: 视频 ID
        download_images: 是否下载缩略图
        
    Returns:
        视频详情字典
    """
    api = JavdbAPI()
    return api.get_video_detail(video_id, download_images)


def get_video_by_code(code: str, download_images: bool = False) -> Optional[Dict]:
    """
    根据番号搜索并获取作品全量信息
    
    Args:
        code: 番号 (如 MIDA-583)
        download_images: 是否下载缩略图
        
    Returns:
        视频详情字典，未找到返回 None
    """
    api = JavdbAPI()
    return api.get_video_by_code(code, download_images)


def search_actor(actor_name: str) -> List[Dict]:
    """
    搜索演员
    
    Args:
        actor_name: 演员名字
        
    Returns:
        演员列表
    """
    api = JavdbAPI()
    return api.search_actor(actor_name)


def get_actor_works_by_page(actor_id: str, page: int = 1) -> Dict:
    """
    获取演员作品的code等基础信息（单页）
    
    Args:
        actor_id: 演员 ID
        page: 页码
        
    Returns:
        包含 page, has_next, works 的字典
    """
    api = JavdbAPI()
    return api.get_actor_works_by_page(actor_id, page)


def get_actor_works_full_by_page(actor_id: str, page: int = 1, 
                                  download_images: bool = False) -> Dict:
    """
    获取演员作品的全量信息（单页）
    
    Args:
        actor_id: 演员 ID
        page: 页码
        download_images: 是否下载缩略图
        
    Returns:
        包含 page, has_next, works 的字典
    """
    api = JavdbAPI()
    return api.get_actor_works_full_by_page(actor_id, page, download_images)


def get_actor_works(actor_name: str, max_pages: int = 10, 
                    get_details: bool = False, download_images: bool = False) -> List[Dict]:
    """
    获取演员作品（多页）
    
    Args:
        actor_name: 演员名字
        max_pages: 最大页数
        get_details: 是否获取详情
        download_images: 是否下载缩略图
        
    Returns:
        作品列表
    """
    api = JavdbAPI()
    
    actors = api.search_actor(actor_name)
    if not actors:
        return []
    
    return api.get_actor_works(
        actors[0]['actor_id'],
        max_pages,
        get_details,
        download_images
    )


def get_tag_works_by_page(tag_id: str, page: int = 1) -> Dict:
    """
    获取Tag搜索结果的code等基础信息（单页）
    
    Args:
        tag_id: Tag ID
        page: 页码
        
    Returns:
        包含 page, has_next, works 的字典
    """
    api = JavdbAPI()
    return api.get_tag_works_by_page(tag_id, page)


def get_tag_works_full_by_page(tag_id: str, page: int = 1,
                                download_images: bool = False) -> Dict:
    """
    获取Tag搜索结果的全量信息（单页）
    
    Args:
        tag_id: Tag ID
        page: 页码
        download_images: 是否下载缩略图
        
    Returns:
        包含 page, has_next, works 的字典
    """
    api = JavdbAPI()
    return api.get_tag_works_full_by_page(tag_id, page, download_images)


def get_tag_works(tag_id: str, max_pages: int = 10, 
                  get_details: bool = False, download_images: bool = False) -> List[Dict]:
    """
    获取 Tag 下的作品（多页）
    
    Args:
        tag_id: Tag ID
        max_pages: 最大页数
        get_details: 是否获取详情
        download_images: 是否下载缩略图
        
    Returns:
        作品列表
    """
    api = JavdbAPI()
    return api.get_tag_works(tag_id, max_pages, get_details, download_images)


def scrape_actor_full(actor_name: str, max_pages: int = 10, 
                      download_images: bool = True) -> Dict:
    """
    全量抓取演员所有信息并保存
    
    Args:
        actor_name: 演员名字
        max_pages: 最大页数
        download_images: 是否下载缩略图
        
    Returns:
        完整数据字典
    """
    api = JavdbAPI()
    return api.save_actor_works(actor_name, max_pages, download_images)


def search_by_tags(page: int = 1, **tag_params) -> Dict:
    """
    多类标签组合搜索（基础信息）
    
    支持多类标签组合，如 c1=23&c3=78
    支持通过标签名称搜索，自动转换为标签ID
    
    Args:
        page: 页码
        **tag_params: 标签参数，支持两种格式：
            1. 直接指定ID: c1=23, c3=78
            2. 通过名称查找: tag_主題="美少女", tag_服裝="水手服"
        
    Returns:
        {
            'page': 1,
            'has_next': True,
            'tag_params': {'c1': 23, 'c3': 78},
            'works': [...]
        }
        
    示例:
        # 方式1: 直接指定标签ID
        result = search_by_tags(page=1, c1=23, c3=78)
        
        # 方式2: 通过标签名称搜索（推荐）
        result = search_by_tags(page=1, tag_主題="淫亂真實")
        result = search_by_tags(page=1, tag_主題="美少女", tag_服裝="水手服")
    """
    api = JavdbAPI()
    return api.search_by_tags(page, **tag_params)


def search_by_tags_full(page: int = 1, download_images: bool = False,
                        **tag_params) -> Dict:
    """
    多类标签组合搜索（全量信息）

    支持多类标签组合，获取作品全量信息
    支持通过标签名称搜索，自动转换为标签ID

    Args:
        page: 页码
        download_images: 是否下载缩略图
        **tag_params: 标签参数，支持两种格式：
            1. 直接指定ID: c1=23, c3=78
            2. 通过名称查找: tag_主題="美少女", tag_服裝="水手服"

    Returns:
        {
            'page': 1,
            'has_next': True,
            'tag_params': {'c1': 23, 'c3': 78},
            'works': [...]
        }

    示例:
        # 方式1: 直接指定标签ID
        result = search_by_tags_full(page=1, c1=23, c3=78)

        # 方式2: 通过标签名称搜索（推荐）
        result = search_by_tags_full(page=1, tag_主題="淫亂真實")
        result = search_by_tags_full(page=1, tag_主題="美少女", tag_服裝="水手服")
    """
    api = JavdbAPI()
    return api.search_by_tags_full(page, download_images, **tag_params)


# ==================== 用户清单功能 ====================

def get_want_watch_videos(page: int = 1) -> Dict:
    """
    获取用户的想看清单
    
    Args:
        page: 页码（从1开始）
        
    Returns:
        {
            'page': 1,
            'has_next': True,
            'works': [...]
        }
    """
    api = JavdbAPI()
    return api.get_want_watch_videos(page)


def get_watched_videos(page: int = 1) -> Dict:
    """
    获取用户的看过清单
    
    Args:
        page: 页码（从1开始）
        
    Returns:
        {
            'page': 1,
            'has_next': True,
            'works': [...]
        }
    """
    api = JavdbAPI()
    return api.get_watched_videos(page)


def get_user_lists(page: int = 1) -> Dict:
    """
    获取用户的清单列表（分页）
    
    Args:
        page: 页码（从1开始）
    
    Returns:
        {
            'page': 1,
            'has_next': True,
            'lists': [
                {
                    'list_id': '0W97k',
                    'list_name': '我的收藏',
                    'list_url': 'https://javdb.com/users/list_detail?id=0W97k',
                    'video_count': 50
                },
                ...
            ]
        }
    """
    api = JavdbAPI()
    return api.get_user_lists(page)


def get_user_lists_all(max_pages: int = 100) -> List[Dict]:
    """
    获取用户的所有清单（自动翻页）
    
    Args:
        max_pages: 最大页数限制
        
    Returns:
        [
            {
                'list_id': '0W97k',
                'list_name': '我的收藏',
                'list_url': 'https://javdb.com/users/list_detail?id=0W97k',
                'video_count': 50
            },
            ...
        ]
    """
    api = JavdbAPI()
    return api.get_user_lists_all(max_pages)


def get_list_detail(list_id: str, page: int = 1) -> Dict:
    """
    获取清单的详细内容
    
    Args:
        list_id: 清单ID（如 "0W97k"）
        page: 页码（从1开始）
        
    Returns:
        {
            'page': 1,
            'has_next': True,
            'list_id': '0W97k',
            'list_name': '我的收藏',
            'works': [...]
        }
    """
    api = JavdbAPI()
    return api.get_list_detail(list_id, page)


def get_want_watch_videos_all(max_pages: int = 100) -> List[Dict]:
    """
    获取用户想看清单的所有作品
    
    Args:
        max_pages: 最大页数限制
        
    Returns:
        作品列表
    """
    api = JavdbAPI()
    return api.get_want_watch_videos_all(max_pages)


def get_watched_videos_all(max_pages: int = 100) -> List[Dict]:
    """
    获取用户看过清单的所有作品
    
    Args:
        max_pages: 最大页数限制
        
    Returns:
        作品列表
    """
    api = JavdbAPI()
    return api.get_watched_videos_all(max_pages)


def get_list_detail_all(list_id: str, max_pages: int = 100) -> Dict:
    """
    获取清单的所有作品
    
    Args:
        list_id: 清单ID
        max_pages: 最大页数限制
        
    Returns:
        {
            'list_id': '0W97k',
            'list_name': '我的收藏',
            'works': [...]
        }
    """
    api = JavdbAPI()
    return api.get_list_detail_all(list_id, max_pages)


# ==================== 标签管理模块导出 ====================
from lib.tag_manager import (
    TagManager,
    get_tag_manager,
    get_tag_by_name,
    get_tag_by_id,
    search_tags_by_keyword,
    convert_to_traditional,
)


# ==================== 图片下载模块 ====================

def download_video_images(video_id: str, image_urls: List[Dict[str, str]], 
                         output_dir: str = "output/images",
                         headers: Dict[str, str] = None) -> Dict[str, Any]:
    """
    下载视频相关图片（通用方法）
    
    支持下载封面、样品图、缩略图等，支持自定义请求头（如 Referer）
    
    Args:
        video_id: 视频 ID 或番号（用于创建子目录）
        image_urls: 图片信息列表，每项包含:
            - 'url': 图片 URL（必需）
            - 'filename': 自定义文件名（可选，默认自动生成）
            例如: [
                {'url': 'https://.../cover.jpg', 'filename': 'cover.jpg'},
                {'url': 'https://.../sample1.jpg', 'filename': 'sample_01.jpg'},
            ]
        output_dir: 输出目录，默认为 "output/images"
        headers: 可选的自定义请求头，例如:
            {'Referer': 'https://javdb.com/v/xxxxx'}
            
    Returns:
        下载结果统计
        {
            'downloaded': 成功下载数量,
            'total': 总数量,
            'success_rate': 成功率（百分比）,
            'download_dir': 下载目录路径,
            'files': [下载的文件路径列表]
        }
    """
    api = JavdbAPI()
    return api.image_downloader.download_images(
        video_id, image_urls, output_dir, headers
    )


def download_video_detail_images(video_id: str, output_dir: str = "output/images") -> Dict[str, Any]:
    """
    获取视频详情并下载所有缩略图
    
    先获取视频详情，然后自动下载所有缩略图
    
    Args:
        video_id: 视频 ID
        output_dir: 输出目录
        
    Returns:
        {
            'detail': 视频详情,
            'download_result': 下载结果统计
        }
    """
    api = JavdbAPI()
    detail = api.get_video_detail(video_id)
    
    download_result = None
    if detail.get('thumbnail_images'):
        image_urls = [
            {'url': url, 'filename': f"{i:03d}.jpg"}
            for i, url in enumerate(detail['thumbnail_images'])
        ]
        download_result = api.image_downloader.download_images(
            detail.get('code', video_id),
            image_urls,
            output_dir
        )
    
    return {
        'detail': detail,
        'download_result': download_result
    }
