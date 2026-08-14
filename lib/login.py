"""
JAVDB 自动登录模块
使用账号密码登录并获取 cookies
"""

import json
from pathlib import Path
from urllib.parse import urljoin

from curl_cffi import requests
from bs4 import BeautifulSoup

import config
from lib.logger import get_logger

log = get_logger(__name__)


class JavdbLogin:
    """
    JAVDB 自动登录器
    
    功能:
    - 使用账号密码登录
    - 获取并保存 cookies
    - 自动处理登录流程
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(config.HEADERS)
        self.base_url = f"https://{config.JAVDB['domains'][0]}"
    
    def login(self, username: str = None, password: str = None) -> bool:
        """
        登录 JAVDB
        
        注意: JAVDB 现在需要验证码，自动登录可能失败。
        建议手动在浏览器登录后导出 cookies 到 cookies.json 文件。
        
        Args:
            username: 用户名/邮箱，如果为 None 使用配置文件中的值
            password: 密码，如果为 None 使用配置文件中的值
            
        Returns:
            是否登录成功
        """
        if username is None:
            username = config.LOGIN.get('username')
        if password is None:
            password = config.LOGIN.get('password')
        
        if not username or not password:
            log.error("错误: 未配置用户名或密码")
            return False
        
        try:
            # 先确认年龄
            self._confirm_over18()
            
            # 获取登录页面
            login_page_url = f"{self.base_url}/login"
            response = self.session.get(login_page_url, timeout=config.JAVDB['timeout'])
            soup = BeautifulSoup(response.text, 'lxml')
            
            # 检查是否需要验证码
            captcha = soup.select_one('img[alt="captcha"], .captcha, #captcha, input[name="captcha"]')
            if captcha:
                log.error("警告: 登录需要验证码，自动登录失败")
                log.info("请手动在浏览器登录后，将 cookies 导出到 cookies.json 文件")
                return False
            
            # 查找登录表单
            form = soup.select_one('form[action="/user_sessions"]')
            if not form:
                log.error("错误: 未找到登录表单")
                return False
            
            token_input = form.select_one('input[name="authenticity_token"]')
            if not token_input:
                log.error("错误: 未找到 authenticity_token")
                return False
            
            authenticity_token = token_input.get('value', '')
            
            login_data = {
                'authenticity_token': authenticity_token,
                'user[email]': username,
                'user[password]': password,
                'user[remember_me]': '1',
            }
            
            # 提交登录
            login_submit_url = f"{self.base_url}/user_sessions"
            response = self.session.post(
                login_submit_url,
                data=login_data,
                timeout=config.JAVDB['timeout'],
                allow_redirects=True
            )
            
            # 检查登录结果
            soup = BeautifulSoup(response.text, 'lxml')
            
            # 检查错误信息
            error = soup.select_one('.alert-danger, .error-message, .flash-error')
            if error:
                error_text = error.get_text(strip=True)
                if '验证码' in error_text or 'captcha' in error_text.lower():
                    log.error(f"登录失败: 需要验证码")
                    log.info("请手动在浏览器登录后，将 cookies 导出到 cookies.json 文件")
                else:
                    log.error(f"登录失败: {error_text}")
                return False
            
            # 检查是否仍在登录页
            if '/login' in response.url:
                log.error("登录失败: 仍在登录页面，可能需要验证码")
                return False
            
            # 保存 cookies
            self._save_cookies()
            log.info("登录成功，cookies 已保存")
            
            return True
            
        except Exception as e:
            log.error(f"登录异常: {e}")
            return False
    
    def _confirm_over18(self):
        """确认已满18岁"""
        try:
            url = f"{self.base_url}/over18?respond=1"
            self.session.get(url, timeout=config.JAVDB['timeout'])
            return True
        except Exception as e:
            return False
    
    def _save_cookies(self):
        """保存 cookies 到文件"""
        cookies = dict(self.session.cookies)
        with open(config.COOKIE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)
    
    def load_cookies(self) -> bool:
        """
        从文件加载 cookies
        
        Returns:
            是否成功加载
        """
        cookie_path = Path(config.COOKIE_FILE)
        if cookie_path.exists():
            try:
                with open(cookie_path, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                    self.session.cookies.update(cookies)
                self._confirm_over18()
                return True
            except Exception as e:
                return False
        return False
    
    def check_login_status(self) -> bool:
        """
        检查登录状态
        
        Returns:
            是否已登录
        """
        try:
            url = f"{self.base_url}/tags"
            response = self.session.get(url, timeout=config.JAVDB['timeout'])

            # 不能用「页面含 /login 字符串」判未登录——导航/页脚正常页面也有该链接，
            # 会导致每次都重走密码登录并触发验证码。以正向信号（用户菜单）为准。
            soup = BeautifulSoup(response.text, 'lxml')
            user_menu = soup.select_one('.user-menu, .dropdown-toggle')

            return user_menu is not None
            
        except Exception as e:
            return False
    
    def ensure_login(self) -> bool:
        """
        确保已登录（自动加载 cookies 或重新登录）
        
        Returns:
            是否已登录
        """
        if self.load_cookies():
            if self.check_login_status():
                return True
        
        return self.login()


def login(username: str = None, password: str = None) -> bool:
    """
    登录 JAVDB
    
    Args:
        username: 用户名，默认使用配置文件
        password: 密码，默认使用配置文件
        
    Returns:
        是否登录成功
    """
    javdb_login = JavdbLogin()
    return javdb_login.login(username, password)


def ensure_login() -> bool:
    """
    确保已登录（自动加载 cookies 或重新登录）
    
    Returns:
        是否已登录
    """
    javdb_login = JavdbLogin()
    return javdb_login.ensure_login()
