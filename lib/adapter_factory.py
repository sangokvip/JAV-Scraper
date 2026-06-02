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


class AdapterFactory:
    """适配器工厂"""
    
    _adapters = {
        Platform.JAVDB: JavdbAdapter,
    }
    
    _instances: Dict[Platform, BaseAdapter] = {}
    
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
        # 检查是否已有实例
        if platform in cls._instances:
            return cls._instances[platform]
        
        adapter_class = cls._adapters.get(platform)
        if not adapter_class:
            raise ValueError(f"不支持的平台: {platform}")
        
        # 创建新实例
        adapter = adapter_class(existing_tags=existing_tags, **kwargs)
        cls._instances[platform] = adapter
        
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
        elif platform in cls._instances:
            del cls._instances[platform]
    
    @classmethod
    def get_supported_platforms(cls) -> list:
        """
        获取支持的平台列表
        
        Returns:
            平台列表
        """
        return list(cls._adapters.keys())
