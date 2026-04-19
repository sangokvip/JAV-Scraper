from __future__ import annotations

import os
import sys
from typing import Any, Dict, List


CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
THIRD_PARTY_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
BACKEND_ROOT = os.path.abspath(os.path.join(THIRD_PARTY_ROOT, ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from protocol.base import ProtocolProvider
from third_party.credential_guard import get_adapter_credential_status
from third_party.javdb_adapter import JavdbAdapter as LegacyCollectionJavdbAdapter
from third_party.javdb_api_scraper import JavbusAdapter as WrappedJavbusAdapter
from third_party.javdb_api_scraper import JavdbAdapter as WrappedJavdbAdapter


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


class JavdbProvider(_VideoProviderBase):
    PLATFORM_NAME = "javdb"

    def _get_collection_client(self, config: Dict[str, Any]):
        normalized = dict(config or {})
        return LegacyCollectionJavdbAdapter(normalized)

    def get_legacy_client(self, config: Dict[str, Any], *args, **kwargs):
        status = self.get_query_status(config)
        if not bool(status.get("configured", False)):
            raise RuntimeError(str(status.get("message") or "JAVDB 平台未配置 cookie"))
        existing_tags = self._extract_existing_tags(*args, **kwargs)
        domain_index = int((config or {}).get("domain_index", 0) or 0)
        return WrappedJavdbAdapter(existing_tags, domain_index=domain_index)

    def execute(self, capability: str, params: Dict[str, Any], context: Dict[str, Any], config: Dict[str, Any]):
        adapter = self.get_legacy_client(config, params.get("existing_tags") or [])
        if capability == "catalog.search":
            return adapter.search_videos(
                str(params.get("keyword") or ""),
                page=int(params.get("page", 1) or 1),
                max_pages=int(params.get("max_pages", 1) or 1),
            )
        if capability == "catalog.detail":
            return adapter.get_video_detail(str(params.get("video_id") or ""))
        if capability == "catalog.by_code":
            if not hasattr(adapter, "get_video_by_code"):
                return None
            return adapter.get_video_by_code(str(params.get("code") or ""))
        if capability == "person.search":
            return adapter.search_actor(str(params.get("actor_name") or ""))
        if capability == "person.works":
            return adapter.get_actor_works(
                str(params.get("actor_id") or ""),
                page=int(params.get("page", 1) or 1),
                max_pages=int(params.get("max_pages", 1) or 1),
            )
        if capability == "collection.list":
            return self._get_collection_client(config).get_user_lists()
        if capability == "collection.detail":
            return self._get_collection_client(config).get_list_detail(str(params.get("list_id") or ""))
        if capability == "collection.favorites":
            return self._get_collection_client(config).get_favorites()
        if capability == "taxonomy.tags":
            return self._get_tag_bundle(adapter)
        if capability == "taxonomy.tag_search":
            return adapter.search_by_tags(
                page=int(params.get("page", 1) or 1),
                max_pages=int(params.get("max_pages", 1) or 1),
                **dict(params.get("tag_params") or {}),
            )
        if capability == "health.query.status":
            return self.get_query_status(config)
        raise ValueError(f"unsupported capability: {capability}")


class JavbusProvider(ProtocolProvider):
    def get_legacy_client(self, config: Dict[str, Any], *args, **kwargs):
        existing_tags = []
        if args and isinstance(args[0], list):
            existing_tags = args[0]
        return WrappedJavbusAdapter(existing_tags)

    def execute(self, capability: str, params: Dict[str, Any], context: Dict[str, Any], config: Dict[str, Any]):
        adapter = self.get_legacy_client(config, params.get("existing_tags") or [])
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

