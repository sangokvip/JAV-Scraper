#!/usr/bin/env python3
"""
AV 在线播放服务器
支持多数据源：MissAV、Jable
"""

from flask import Flask, request, Response, jsonify, send_from_directory
from flask_cors import CORS
from curl_cffi import requests as cffi_requests
import re
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=SCRIPT_DIR, template_folder=SCRIPT_DIR)
CORS(app)

PROXY = None

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

def extract_from_missav(avid: str, domain: str = 'missav.ai'):
    """从 MissAV 提取 m3u8"""
    headers = {**HEADERS, 'Referer': f'https://{domain}/'}
    
    urls = [
        f'https://{domain}/cn/{avid}-chinese-subtitle'.lower(),
        f'https://{domain}/cn/{avid}-uncensored-leak'.lower(),
        f'https://{domain}/cn/{avid}'.lower(),
    ]
    
    html = None
    page_url = None
    for url in urls:
        try:
            resp = cffi_requests.get(url, headers=headers, timeout=15, impersonate="chrome120")
            if resp.status_code == 200:
                html = resp.text
                page_url = url
                break
        except:
            continue
    
    if not html:
        return None, "无法获取页面"
    
    uuid = None
    if match := re.search(r"m3u8\|([a-f0-9\|]+)\|com\|surrit\|https\|video", html):
        uuid = "-".join(match.group(1).split("|")[::-1])
    elif match := re.search(r"surrit\.com/([a-f0-9-]+)", html):
        uuid = match.group(1)
    
    if not uuid:
        return None, "未找到视频源"
    
    playlist_url = f"https://surrit.com/{uuid}/playlist.m3u8"
    
    try:
        surrit_headers = {
            **HEADERS,
            'Origin': 'https://missav.ai',
            'Referer': 'https://missav.ai/',
        }
        pl_resp = cffi_requests.get(playlist_url, headers=surrit_headers, timeout=10, impersonate="chrome120")
        if pl_resp.status_code != 200:
            return None, "无法获取播放列表"
        
        streams = []
        pattern = re.compile(r'#EXT-X-STREAM-INF:BANDWIDTH=(\d+),.*?RESOLUTION=(\d+x\d+).*?\n(.*)')
        
        for match in pattern.finditer(pl_resp.text):
            streams.append({
                'bandwidth': int(match.group(1)),
                'resolution': match.group(2),
                'url': match.group(3).strip()
            })
        
        if not streams:
            return None, "未找到视频流"
        
        streams.sort(key=lambda x: x['bandwidth'], reverse=True)
        
        from urllib.parse import urlparse
        for s in streams:
            if not s['url'].startswith('http'):
                s['url'] = f"https://surrit.com/{uuid}/{s['url']}"
            s['proxy_url'] = f"/proxy/surrit.com{urlparse(s['url']).path}"
        
        return {
            'avid': avid,
            'uuid': uuid,
            'streams': streams,
            'playlist_url': playlist_url,
            'page_url': page_url,
            'source': 'MissAV'
        }, None
        
    except Exception as e:
        return None, str(e)


