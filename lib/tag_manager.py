"""
标签管理模块
支持标签名称和ID的互查，包括繁体转换
使用加密数据库存储标签信息
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

from .crypto_utils import CryptoUtils, DEFAULT_KEY


class TagManager:
    """标签管理器"""
    
    def __init__(self, database_path: Optional[str] = None, key: Optional[str] = None):
        """
        初始化标签管理器
        
        Args:
            database_path: 加密数据库文件路径，默认为 output/tags_database.enc
            key: 解密密钥，默认使用 DEFAULT_KEY
        """
        if database_path is None:
            database_path = Path(__file__).parent / "tags_database.enc"
        else:
            database_path = Path(database_path)
        
        if key is None:
            key = DEFAULT_KEY
        
        self.database_path = database_path
        self.key = key
        self._tag_cache: Dict[str, Dict] = {}  # 缓存标签信息，key为 "c1=23"
        self._name_to_id_cache: Dict[str, str] = {}  # 名称到ID的缓存
        self._id_to_name_cache: Dict[str, str] = {}  # ID到名称的缓存
        self._category_cache: Dict[str, str] = {}  # 分类名称缓存，key为 "c1"，value为 "主題"
        
        # 加载数据库
        self._load_database()
    
    def _load_database(self):
        """加载加密数据库"""
        if not self.database_path.exists():
            print(f"警告: 标签数据库文件不存在: {self.database_path}")
            return
        
        try:
            decrypted_content = CryptoUtils.decrypt_file(str(self.database_path), self.key)
            data = json.loads(decrypted_content)
            
            # 数据库结构: {"categories": {"c1": {"name": "主題", "tags": [...]}, ...}, "updated_at": "...", "source": "..."}
            tag_data = data.get('categories', {})
            
            # 构建缓存
            for category_key, category_info in tag_data.items():
                # 跳过非分类字段
                if not isinstance(category_info, dict):
                    continue
                    
                # 缓存分类名称
                category_name = category_info.get('name', '')
                self._category_cache[category_key] = category_name
                
                # 缓存标签
                tags = category_info.get('tags', [])
                for tag in tags:
                    tag_id = tag.get('id')
                    tag_name = tag.get('name')
                    tag_value = tag.get('value', str(tag_id))
                    
                    if tag_id and tag_name:
                        # 构建完整的标签ID，如 "c1=23"
                        full_tag_id = f"{category_key}={tag_id}"
                        
                        tag_info = {
                            'id': full_tag_id,
                            'name': tag_name,
                            'category': category_key,
                            'category_name': category_name,
                            'value': tag_value,
                            'tag_id': tag_id,
                        }
                        
                        self._tag_cache[full_tag_id] = tag_info
                        self._name_to_id_cache[tag_name] = full_tag_id
                        self._id_to_name_cache[full_tag_id] = tag_name
            
            print(f"成功加载 {len(self._tag_cache)} 个标签")
        except Exception as e:
            print(f"加载标签数据库失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _to_traditional(self, text: str) -> str:
        """
        简体转换为繁体
        
        Args:
            text: 简体文本
            
        Returns:
            繁体文本
        """
        # 简繁转换对照表（常用字）
        simplified_to_traditional = {
            '乱': '亂', '义': '義', '乌': '烏', '乐': '樂', '乔': '喬',
            '习': '習', '乡': '鄉', '书': '書', '买': '買', '乱': '亂',
            '了': '瞭', '亏': '虧', '云': '雲', '亚': '亞', '产': '產',
            '亩': '畝', '亲': '親', '亵': '褻', '亿': '億', '仅': '僅',
            '从': '從', '仑': '侖', '仓': '倉', '仪': '儀', '们': '們',
            '价': '價', '众': '眾', '优': '優', '伙': '夥', '会': '會',
            '伞': '傘', '伟': '偉', '传': '傳', '伤': '傷', '伦': '倫',
            '伪': '偽', '体': '體', '余': '餘', '佣': '傭', '侠': '俠',
            '侣': '侶', '侥': '僥', '侦': '偵', '侧': '側', '侨': '僑',
            '侩': '儈', '宾': '賓', '审': '審', '宪': '憲', '家': '傢',
            '实': '實', '验': '驗', '关': '關', '业': '業', '历': '歷',
            '历': '歷', '东': '東', '丝': '絲', '两': '兩', '严': '嚴',
            '丧': '喪', '个': '個', '临': '臨', '为': '為', '丽': '麗',
            '举': '舉', '么': '麼', '义': '義', '乌': '烏', '乐': '樂',
            '乔': '喬', '习': '習', '乡': '鄉', '书': '書', '买': '買',
            '乱': '亂', '了': '瞭', '亏': '虧', '云': '雲', '亚': '亞',
            '产': '產', '亩': '畝', '亲': '親', '亵': '褻', '亿': '億',
            '仅': '僅', '从': '從', '仑': '侖', '仓': '倉', '仪': '儀',
            '们': '們', '价': '價', '众': '眾', '优': '優', '伙': '夥',
            '会': '會', '伞': '傘', '伟': '偉', '传': '傳', '伤': '傷',
            '伦': '倫', '伪': '偽', '体': '體', '余': '餘', '佣': '傭',
            '侠': '俠', '侣': '侶', '侥': '僥', '侦': '偵', '侧': '側',
            '侨': '僑', '侩': '儈', '宾': '賓', '审': '審', '宪': '憲',
            '家': '傢', '实': '實', '验': '驗', '关': '關', '业': '業',
            '历': '歷', '东': '東', '丝': '絲', '两': '兩', '严': '嚴',
            '丧': '喪', '个': '個', '临': '臨', '为': '為', '丽': '麗',
            '举': '舉', '么': '麼', '义': '義', '乌': '烏', '乐': '樂',
        }
        
        result = ""
        for char in text:
            result += simplified_to_traditional.get(char, char)
        return result
    
    def get_tag_by_name(self, tag_name: str, use_traditional: bool = True) -> Optional[Dict]:
        """
        通过标签名称获取标签信息
        
        Args:
            tag_name: 标签名称（简体或繁体）
            use_traditional: 如果简体搜索不到，是否尝试繁体转换后搜索
            
        Returns:
            标签信息字典，找不到返回None
        """
        # 先尝试直接搜索
        tag_id = self._name_to_id_cache.get(tag_name)
        if tag_id:
            return self._tag_cache[tag_id]
        
        # 如果开启了繁体转换且没找到，尝试繁体
        if use_traditional:
            traditional_name = self._to_traditional(tag_name)
            if traditional_name != tag_name:
                tag_id = self._name_to_id_cache.get(traditional_name)
                if tag_id:
                    return self._tag_cache[tag_id]
        
        return None
    
    def get_tag_by_id(self, tag_id: str) -> Optional[Dict]:
        """
        通过标签ID获取标签信息
        
        Args:
            tag_id: 标签ID，格式如 "c1=23"
            
        Returns:
            标签信息字典，找不到返回None
        """
        return self._tag_cache.get(tag_id)
    
    def search_tags_by_keyword(self, keyword: str, use_traditional: bool = True) -> List[Dict]:
        """
        通过关键词模糊搜索标签
        
        Args:
            keyword: 搜索关键词
            use_traditional: 如果简体搜索不到，是否尝试繁体转换后搜索
            
        Returns:
            匹配的标签列表
        """
        results = []
        
        # 搜索包含关键词的标签
        for tag_id, tag_info in self._tag_cache.items():
            if keyword in tag_info['name']:
                results.append(tag_info)
        
        # 如果开启了繁体转换且没找到结果，尝试繁体
        if use_traditional and not results:
            traditional_keyword = self._to_traditional(keyword)
            if traditional_keyword != keyword:
                for tag_id, tag_info in self._tag_cache.items():
                    if traditional_keyword in tag_info['name']:
                        results.append(tag_info)
        
        return results
    
    def get_all_tags(self) -> Dict[str, Dict]:
        """
        获取所有标签
        
        Returns:
            所有标签的字典
        """
        return self._tag_cache.copy()
    
    def get_tags_by_category(self, category: str) -> List[Dict]:
        """
        获取指定分类的所有标签
        
        Args:
            category: 分类名称，如 "c1", "c2" 等
            
        Returns:
            该分类下的所有标签
        """
        results = []
        for tag_id, tag_info in self._tag_cache.items():
            if tag_info.get('category') == category:
                results.append(tag_info)
        return results
    
    def get_categories(self) -> Dict[str, str]:
        """
        获取所有分类
        
        Returns:
            分类字典，key为分类ID（如"c1"），value为分类名称（如"主題"）
        """
        return self._category_cache.copy()


# 全局标签管理器实例
_tag_manager: Optional[TagManager] = None


def get_tag_manager() -> TagManager:
    """
    获取全局标签管理器实例
    
    Returns:
        TagManager 实例
    """
    global _tag_manager
    if _tag_manager is None:
        _tag_manager = TagManager()
    return _tag_manager


def get_tag_by_name(tag_name: str, use_traditional: bool = True) -> Optional[Dict]:
    """
    通过标签名称获取标签信息（便捷函数）
    
    Args:
        tag_name: 标签名称（简体或繁体）
        use_traditional: 如果简体搜索不到，是否尝试繁体转换后搜索
        
    Returns:
        标签信息字典，找不到返回None
    """
    manager = get_tag_manager()
    return manager.get_tag_by_name(tag_name, use_traditional)


def get_tag_by_id(tag_id: str) -> Optional[Dict]:
    """
    通过标签ID获取标签信息（便捷函数）
    
    Args:
        tag_id: 标签ID，格式如 "c1=23"
        
    Returns:
        标签信息字典，找不到返回None
    """
    manager = get_tag_manager()
    return manager.get_tag_by_id(tag_id)


def search_tags_by_keyword(keyword: str, use_traditional: bool = True) -> List[Dict]:
    """
    通过关键词模糊搜索标签（便捷函数）
    
    Args:
        keyword: 搜索关键词
        use_traditional: 如果简体搜索不到，是否尝试繁体转换后搜索
        
    Returns:
        匹配的标签列表
    """
    manager = get_tag_manager()
    return manager.search_tags_by_keyword(keyword, use_traditional)


def convert_to_traditional(text: str) -> str:
    """
    简体转换为繁体（便捷函数）
    
    Args:
        text: 简体文本
        
    Returns:
        繁体文本
    """
    manager = get_tag_manager()
    return manager._to_traditional(text)
