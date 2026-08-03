"""
适配器工厂
管理所有适配器的注册和实例化
"""

import json
import os
from typing import Optional, Dict, Any
from pathlib import Path

from .platform import Platform
from .base_adapter import BaseAdapter
from .javdb_adapter import JavdbAdapter
from .jav321_adapter import Jav321Adapter


class AdapterFactory:
    """适配器工厂"""
    
    _adapters = {
        Platform.JAVDB: JavdbAdapter,
        Platform.JAV321: Jav321Adapter,
    }
    
    _instances: Dict[Platform, BaseAdapter] = {}
    _instance_params: Dict[Platform, str] = {}

    @classmethod
    def get_adapter(cls, platform: Platform, existing_tags: list = None, **kwargs) -> BaseAdapter:
        """
        获取指定平台的适配器

        Args:
            platform: 平台类型
            existing_tags: 已有的标签列表
            **kwargs: 其他参数

        Returns:
            适配器实例
        """
        # 缓存键纳入构造参数指纹：用户改代理/域名后必须重建实例，
        # 否则命中旧缓存时新参数被静默丢弃
        try:
            params_key = json.dumps({'existing_tags_len': len(existing_tags or []), **kwargs},
                                    sort_keys=True, default=str)
        except TypeError:
            params_key = str(kwargs)

        if platform in cls._instances and cls._instance_params.get(platform) == params_key:
            return cls._instances[platform]

        adapter_class = cls._adapters.get(platform)
        if not adapter_class:
            raise ValueError(f"不支持的平台: {platform}")

        # 创建新实例（参数变化时覆盖旧实例）
        adapter = adapter_class(existing_tags=existing_tags, **kwargs)
        cls._instances[platform] = adapter
        cls._instance_params[platform] = params_key

        return adapter
    
    @classmethod
    def get_adapter_by_name(cls, platform_name: str, existing_tags: list = None, **kwargs) -> BaseAdapter:
        """
        根据名称获取适配器
        
        Args:
            platform_name: 平台名称
            existing_tags: 已有的标签列表
            **kwargs: 其他参数
            
        Returns:
            适配器实例
        """
        from .platform import get_platform_by_name
        
        platform = get_platform_by_name(platform_name)
        if not platform:
            raise ValueError(f"未知的平台: {platform_name}")
        
        return cls.get_adapter(platform, existing_tags, **kwargs)
    
    @classmethod
    def register_adapter(cls, platform: Platform, adapter_class: type):
        """
        注册新的适配器
        
        Args:
            platform: 平台类型
            adapter_class: 适配器类
        """
        if not issubclass(adapter_class, BaseAdapter):
            raise ValueError("适配器类必须继承 BaseAdapter")
        
        cls._adapters[platform] = adapter_class
    
    @classmethod
    def clear_instance(cls, platform: Platform = None):
        """
        清除适配器实例
        
        Args:
            platform: 平台类型，如果为None则清除所有实例
        """
        if platform is None:
            cls._instances.clear()
            cls._instance_params.clear()
        elif platform in cls._instances:
            del cls._instances[platform]
            cls._instance_params.pop(platform, None)
    
    @classmethod
    def get_supported_platforms(cls) -> list:
        """
        获取支持的平台列表
        
        Returns:
            平台列表
        """
        return list(cls._adapters.keys())
