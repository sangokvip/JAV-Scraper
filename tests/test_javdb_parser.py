"""javdb 解析层快照测试：站点/代码任一侧结构变化时在此报警。"""
import os

import pytest
from bs4 import BeautifulSoup

from javdb_api import JavdbAPI

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture(scope="module")
def api():
    return JavdbAPI()


@pytest.fixture(scope="module")
def detail_soup():
    with open(os.path.join(FIXTURES, "detail_page.html"), encoding="utf-8") as f:
        return BeautifulSoup(f.read(), "lxml")


@pytest.fixture(scope="module")
def search_soup():
    with open(os.path.join(FIXTURES, "search_page.html"), encoding="utf-8") as f:
        return BeautifulSoup(f.read(), "lxml")


def test_extract_title_strips_site_suffix(api, detail_soup):
    title = api._extract_title(detail_soup)
    assert "MIDA-583" in title
    assert "JavDB" not in title  # "| JavDB..." 尾巴必须剥掉


def test_extract_code_from_copy_button(api, detail_soup):
    assert api._extract_code(detail_soup) == "MIDA-583"


def test_extract_date(api, detail_soup):
    assert api._extract_date(detail_soup) == "2023-05-12"


def test_extract_series(api, detail_soup):
    assert api._extract_series(detail_soup) == "絶頂シリーズ"


def test_extract_tags(api, detail_soup):
    assert api._extract_tags(detail_soup) == ["單體作品", "中出", "美少女"]


def test_extract_actors_skips_gender_symbol(api, detail_soup):
    assert api._extract_actors(detail_soup) == ["七沢みあ"]


def test_extract_actor_entries_carries_actor_id(api, detail_soup):
    entries = api._extract_actor_entries(detail_soup)
    assert entries[0]["actor_id"] == "AbCdE"
    assert entries[0]["actor_url"].endswith("/actors/AbCdE")


def test_extract_magnets_sorted_and_filtered(api, detail_soup):
    magnets = api._extract_magnets(detail_soup)
    # 非 magnet: 前缀的条目被过滤
    assert len(magnets) == 2
    # 按大小降序
    assert magnets[0]["magnet"].endswith("BIG")
    assert magnets[0]["size_mb"] == pytest.approx(4.52 * 1024)


def test_extract_preview_video_protocol_relative(api, detail_soup):
    assert api._extract_preview_video(detail_soup) == "https://cdn.example.com/preview/mida583.mp4"


def test_parse_size_units(api):
    assert api._parse_size("4.52GB") == pytest.approx(4628.48)
    assert api._parse_size("1.5TB") == pytest.approx(1.5 * 1024 * 1024)
    assert api._parse_size("512KB") == pytest.approx(0.5)
    assert api._parse_size("未知大小") == 0


def test_parse_work_item(api, search_soup):
    items = search_soup.select("div.item a")
    work = api._parse_work_item(items[0])
    assert work["video_id"] == "YwG8Ve"
    assert work["code"] == "MIDA-583"
    assert work["date"] == "2023-05-12"
    assert "4.48" in work["rating"]
    # data-src 优先于占位 src
    assert work["cover_url"].endswith("YwG8Ve.jpg")


def test_parse_work_item_exact_code_priority(api, search_soup):
    """搜 MIDA-58 时，精确匹配的第二项必须优先于模糊首项 MIDA-583。"""
    items = search_soup.select("div.item a")
    parsed = [api._parse_work_item(i) for i in items]
    codes = [p["code"] for p in parsed]
    assert codes == ["MIDA-583", "MIDA-58"]


def test_pagination_next_selector(search_soup):
    assert search_soup.select_one('nav.pagination a[rel="next"]') is not None
