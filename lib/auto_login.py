"""
自动化登录辅助模块
使用本地服务器接收浏览器登录后的 cookies
"""

import json
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import time

import config
from lib.logger import get_logger

log = get_logger(__name__)


class CookieReceiverHandler(BaseHTTPRequestHandler):
    """Cookie 接收处理器"""
    
    def do_GET(self):
        """处理 GET 请求"""
        if self.path == '/':
            # 返回登录页面
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            
            html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>JAVDB 登录助手</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            margin-bottom: 20px;
        }
        .step {
            margin: 20px 0;
            padding: 15px;
            background: #e8f4f8;
            border-left: 4px solid #2196F3;
        }
        .step h3 {
            margin-top: 0;
            color: #2196F3;
        }
        button {
            background: #4CAF50;
            color: white;
            padding: 12px 24px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            margin: 10px 0;
        }
        button:hover {
            background: #45a049;
        }
        .success {
            color: #4CAF50;
            font-weight: bold;
        }
        .error {
            color: #f44336;
            font-weight: bold;
        }
        .info {
            color: #2196F3;
            font-weight: bold;
        }
        textarea {
            width: 100%;
            padding: 10px;
            margin: 10px 0;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-family: monospace;
            font-size: 12px;
        }
        ol {
            margin: 10px 0;
            padding-left: 20px;
        }
        li {
            margin: 5px 0;
        }
        .image-container {
            margin: 20px 0;
            text-align: center;
        }
        .image-item {
            margin: 15px 0;
        }
        .image-item img {
            max-width: 100%;
            border: 1px solid #ddd;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .image-item p {
            margin-top: 5px;
            font-size: 14px;
            color: #666;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔐 JAVDB 自动登录助手</h1>
        
        <div class="step">
            <h3>步骤 1: 点击下方按钮打开 JAVDB 登录页面</h3>
            <button onclick="openJavdb()">打开 JAVDB 登录页面</button>
        </div>
        
        <div class="step">
            <h3>步骤 2: 在新打开的浏览器窗口中登录</h3>
            <p>使用您的账号密码登录 JAVDB</p>
        </div>
        
        <div class="step">
            <h3>步骤 3: 获取 Session 值</h3>
            <p>登录成功后，按以下步骤获取 Session 值：</p>
            <ol>
                <li>在 JAVDB 页面按 <strong>F12</strong> 打开开发者工具</li>
                <li>切换到 <strong>Application</strong>（或"应用程序"）标签</li>
                <li>在左侧找到 <strong>Cookies</strong> → <strong>https://javdb.com</strong></li>
                <li>找到名为 <code>_jdb_session</code> 的 Cookie</li>
                <li>点击该 Cookie，复制 <strong>Value</strong> 列的值</li>
            </ol>
            
            <div class="image-container">
                <h4>操作步骤截图：</h4>
                <div class="image-item">
                    <img src="/screenshots/1.png" alt="步骤 1 - 打开开发者工具">
                    <p>图 1: 按 F12 打开开发者工具</p>
                </div>
                <div class="image-item">
                    <img src="/screenshots/2.png" alt="步骤 2 - 找到 Cookies">
                    <p>图 2: 找到 Cookies → https://javdb.com</p>
                </div>
                <div class="image-item">
                    <img src="/screenshots/3.png" alt="步骤 3 - 复制 Session 值">
                    <p>图 3: 找到并复制 _jdb_session 的值</p>
                </div>
            </div>
            
            <p class="info">💡 提示：截图保存到 <code>test/output/screenshots/</code> 目录作为教学文档</p>
        </div>
        
        <div class="step">
            <h3>步骤 4: 粘贴 Session 值</h3>
            <p>将复制的 Session 值粘贴到下方输入框：</p>
            <textarea id="sessionInput" rows="5" 
                placeholder="粘贴 _jdb_session 的值，例如：
WxfOVU11nGDFZ79PnSUnPdkhvwY7ptpqqsm1lrlKO%2F2yuTDVmCno%2FOtDT8FC%2BoiFT2IXNobjsSsIsM6HtDCcT97M5Di%2FbsmDe1pmak0xTebtkuLyWMgRyq1n7TQ8%2BI0LitYKOWV%2BLDxE%2BQ2N2S%2F%2Fi9f9LSTDLPa9yFRMZAcRheczH2PnDcIe%2FstlKhcOw2ZtVIFmUZhBVNqpcxXjZ7laelaA3cMW9hVofli4%2FvHa5UXBts4e8UFDeR16p6iRFTGFIQiFYFkKCpKuLmNULmkxIIJtNB6tEcBSwztv%2FbRN0Ec8Z%2BBEgNXsHWIPXjYR0JOrQsf%2BfMP1Wbuolm4W6zbODxcGK%2Bb8CXaw7myvMaiLFv50FuHs2zajkUu%2BCCfKH%2FnEvsg%3D--0Brj7Un3a3rOeJmd--zerO3ajfM2pW%2FouM%2BPciIQ%3D%3D"></textarea>
            <button onclick="submitSession()">提交 Session</button>
        </div>
        
        <div id="result"></div>
    </div>
    
    <script>
        function openJavdb() {
            window.open('https://javdb.com/login', '_blank');
        }
        
        function submitSession() {
            const sessionInput = document.getElementById('sessionInput').value;
            const resultDiv = document.getElementById('result');
            
            if (!sessionInput.trim()) {
                resultDiv.innerHTML = '<p class="error">请先粘贴 Session 值！</p>';
                return;
            }
            
            const cookies = [{
                "name": "_jdb_session",
                "value": sessionInput.trim(),
                "domain": ".javdb.com"
            }];
            
            submitCookiesData(cookies);
        }
        
        function submitCookiesData(cookies) {
            const resultDiv = document.getElementById('result');
            
            fetch('/save-cookies', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({cookies: cookies})
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    resultDiv.innerHTML = '<p class="success">✅ Session 保存成功！现在可以关闭此页面。</p>';
                } else {
                    resultDiv.innerHTML = '<p class="error">❌ 保存失败: ' + data.error + '</p>';
                }
            })
            .catch(error => {
                resultDiv.innerHTML = '<p class="error">❌ 提交失败: ' + error.message + '</p>';
            });
        }
    </script>
