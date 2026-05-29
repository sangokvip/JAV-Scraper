from __future__ import annotations

import importlib.util
import os
import re
import sys
from typing import Any, Dict, List

from bs4 import BeautifulSoup, FeatureNotFound

CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
THIRD_PARTY_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
BACKEND_ROOT = os.path.abspath(os.path.join(THIRD_PARTY_ROOT, ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
LIB_DIR = os.path.join(CURRENT_DIR, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)
JAVDB_UTILS_PATH = os.path.abspath(os.path.join(CURRENT_DIR, "utils.py"))

cached_utils = sys.modules.get("utils")
if cached_utils is not None:
    cached_utils_file = os.path.abspath(str(getattr(cached_utils, "__file__", "") or ""))
    if cached_utils_file != JAVDB_UTILS_PATH:
        del sys.modules["utils"]

if os.path.exists(JAVDB_UTILS_PATH) and "utils" not in sys.modules:
    spec = importlib.util.spec_from_file_location("utils", JAVDB_UTILS_PATH)
    if spec is not None and spec.loader is not None:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sys.modules["utils"] = module

from protocol.base import ProtocolProvider
from protocol.credential_guard import get_adapter_credential_status
from javdb_api import JavdbAPI
from lib.javbus_adapter import JavbusAdapter as PluginJavbusAdapter
from lib.javdb_adapter import JavdbAdapter as PluginJavdbAdapter


def _parse_cookie_string(cookie_string: str) -> Dict[str, str]:
    cookies: Dict[str, str] = {}
    raw = str(cookie_string or "").strip()
    if not raw:
        return cookies
    for part in raw.split(";"):
        pair = part.strip()
        if not pair or "=" not in pair:
            continue
        key, value = pair.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key:
            cookies[key] = value
    return cookies


def _normalize_javdb_cookie_input(cookie_input: str) -> Dict[str, str]:
    raw = str(cookie_input or "").strip()
    if not raw:
        return {}
    parsed = _parse_cookie_string(raw)
    if not parsed:
        parsed = {"_jdb_session": raw}
    session_value = str(parsed.get("_jdb_session", "")).strip()
    if not session_value:
        return {}
    normalized = {
        "_jdb_session": session_value,
        "list_mode": "h",
        "theme": "auto",
        "over18": "1",
        "locale": "zh",
    }
    for key in ("list_mode", "theme", "over18", "locale"):
        value = str(parsed.get(key, "")).strip()
        if value:
            normalized[key] = value
    return normalized


class _VideoProviderBase(ProtocolProvider):
    PLATFORM_NAME = ""

    def _extract_existing_tags(self, *args, **kwargs) -> List[Dict[str, Any]]:
        if args:
            first = args[0]
            if isinstance(first, list):
                return first
        existing_tags = kwargs.get("existing_tags")
        if isinstance(existing_tags, list):
            return existing_tags
        return []

    def serialize_public_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        public = dict(config or {})
        cookies = public.get("cookies") or {}
        if isinstance(cookies, dict) and cookies:
            public["cookie_string"] = str(cookies.get("_jdb_session", "")).strip()
        else:
            public["cookie_string"] = ""
        return public

    def normalize_config(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(payload or {})
        normalized.setdefault("enabled", True)
        cookie_string = normalized.pop("cookie_string", None)
        if cookie_string is not None:
            normalized["cookies"] = _normalize_javdb_cookie_input(cookie_string)
        elif isinstance(normalized.get("cookies"), str):
            normalized["cookies"] = _normalize_javdb_cookie_input(normalized.get("cookies"))
        return normalized

    def get_query_status(self, config: Dict[str, Any]) -> Dict[str, Any]:
        return get_adapter_credential_status("javdb", config)

    def _build_health_status_payload(self, config: Dict[str, Any]) -> Dict[str, Any]:
        status = self.get_query_status(config)
        cookies = config.get("cookies") or {}
        normalized_cookies: Dict[str, str] = {}
        if isinstance(cookies, dict):
            for raw_key, raw_value in cookies.items():
                key = str(raw_key or "").strip()
                value = str(raw_value or "").strip()
                if key and value:
                    normalized_cookies[key] = value

        return {
            "configured": bool(status.get("configured", False)),
            "cookie_keys": sorted(normalized_cookies.keys()),
            "has_session_cookie": bool(status.get("configured", False)),
            "message": str(status.get("message") or ""),
        }

    @staticmethod
    def _collect_cookies(config: Dict[str, Any]) -> Dict[str, str]:
        cookies = config.get("cookies") or {}
        normalized: Dict[str, str] = {}
        if isinstance(cookies, dict):
            for raw_key, raw_value in cookies.items():
                key = str(raw_key or "").strip()
                value = str(raw_value or "").strip()
                if key and value:
                    normalized[key] = value
        return normalized

    def _apply_config_cookies(self, target: Any, config: Dict[str, Any]) -> None:
        cookies = self._collect_cookies(config)
        if not cookies:
            return

        session = getattr(target, "session", None)
        if session is None:
            api = getattr(target, "api", None)
            session = getattr(api, "session", None)
        if session is None:
            return

        for key, value in cookies.items():
            try:
                session.cookies.set(key, value)
            except Exception:
                continue

    def _get_tag_bundle(self, adapter) -> Dict[str, Any]:
        tag_manager = getattr(getattr(adapter, "api", None), "tag_manager", None)
        if tag_manager is None:
            return {
                "tags": {},
                "categories": {},
            }
        return {
            "tags": tag_manager.get_all_tags() or {},
            "categories": tag_manager.get_categories() or {},
        }

    @staticmethod
    def _parse_tag_ids(tag_ids) -> tuple[Dict[str, List[int]], List[str], List[str], List[str]]:
        tag_params: Dict[str, List[int]] = {}
        invalid_tag_ids: List[str] = []

        for raw_tag_id in tag_ids or []:
            normalized = str(raw_tag_id or "").strip().lower()
            if not normalized:
                continue

            category, sep, value = normalized.partition("=")
            category = category.strip()
            raw_values = value.strip()

            if not sep or not re.fullmatch(r"c\d+", category):
                invalid_tag_ids.append(str(raw_tag_id))
                continue

            values: List[int] = []
            for part in raw_values.split(","):
                value_part = part.strip()
                if not value_part or not value_part.isdigit():
                    continue
                values.append(int(value_part))

            if not values:
                invalid_tag_ids.append(str(raw_tag_id))
                continue

            tag_params.setdefault(category, [])
            for parsed_value in values:
                if parsed_value not in tag_params[category]:
                    tag_params[category].append(parsed_value)

        def _category_sort_key(category_key: str):
            suffix = category_key[1:]
            return int(suffix) if suffix.isdigit() else 999

        effective_tag_ids: List[str] = []
        for category_key in sorted(tag_params.keys(), key=_category_sort_key):
            for value_item in tag_params[category_key]:
                effective_tag_ids.append(f"{category_key}={value_item}")

        return tag_params, effective_tag_ids, invalid_tag_ids, []

    @staticmethod
    def _build_tag_query(tag_params: Dict[str, List[int]]) -> str:
        query_parts: List[str] = []

        def _category_sort_key(category_key: str):
            suffix = category_key[1:]
            return int(suffix) if suffix.isdigit() else 999

        for category_key in sorted(tag_params.keys(), key=_category_sort_key):
            values = tag_params.get(category_key) or []
            if not values:
                continue
            query_parts.append(f"{category_key}={','.join(str(v) for v in values)}")

        return "&".join(query_parts)

    @staticmethod
    def _is_login_page(html_text: str) -> bool:
        if not html_text:
            return False

        lower_html = str(html_text).lower()
        title_match = re.search(r"<title[^>]*>(.*?)</title>", lower_html, re.DOTALL)
        title_text = title_match.group(1).strip() if title_match else ""
        return "登入 | javdb" in title_text or "login | javdb" in title_text

    def _is_tag_search_available(self, adapter) -> bool:
        try:
            response = adapter.api.get("/tags")
            return not self._is_login_page(response.text)
        except Exception:
            return True

    def _search_by_tag_params(self, adapter, page: int, tag_params: Dict[str, List[int]]) -> Dict[str, Any]:
        query_string = self._build_tag_query(tag_params)
        if not query_string:
            raise ValueError("empty tag query")

        path = f"/tags?{query_string}" if page <= 1 else f"/tags?{query_string}&page={page}"
        response = adapter.api.get(path)
        html_text = response.text or ""
        if self._is_login_page(html_text):
            raise PermissionError("JAVDB 标签搜索需要登录，请更新 cookies 后重试")

        try:
            soup = BeautifulSoup(html_text, "lxml")
        except FeatureNotFound:
            soup = BeautifulSoup(html_text, "html.parser")

        items = soup.select("div.item a")
        parse_work = getattr(adapter.api, "_parse_work_item", None)
        works: List[Dict[str, Any]] = []
        if callable(parse_work):
            for item in items:
                try:
                    work = parse_work(item)
                    if work:
                        works.append(work)
                except Exception:
                    continue

        has_next = soup.select_one('nav.pagination a[rel="next"]') is not None
        return {
            "page": page,
            "has_next": has_next,
            "works": works,
            "query": query_string,
        }


class JavdbProvider(_VideoProviderBase):
    PLATFORM_NAME = "javdb"

    def normalize_config(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        normalized = super().normalize_config(payload)
        normalized["domain_index"] = JavdbAPI.normalize_domain_index(normalized.get("domain_index", 0))
        return normalized

    @staticmethod
    def _get_domain_index(config: Dict[str, Any]) -> int:
        return JavdbAPI.normalize_domain_index((config or {}).get("domain_index", 0))

    def _get_collection_api(self, config: Dict[str, Any]) -> JavdbAPI:
        status = self.get_query_status(config)
        if not bool(status.get("configured", False)):
            raise RuntimeError(str(status.get("message") or "JAVDB 平台未配置 cookie"))
        domain_index = self._get_domain_index(config)
        api = JavdbAPI(domain_index=domain_index)
        self._apply_config_cookies(api, config)
        return api

    def _get_adapter(self, config: Dict[str, Any], *args, **kwargs):
        status = self.get_query_status(config)
        if not bool(status.get("configured", False)):
            raise RuntimeError(str(status.get("message") or "JAVDB 平台未配置 cookie"))
        existing_tags = self._extract_existing_tags(*args, **kwargs)
        domain_index = self._get_domain_index(config)
        adapter = PluginJavdbAdapter(existing_tags, domain_index=domain_index)
        self._apply_config_cookies(adapter, config)
        return adapter

    def _get_user_lists(self, config: Dict[str, Any]) -> Dict[str, Any]:
        lists = self._get_collection_api(config).get_user_lists_all()
        return {"lists": list(lists or [])}

    def _get_list_detail(self, config: Dict[str, Any], list_id: str) -> Dict[str, Any]:
        result = dict(self._get_collection_api(config).get_list_detail_all(list_id) or {})
        return {
            "list_id": result.get("list_id", list_id),
            "list_name": result.get("list_name", ""),
            "works": list(result.get("works") or []),
        }

    def _get_favorites(self, config: Dict[str, Any]) -> Dict[str, Any]:
        all_works: List[Dict[str, Any]] = []
        for list_data in self._get_user_lists(config).get("lists", []):
            list_id = str((list_data or {}).get("list_id") or "").strip()
            if not list_id:
                continue
            detail = self._get_list_detail(config, list_id)
            for work in detail.get("works", []) or []:
                if isinstance(work, dict):
                    all_works.append(dict(work))
        return {
            "collection_name": "JAVDB 导入",
            "user": "",
            "total_favorites": len(all_works),
            "last_updated": "",
            "videos": all_works,
        }

    def execute(self, capability: str, params: Dict[str, Any], context: Dict[str, Any], config: Dict[str, Any]):
        if capability == "catalog.search":
            adapter = self._get_adapter(config, params.get("existing_tags") or [])
            return adapter.search_videos(
                str(params.get("keyword") or ""),
                page=int(params.get("page", 1) or 1),
                max_pages=int(params.get("max_pages", 1) or 1),
            )
        if capability == "catalog.detail":
            adapter = self._get_adapter(config, params.get("existing_tags") or [])
            return adapter.get_video_detail(str(params.get("video_id") or ""))
        if capability == "catalog.by_code":
            adapter = self._get_adapter(config, params.get("existing_tags") or [])
            if not hasattr(adapter, "get_video_by_code"):
                return None
            return adapter.get_video_by_code(str(params.get("code") or ""))
        if capability == "person.search":
            adapter = self._get_adapter(config, params.get("existing_tags") or [])
            return adapter.search_actor(str(params.get("actor_name") or ""))
        if capability == "person.works":
            adapter = self._get_adapter(config, params.get("existing_tags") or [])
            return adapter.get_actor_works(
                str(params.get("actor_id") or ""),
                page=int(params.get("page", 1) or 1),
                max_pages=int(params.get("max_pages", 1) or 1),
            )
        if capability == "collection.list":
            return self._get_user_lists(config)
        if capability == "collection.detail":
            return self._get_list_detail(config, str(params.get("list_id") or ""))
        if capability == "collection.favorites":
            return self._get_favorites(config)
        if capability == "taxonomy.tags":
            keyword = str(params.get("keyword") or "").strip().lower()
            category_filter = str(params.get("category") or "").strip().lower()
            health_status = self._build_health_status_payload(config)
            if not health_status.get("configured"):
                return {
                    "categories": [],
                    "tags": [],
                    "total": 0,
                    "source_ready": False,
                    "tag_search_available": False,
                    "cookie_configured": False,
                    "message": str(health_status.get("message") or "未配置cookie，请先在系统配置中填写JAVDB cookie"),
                }

            adapter = self._get_adapter(config, params.get("existing_tags") or [])
            tag_bundle = self._get_tag_bundle(adapter)
            all_tags = tag_bundle.get("tags") or {}
            categories = tag_bundle.get("categories") or {}
            tag_search_available = self._is_tag_search_available(adapter)

            if not all_tags:
                return {
                    "categories": [],
                    "tags": [],
                    "total": 0,
                    "source_ready": False,
                    "tag_search_available": tag_search_available,
                    "cookie_configured": True,
                    "message": "JAVDB 内置标签库未初始化（缺少 tags_database.enc）",
                }

            tags: List[Dict[str, Any]] = []
            category_counts: Dict[str, int] = {}
            for tag_id, tag_info in all_tags.items():
                category = str(tag_info.get("category") or "").strip().lower()
                category_name = tag_info.get("category_name") or categories.get(category, "")
                tag_name = str(tag_info.get("name") or "").strip()

                if category_filter and category != category_filter:
                    continue

                searchable_text = f"{tag_name} {tag_id}".lower()
                if keyword and keyword not in searchable_text:
                    continue

                category_counts[category] = category_counts.get(category, 0) + 1
                tags.append(
                    {
                        "id": str(tag_id),
                        "name": tag_name,
                        "category": category,
                        "category_name": category_name,
                        "tag_id": str(tag_info.get("tag_id") or ""),
                        "value": str(tag_info.get("value") or ""),
                    }
                )

            tags.sort(key=lambda item: (item.get("category", ""), item.get("name", "")))

            response_categories: List[Dict[str, Any]] = []
            for category_key, category_name in sorted(categories.items(), key=lambda item: item[0]):
                if category_filter and category_key != category_filter:
                    continue
                count = category_counts.get(category_key, 0)
                if keyword and count == 0:
                    continue
                response_categories.append(
                    {
                        "key": category_key,
                        "name": category_name,
                        "count": count,
                    }
                )

            return {
                "categories": response_categories,
                "tags": tags,
                "total": len(tags),
                "source_ready": True,
                "tag_search_available": tag_search_available,
                "cookie_configured": True,
            }
        if capability == "taxonomy.tag_search":
            requested_tag_ids = params.get("tag_ids") or []
            if isinstance(requested_tag_ids, str):
                requested_tag_ids = [part.strip() for part in requested_tag_ids.split(",") if part.strip()]
            elif not isinstance(requested_tag_ids, list):
                requested_tag_ids = []

            tag_params, effective_tag_ids, invalid_tag_ids, overridden_tag_ids = self._parse_tag_ids(requested_tag_ids)
            if not tag_params:
                raise ValueError("请至少提供一个有效 tag_id（格式如 c1=23）")

            adapter = self._get_adapter(config, params.get("existing_tags") or [])
            if not self._is_tag_search_available(adapter):
                raise PermissionError("JAVDB 标签搜索需要登录，请更新 cookies 后重试")

            result = self._search_by_tag_params(
                adapter,
                page=max(int(params.get("page", 1) or 1), 1),
                tag_params=tag_params,
            )
            works = [dict(item or {}) for item in (result.get("works") or []) if isinstance(item, dict)]
            return {
                "platform": self.PLATFORM_NAME,
                "page": result.get("page", 1),
                "has_next": result.get("has_next", False),
                "total_pages": result.get("total_pages"),
                "videos": works,
                "works": works,
                "query": result.get("query"),
                "requested_tag_ids": list(requested_tag_ids),
                "effective_tag_ids": effective_tag_ids,
                "invalid_tag_ids": invalid_tag_ids,
                "overridden_tag_ids": overridden_tag_ids,
            }
        if capability == "health.query.status":
            return self._build_health_status_payload(config)
        raise ValueError(f"unsupported capability: {capability}")


class JavbusProvider(ProtocolProvider):
    def _get_adapter(self, config: Dict[str, Any], *args, **kwargs):
        existing_tags = []
        if args and isinstance(args[0], list):
            existing_tags = args[0]
        return PluginJavbusAdapter(existing_tags)

    def execute(self, capability: str, params: Dict[str, Any], context: Dict[str, Any], config: Dict[str, Any]):
        adapter = self._get_adapter(config, params.get("existing_tags") or [])
        if capability == "catalog.search":
            return adapter.search_videos(
                str(params.get("keyword") or ""),
                page=int(params.get("page", 1) or 1),
                max_pages=int(params.get("max_pages", 1) or 1),
            )
        if capability == "catalog.detail":
            return adapter.get_video_detail(str(params.get("video_id") or ""))
        if capability == "person.search":
            return adapter.search_actor(str(params.get("actor_name") or ""))
        if capability == "person.works":
            return adapter.get_actor_works(
                str(params.get("actor_id") or ""),
                page=int(params.get("page", 1) or 1),
                max_pages=int(params.get("max_pages", 1) or 1),
            )
        if capability == "health.query.status":
            return {
                "configured": True,
                "message": "",
                "missing_fields": [],
            }
        raise ValueError(f"unsupported capability: {capability}")
