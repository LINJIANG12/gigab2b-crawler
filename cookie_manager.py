import os
import json
import sqlite3
import shutil
import ctypes
from ctypes import wintypes
import requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from config import COOKIE_FILE, COOKIE_TXT_FILE, DEFAULT_HEADERS, BASE_URL, SEARCH_URL

CF_UNICODETEXT = 13

class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ('cbData', wintypes.DWORD),
        ('pbData', ctypes.POINTER(ctypes.c_byte))
    ]

def decrypt_dpapi(cipher_text: bytes) -> bytes:
    """使用 Windows DPAPI 解密主密钥"""
    blob_in = DATA_BLOB(len(cipher_text), ctypes.cast(ctypes.create_string_buffer(cipher_text), ctypes.POINTER(ctypes.c_byte)))
    blob_out = DATA_BLOB()
    if ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        data = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)
        return data
    return None

def decrypt_cookie_value(enc_val: bytes, aes_key: bytes) -> str:
    """解密 Edge 加密的单个 Cookie 值"""
    try:
        if enc_val.startswith(b'v10') or enc_val.startswith(b'v11'):
            nonce = enc_val[3:15]
            ciphertext = enc_val[15:]
            aes_gcm = AESGCM(aes_key)
            return aes_gcm.decrypt(nonce, ciphertext, None).decode('utf-8', errors='ignore')
        else:
            decrypted = decrypt_dpapi(enc_val)
            if decrypted:
                return decrypted.decode('utf-8', errors='ignore')
    except Exception:
        pass
    return ""

def extract_cookies_from_edge() -> dict:
    """从本地 Edge 浏览器的 User Data 自动提取解密 gigab2b.com 的 Cookie"""
    edge_data = os.path.expandvars(r'%LOCALAPPDATA%\Microsoft\Edge\User Data')
    local_state_path = os.path.join(edge_data, 'Local State')
    if not os.path.exists(local_state_path):
        raise FileNotFoundError("未找到 Edge Local State 文件")

    with open(local_state_path, 'r', encoding='utf-8') as f:
        local_state = json.load(f)

    import base64
    encrypted_key = base64.b64decode(local_state['os_crypt']['encrypted_key'])
    aes_key = decrypt_dpapi(encrypted_key[5:])
    if not aes_key:
        raise ValueError("DPAPI 解密 Edge Master Key 失败")

    profiles = ['Default'] + [d for d in os.listdir(edge_data) if d.startswith('Profile ')]
    extracted_cookies = {}

    for prof in profiles:
        cookie_db = os.path.join(edge_data, prof, 'Network', 'Cookies')
        if not os.path.exists(cookie_db):
            cookie_db = os.path.join(edge_data, prof, 'Cookies')
        if not os.path.exists(cookie_db):
            continue

        temp_db = os.path.join(os.path.dirname(__file__), f'temp_{prof}_cookies.db')
        try:
            shutil.copy2(cookie_db, temp_db)
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute("SELECT host_key, name, encrypted_value, value FROM cookies WHERE host_key LIKE '%gigab2b%'")
            rows = cursor.fetchall()
            for host, name, enc_val, val in rows:
                if enc_val:
                    dec_val = decrypt_cookie_value(enc_val, aes_key)
                    if dec_val:
                        extracted_cookies[name] = dec_val
                elif val:
                    extracted_cookies[name] = val
            conn.close()
        except PermissionError:
            raise PermissionError("Edge 浏览器当前正在运行并锁定了 Cookie 文件。请临时关闭 Edge 浏览器 3 秒钟后再执行自动提取，或者在 Edge 按 F12 复制 document.cookie。")
        except Exception as e:
            continue
        finally:
            if os.path.exists(temp_db):
                try:
                    os.remove(temp_db)
                except:
                    pass

    return extracted_cookies

def get_clipboard_text() -> str:
    """读取 Windows 剪贴板文本"""
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE

    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL

    if not user32.OpenClipboard(None):
        return ""
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return ""
        try:
            return ctypes.c_wchar_p(ptr).value or ""
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()

def parse_raw_cookie_string(raw_cookie: str) -> dict:
    """将键值对 Cookie 字符串（例如 `a=1; b=2`）解析为字典"""
    cookie_dict = {}
    items = raw_cookie.strip().split(';')
    for item in items:
        item = item.strip()
        if not item or item.startswith('#'):
            continue
        if '=' in item:
            k, v = item.split('=', 1)
            cookie_dict[k.strip()] = v.strip()
    return cookie_dict

def load_cookies() -> dict:
    """从本地文件加载保存的 Cookie"""
    if os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict) and data:
                    return data
        except Exception:
            pass

    if os.path.exists(COOKIE_TXT_FILE):
        try:
            with open(COOKIE_TXT_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content and not content.startswith('#'):
                    parsed = parse_raw_cookie_string(content)
                    if parsed:
                        return parsed
        except Exception:
            pass

    return {}

def save_cookies(cookies: dict):
    """保存 Cookie 到本地 json 和 txt 文件"""
    with open(COOKIE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)

    cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
    with open(COOKIE_TXT_FILE, 'w', encoding='utf-8') as f:
        f.write(cookie_str)

def get_authenticated_session(cookies: dict = None) -> requests.Session:
    """创建一个带有请求头和 Cookie 的 Session 实例"""
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    if not cookies:
        cookies = load_cookies()
    if cookies:
        requests.utils.add_dict_to_cookiejar(session.cookies, cookies)
    return session

def check_login_status(session: requests.Session) -> tuple[bool, str]:
    """
    测试当前 Session 的登录态是否有效
    返回 (is_logged_in, message)
    """
    try:
        resp = session.get(SEARCH_URL, timeout=15, allow_redirects=True)
        final_url = resp.url
        if "safe/captcha" in final_url:
            return False, "请求触发了验证码拦截 (safe/captcha)，需要提供已登录 Edge 的 Cookie 凭据。"
        if "account/login" in final_url:
            return False, "请求被重定向至登录页面，登录态已失效。"
        if resp.status_code == 200:
            return True, "登录态有效，可以正常访问全站商品与批发价格。"
        return False, f"请求返回异常状态码: {resp.status_code}"
    except Exception as e:
        return False, f"网络连接异常: {e}"