</body>
</html>
            """
            self.wfile.write(html.encode('utf-8'))
        
        elif self.path.startswith('/screenshots/'):
            # 处理截图请求
            import os
            screenshot_path = self.path.replace('/screenshots/', '')
            screenshots_dir = (Path(__file__).parent / 'screenshots').resolve()
            full_path = (screenshots_dir / screenshot_path).resolve()

            # 防路径遍历：解析后必须仍在 screenshots 目录内
            if screenshots_dir not in full_path.parents and full_path != screenshots_dir:
                self.send_response(404)
                self.end_headers()
                return

            if full_path.exists() and full_path.is_file():
                # 确定文件类型
                if screenshot_path.endswith('.png'):
                    content_type = 'image/png'
                elif screenshot_path.endswith('.jpg') or screenshot_path.endswith('.jpeg'):
                    content_type = 'image/jpeg'
                elif screenshot_path.endswith('.gif'):
                    content_type = 'image/gif'
                else:
                    content_type = 'application/octet-stream'
                
                # 发送文件
                self.send_response(200)
                self.send_header('Content-type', content_type)
                self.end_headers()
                with open(full_path, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        """处理 POST 请求"""
        if self.path == '/save-cookies':
            # 防 CSRF：只接受本页面（同源）发起的写入。
            # 跨站的 fetch 会带上外站 Origin；text/plain 简单请求不触发预检，必须显式校验。
            origin = self.headers.get('Origin', '')
            host = self.headers.get('Host', '')
            if origin and origin not in (f'http://{host}', f'http://localhost:{self.server.server_port}',
                                         f'http://127.0.0.1:{self.server.server_port}'):
                self.send_response(403)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': 'Forbidden origin'}).encode('utf-8'))
                log.info(f"❌ 拒绝跨站 cookie 写入请求，Origin: {origin}")
                return

            # 保存 cookies
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
                cookies = data.get('cookies', [])
                
                # 转换为字典格式
                cookie_dict = {}
                for cookie in cookies:
                    name = cookie.get('name')
                    value = cookie.get('value')
                    if name and value:
                        cookie_dict[name] = value
                
                # 保存到文件
                with open(config.COOKIE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(cookie_dict, f, indent=2, ensure_ascii=False)
                
                # 返回成功
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {'success': True, 'message': 'Cookies saved successfully'}
                self.wfile.write(json.dumps(response).encode('utf-8'))
                
                log.info(f"✅ Cookies 已保存到 {config.COOKIE_FILE}")
                
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {'success': False, 'error': str(e)}
                self.wfile.write(json.dumps(response).encode('utf-8'))
                log.error(f"❌ 保存 cookies 失败: {e}")
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """禁用默认日志"""
        pass


class AutoLogin:
    """自动化登录助手"""
    
    def __init__(self, port=8888):
        self.port = port
        self.server = None
        self.server_thread = None
    
    def start_server(self, max_retries: int = 20):
        """启动本地服务器（端口被占用时顺延重试，最多 max_retries 次）"""
        for _ in range(max_retries):
            try:
                self.server = HTTPServer(('localhost', self.port), CookieReceiverHandler)
                self.server_thread = threading.Thread(target=self.server.serve_forever)
                self.server_thread.daemon = True
                self.server_thread.start()
                log.info(f"✅ 本地服务器已启动: http://localhost:{self.port}")
                return True
            except OSError as e:
                if e.errno == 48:  # Address already in use
                    log.info(f"⚠️  端口 {self.port} 已被占用，尝试使用其他端口...")
                    self.port += 1
                else:
                    log.error(f"❌ 启动服务器失败: {e}")
                    return False
        log.info(f"❌ 连续 {max_retries} 个端口均被占用，放弃启动")
        return False
    
    def stop_server(self):
        """停止服务器"""
        if self.server:
            self.server.shutdown()
            log.info("✅ 本地服务器已停止")
    
    def open_login_page(self):
        """打开登录助手页面"""
        url = f"http://localhost:{self.port}"
        log.info(f"🌐 正在打开浏览器: {url}")
        webbrowser.open(url)
    
    def wait_for_cookies(self, timeout=300):
        """等待 cookies 保存"""
        log.info(f"⏳ 等待用户登录并提交 cookies (最长 {timeout} 秒)...")
        log.info(f"💡 提示: 请在浏览器中完成登录并提交 cookies")
        
        cookie_file = Path(config.COOKIE_FILE)
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if cookie_file.exists():
                file_time = cookie_file.stat().st_mtime
                if file_time > start_time:
                    log.info("✅ 检测到 cookies 已更新！")
                    return True
            time.sleep(1)
        
        log.info(f"⏱️  等待超时 ({timeout} 秒)")
        return False
    
    def run(self, timeout=300):
        """运行自动化登录流程"""
        log.info("=" * 70)
        log.info("🔐 JAVDB 自动化登录助手")
        log.info("=" * 70)
        
        # 启动服务器
        if not self.start_server():
            return False
        
        # 打开浏览器
        self.open_login_page()
        
        # 等待 cookies
        success = self.wait_for_cookies(timeout)
        
        # 停止服务器
        self.stop_server()
        
        return success


def auto_login(timeout=300):
    """
    自动化登录函数
    
    Args:
        timeout: 等待超时时间（秒），默认 5 分钟
        
    Returns:
        是否成功获取 cookies
    """
    login_helper = AutoLogin()
    return login_helper.run(timeout)


if __name__ == "__main__":
    log.info("启动 JAVDB 自动化登录助手...")
    auto_login()
