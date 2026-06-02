import os
import xml.etree.ElementTree as ET
from lib.nfo_generator import generate_nfo

def test_generate_nfo(tmp_path):
    target_nfo = tmp_path / "test_movie.nfo"
    data = {
        "code": "SSIS-123",
        "title": "秘密のデート",
        "date": "2026-03-04",
        "studio": "S1 NO.1 STYLE",
        "tags": ["美少女", "单体"],
        "actors": ["井上もも"],
        "plot": "这里是剧情大纲。"
    }
    
    generate_nfo(data, str(target_nfo))
    
    assert target_nfo.exists()
    tree = ET.parse(target_nfo)
    root = tree.getroot()
    
    assert root.tag == "movie"
    assert root.find("title").text == "[SSIS-123] 秘密のデート"
    assert root.find("uniqueid").text == "SSIS-123"
    assert root.find("premiered").text == "2026-03-04"
    assert root.find("studio").text == "S1 NO.1 STYLE"
    genres = [g.text for g in root.findall("genre")]
    assert "美少女" in genres
    assert "单体" in genres
    actors = [a.find("name").text for a in root.findall("actor")]
    assert "井上もも" in actors