def extract_from_jable(avid: str, domain: str = 'jable.tv'):
    """从 Jable 提取 m3u8"""
    headers = {**HEADERS, 'Referer': f'https://{domain}/'}
    
    url = f'https://{domain}/videos/{avid}/'.lower()
    
    try:
        resp = cffi_requests.get(url, headers=headers, timeout=15, impersonate="chrome120")
        if resp.status_code != 200:
            return None, f"页面返回 {resp.status_code}"
        
        html = resp.text
    except Exception as e:
        return None, f"请求失败: {str(e)}"
    
    pattern = r"var hlsUrl = '(https?://[^']+)'"
    match = re.search(pattern, html)
    
    if not match:
        return None, "未找到 m3u8 链接"
    
    m3u8_url = match.group(1)
    
    try:
        from urllib.parse import urlparse, parse_qs
        import base64
        parsed = urlparse(m3u8_url)
        
        m3u8_resp = cffi_requests.get(m3u8_url, headers=headers, timeout=10, impersonate="chrome120")
        if m3u8_resp.status_code != 200:
            return None, "无法获取 m3u8 内容"
        
        streams = []
        pattern = re.compile(r'#EXT-X-STREAM-INF:BANDWIDTH=(\d+),.*?RESOLUTION=(\d+x\d+).*?\n(.*)')
        
        for m in pattern.finditer(m3u8_resp.text):
            streams.append({
                'bandwidth': int(m.group(1)),
                'resolution': m.group(2),
                'url': m.group(3).strip()
            })
        
        if streams:
            streams.sort(key=lambda x: x['bandwidth'], reverse=True)
            
            base_url = m3u8_url.rsplit('/', 1)[0]
            for s in streams:
                if not s['url'].startswith('http'):
                    s['url'] = f"{base_url}/{s['url']}"
                encoded_url = base64.b64encode(s['url'].encode('utf-8')).decode('utf-8')
                s['proxy_url'] = f"/proxy2?url={encoded_url}"
        else:
            encoded_url = base64.b64encode(m3u8_url.encode('utf-8')).decode('utf-8')
            streams = [{
                'bandwidth': 0,
                'resolution': 'unknown',
                'url': m3u8_url,
                'proxy_url': f"/proxy2?url={encoded_url}"
            }]
        
        return {
            'avid': avid,
            'streams': streams,
            'm3u8_url': m3u8_url,
            'page_url': url,
            'source': 'Jable'
        }, None
        
    except Exception as e:
        return None, str(e)


@app.route('/')
def index():
    index_path = os.path.join(SCRIPT_DIR, 'index.html')
    with open(index_path, 'r', encoding='utf-8') as f:
        return f.read()


@app.route('/api/extract/<avid>')
def extract_m3u8(avid):
    """提取 m3u8 链接"""
    avid = avid.upper()
    source = request.args.get('source', 'missav')
    
    if source == 'jable':
        domain = request.args.get('domain', 'jable.tv')
        result, error = extract_from_jable(avid, domain)
    else:
        domain = request.args.get('domain', 'missav.ai')
        result, error = extract_from_missav(avid, domain)
    
    if error:
        return jsonify({'error': error}), 404
    
    return jsonify(result)


@app.route('/api/sources')
def get_sources():
    """获取可用的数据源列表"""
    return jsonify({
        'sources': [
            {'id': 'missav', 'name': 'MissAV', 'domains': ['missav.ai', 'missav.ws', 'missav.com']},
            {'id': 'jable', 'name': 'Jable', 'domains': ['jable.tv']}
        ]
    })


@app.route('/proxy/<domain>/<path:path>')
def proxy_request(domain, path):
    """代理请求"""
    from urllib.parse import urlparse, unquote
    import base64
    from flask import make_response
    
    query_string = request.query_string.decode()
    target_url = f"https://{domain}/{path}"
    if query_string:
        target_url += f"?{query_string}"
    
    referer = request.headers.get('Referer', '')
    origin = None
    if 'jable' in domain:
        referer = f'https://{domain}/'
    elif 'missav' in domain or 'surrit' in domain:
        referer = 'https://missav.ai/'
        origin = 'https://missav.ai'
    
    headers = {**HEADERS, 'Referer': referer}
    if origin:
        headers['Origin'] = origin
    
    try:
        resp = cffi_requests.get(
            target_url,
            headers=headers,
            proxies={'http': PROXY, 'https': PROXY} if PROXY else None,
            timeout=30,
            impersonate="chrome120"
        )
        
        content = resp.content
        content_type = resp.headers.get('Content-Type', '').lower()
        
        if 'mpegurl' in content_type or 'm3u8' in content_type or path.endswith('.m3u8'):
            content_text = content.decode('utf-8')
            base_url = target_url.rsplit('/', 1)[0]
            
            lines = content_text.split('\n')
            new_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith('#'):
                    if not stripped.startswith('http://') and not stripped.startswith('https://'):
                        new_lines.append(f"/proxy/{domain}{urlparse(base_url).path}/{stripped}")
                    else:
                        parsed = urlparse(stripped)
                        encoded_url = base64.b64encode(stripped.encode('utf-8')).decode('utf-8')
                        new_lines.append(f"/proxy2?url={encoded_url}")
                else:
                    new_lines.append(line)
            
            content = '\n'.join(new_lines).encode('utf-8')
        
        response = make_response(content)
        response.status_code = resp.status_code
        
        excluded = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        for n, v in resp.headers.items():
            if n.lower() not in excluded:
                response.headers[n] = v
        
        return response
        
    except Exception as e:
        return Response(f'Proxy error: {str(e)}', status=500)


