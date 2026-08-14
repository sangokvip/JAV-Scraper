import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom

def generate_nfo(data: dict, output_path: str):
    root = ET.Element("movie")
    
    # 标题
    title_val = f"[{data.get('code', '')}] {data.get('title', '')}"
    ET.SubElement(root, "title").text = title_val
    ET.SubElement(root, "originaltitle").text = data.get("title", "")
    
    # 番号 ID
    uniqueid = ET.SubElement(root, "uniqueid", type="num", default="true")
    uniqueid.text = data.get("code", "")
    if data.get("javdb_id"):
        javdb_uid = ET.SubElement(root, "uniqueid", type="javdb")
        javdb_uid.text = data["javdb_id"]

    # 发行日期
    date = data.get("date", "")
    ET.SubElement(root, "premiered").text = date
    ET.SubElement(root, "releasedate").text = date
    if len(date) >= 4 and date[:4].isdigit():
        ET.SubElement(root, "year").text = date[:4]

    # 评分（10 分制）
    if data.get("rating"):
        ET.SubElement(root, "rating").text = str(data["rating"])
    
    # 片商
    ET.SubElement(root, "studio").text = data.get("studio", "")

    # 系列 → <set>（Kodi/Jellyfin 的合集字段，勿与片商混写）
    series = data.get("series", "")
    if series:
        set_el = ET.SubElement(root, "set")
        ET.SubElement(set_el, "name").text = series

    # 标签：genre 只放前 5 个主类别（javdb 单片可有 20+ 标签，
    # 全塞 genre 会淹没媒体库的类型筛选），完整列表进 tag
    tags = data.get("tags", [])
    for tag in tags[:5]:
        ET.SubElement(root, "genre").text = tag
    for tag in tags:
        ET.SubElement(root, "tag").text = tag
        
    # 演员
    for actor_name in data.get("actors", []):
        actor_el = ET.SubElement(root, "actor")
        ET.SubElement(actor_el, "name").text = actor_name
        ET.SubElement(actor_el, "role").text = "Actor"
        
    # 简介
    ET.SubElement(root, "plot").text = data.get("plot", "")

    # 预告片
    if data.get("trailer"):
        ET.SubElement(root, "trailer").text = data["trailer"]
    
    # 海报/背景图：顶层 <poster>/<fanart> 兼容部分刮削器，
    # <art> 包裹的写法才是 Kodi movie.nfo 标准，两者都写
    ET.SubElement(root, "poster").text = "poster.jpg"
    fanart_el = ET.SubElement(root, "fanart")
    ET.SubElement(fanart_el, "thumb").text = "fanart.jpg"
    art_el = ET.SubElement(root, "art")
    ET.SubElement(art_el, "poster").text = "poster.jpg"
    ET.SubElement(art_el, "fanart").text = "fanart.jpg"
    
    # 美化 XML 输出
    raw_xml = ET.tostring(root, encoding="utf-8")
    parsed = minidom.parseString(raw_xml)
    pretty_xml = parsed.toprettyxml(indent="  ", encoding="utf-8")
    
    with open(output_path, "wb") as f:
        f.write(pretty_xml)
