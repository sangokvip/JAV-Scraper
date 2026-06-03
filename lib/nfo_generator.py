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
    
    # 发行日期
    ET.SubElement(root, "premiered").text = data.get("date", "")
    ET.SubElement(root, "releasedate").text = data.get("date", "")
    
    # 片商
    ET.SubElement(root, "studio").text = data.get("studio", "")
    
    # 标签
    for tag in data.get("tags", []):
        ET.SubElement(root, "genre").text = tag
        ET.SubElement(root, "tag").text = tag
        
    # 演员
    for actor_name in data.get("actors", []):
        actor_el = ET.SubElement(root, "actor")
        ET.SubElement(actor_el, "name").text = actor_name
        ET.SubElement(actor_el, "role").text = "Actor"
        
    # 简介
    ET.SubElement(root, "plot").text = data.get("plot", "")
    
    # 默认海报/背景图
    ET.SubElement(root, "poster").text = "poster.jpg"
    ET.SubElement(root, "fanart").text = "fanart.jpg"
    
    # 美化 XML 输出
    raw_xml = ET.tostring(root, encoding="utf-8")
    parsed = minidom.parseString(raw_xml)
    pretty_xml = parsed.toprettyxml(indent="  ", encoding="utf-8")
    
    with open(output_path, "wb") as f:
        f.write(pretty_xml)