@app.route('/proxy2', methods=['GET', 'POST'])
def proxy_request2():
    """代理请求（完整URL方式）"""
    from urllib.parse import urlparse, unquote, urljoin
    import base64
    import re
    from flask import make_response
    
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        url = data.get('url', '')
    else:
        query_string = request.query_string.decode()
        url = None
        for param in query_string.split('&'):
            if param.startswith('url='):
                url = param[4:]
                break
        
        if url:
            try:
                url = base64.b64decode(url).decode('utf-8')
            except:
                url = unquote(url)
    
    if not url:
        return Response('Missing url parameter', status=400)
    
    if not url.startswith('http://') and not url.startswith('https://'):
        url = f'https://{url}'
    
    parsed = urlparse(url)
    
    referer = request.headers.get('Referer', '')
    origin = None
    if 'jable' in parsed.netloc:
        referer = f'https://{parsed.netloc}/'
    elif 'missav' in parsed.netloc or 'surrit' in parsed.netloc or 'mushroom' in parsed.netloc:
        referer = 'https://missav.ai/'
        origin = 'https://missav.ai'
    
    headers = {**HEADERS, 'Referer': referer}
    if origin:
        headers['Origin'] = origin
    
    try:
        resp = cffi_requests.get(
            url,
            headers=headers,
            proxies={'http': PROXY, 'https': PROXY} if PROXY else None,
            timeout=30,
            impersonate="chrome120"
        )
        
        content = resp.content
        content_type = resp.headers.get('Content-Type', '').lower()
        
        if 'mpegurl' in content_type or 'm3u8' in content_type or url.endswith('.m3u8'):
            content_text = content.decode('utf-8')
            base_url = url.rsplit('/', 1)[0]
            
            def replace_key_uri(m):
                full_match = m.group(0)
                method = m.group(1)
                key_uri = m.group(2)
                
                if not key_uri.startswith('http://') and not key_uri.startswith('https://'):
                    full_key_url = f"{base_url}/{key_uri}"
                    encoded_key_url = base64.b64encode(full_key_url.encode('utf-8')).decode('utf-8')
                    proxy_key_url = f"/proxy2?url={encoded_key_url}"
                    return full_match.replace(key_uri, proxy_key_url)
                
                return full_match
            
            def replace_ts_uri(uri):
                if not uri.startswith('http://') and not uri.startswith('https://'):
                    full_ts_url = f"{base_url}/{uri}"
                    encoded_ts_url = base64.b64encode(full_ts_url.encode('utf-8')).decode('utf-8')
                    return f"/proxy2?url={encoded_ts_url}"
                return uri
            
            content_text = re.sub(r'#EXT-X-KEY:METHOD=([^,]+),URI="([^"]+)"', replace_key_uri, content_text)
            
            lines = content_text.split('\n')
            new_lines = []
            for line in lines:
                if line.strip() and not line.startswith('#'):
                    new_lines.append(replace_ts_uri(line.strip()))
                else:
                    new_lines.append(line)
            
            content_text = '\n'.join(new_lines)
            content = content_text.encode('utf-8')
        
        response = make_response(content)
        response.status_code = resp.status_code
        
        excluded = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        for n, v in resp.headers.items():
            if n.lower() not in excluded:
                response.headers[n] = v
        
        return response
        
    except Exception as e:
        return Response(f'Proxy error: {str(e)}', status=500)


if __name__ == '__main__':
    print("="*60)
    print("AV 在线播放服务器 (多源版)")
    print("="*60)
    print("访问地址: http://localhost:5000")
    print("="*60)
    print("\n支持的数据源:")
    print("  - MissAV (missav.ai)")
    print("  - Jable (jable.tv)")
    print("\n使用方法:")
    print("1. 打开浏览器访问 http://localhost:5000")
    print("2. 选择数据源")
    print("3. 输入番号，点击播放")
    print("\n按 Ctrl+C 停止服务器\n")
    
    app.run(host='127.0.0.1', port=5000, debug=False, threaded=True)
