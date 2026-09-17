#!/usr/bin/env python3
"""
Bilibili 评论/弹幕/通知清理工具
从 Rust 版本 (bilibili-comment-cleaning) 还原为 Python CLI 工具

功能:
  - 扫码登录 / Cookie 登录
  - 从 B 站消息中心获取被点赞/回复/@ 的评论、弹幕、通知
  - 从 aicu.cc 第三方 API 获取历史评论和弹幕
  - 批量删除评论、弹幕、通知（含级联删除关联通知）
  - 导出数据到 JSON

用法:
  pip install requests qrcode
  python bilibili_cleaner.py
"""

import json
import re
import sys
import time
import random
import logging
from dataclasses import dataclass
from typing import Optional

import requests

try:
    from curl_cffi import requests as cffi_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("bilibili_cleaner")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36 Edg/127.0.2651.86"
)

# aicu.cc API 版本路径，v3 为原版，可按需切换到 v4
AICU_API_BASE = "https://api.aicu.cc/api/v3/search"

# aicu.cc 代理地址（由 _detect_proxy 自动检测）
_aicu_proxy: str = ""


def _detect_proxy() -> str:
    """
    自动检测可用代理。优先级:
    1. 环境变量 HTTPS_PROXY / ALL_PROXY
    2. Windows 系统代理（注册表）
    """
    import os
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("ALL_PROXY") or ""
    if proxy:
        return proxy
    # Windows 系统代理
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        )
        enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
        if enabled:
            server, _ = winreg.QueryValueEx(key, "ProxyServer")
            if server:
                if not server.startswith("http"):
                    server = "http://" + server
                return server
    except Exception:
        pass
    return ""


def _build_aicu_opener():
    """构建 urllib opener，根据 _aicu_proxy 配置代理"""
    import urllib.request
    if _aicu_proxy:
        proxy_handler = urllib.request.ProxyHandler({
            "http": _aicu_proxy,
            "https": _aicu_proxy,
        })
        return urllib.request.build_opener(proxy_handler)
    return urllib.request.build_opener()


def _aicu_get_json(url: str, max_retries: int = 3) -> dict:
    """
    aicu.cc 专用 GET 请求。
    使用 urllib + 代理（若配置）直连，403 时降级 curl_cffi。
    带自动重试。
    """
    import urllib.request, urllib.error
    opener = _build_aicu_opener()

    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with opener.open(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 403 and HAS_CURL_CFFI:
                log.debug("urllib 被 403 拦截，降级为 curl_cffi")
                try:
                    s = cffi_requests.Session(impersonate="chrome")
                    if _aicu_proxy:
                        s.proxies = {"http": _aicu_proxy, "https": _aicu_proxy}
                    resp2 = s.get(url, timeout=15)
                    resp2.raise_for_status()
                    result = resp2.json()
                    return result() if callable(result) else result
                except Exception as e2:
                    if attempt < max_retries:
                        wait = attempt * 3
                        log.warning(f"curl_cffi 也失败 (第{attempt}次), {wait}秒后重试: {e2}")
                        time.sleep(wait)
                        continue
                    raise
            elif attempt < max_retries:
                wait = attempt * 3
                log.warning(f"aicu 请求失败 (第{attempt}次), {wait}秒后重试: {e}")
                time.sleep(wait)
            else:
                raise
        except Exception as e:
            if attempt < max_retries:
                wait = attempt * 3
                log.warning(f"aicu 请求失败 (第{attempt}次), {wait}秒后重试: {e}")
                time.sleep(wait)
            else:
                raise


# ============================================================
# 自定义异常
# ============================================================

class AuthExpiredError(Exception):
    """登录态过期（code=-101）"""

class RateLimitError(Exception):
    """请求被风控拦截（code=-412）"""


# ============================================================
# 数据模型
# ============================================================

@dataclass
class Comment:
    oid: int
    type: int
    content: str
    notify_id: Optional[int] = None
    tp: Optional[int] = None  # 0=点赞, 1=回复, 2=被@


@dataclass
class Danmu:
    content: str
    cid: int
    notify_id: Optional[int] = None


@dataclass
class Notify:
    content: str
    tp: int  # 0=点赞, 1=回复, 2=被@
    system_notify_api: Optional[int] = None  # 系统通知区分 API 0/1


# ============================================================
# API 服务
# ============================================================

class ApiService:
    """封装 requests.Session，统一管理 Cookie、UA、CSRF"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": UA})
        self.csrf = ""

    @classmethod
    def from_cookie(cls, cookie_str: str) -> "ApiService":
        """从 Cookie 字符串创建"""
        api = cls()
        api.session.headers.update({"Cookie": cookie_str})
        # 解析 bili_jct
        m = re.search(r"bili_jct=([^;]+)", cookie_str)
        if not m:
            raise ValueError("Cookie 中未找到 bili_jct，请确认 Cookie 完整")
        api.csrf = m.group(1)
        return api

    def set_csrf(self, csrf: str):
        self.csrf = csrf

    def get_json(self, url: str) -> dict:
        """GET 请求，返回 JSON，检查业务码"""
        resp = self.session.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        self._check_code(data)
        return data

    def post_form(self, url: str, data: dict) -> dict:
        """POST 表单请求，返回 JSON，检查业务码"""
        resp = self.session.post(url, data=data, timeout=15)
        resp.raise_for_status()
        result = resp.json()
        self._check_code(result)
        return result

    def post_json(self, url: str, json_data: dict) -> dict:
        """POST JSON 请求，返回 JSON，检查业务码"""
        resp = self.session.post(url, json=json_data, timeout=15)
        resp.raise_for_status()
        result = resp.json()
        self._check_code(result)
        return result

    @staticmethod
    def _check_code(data: dict):
        """
        检查 B 站 API 业务层返回码。
        -101: 账号未登录 / Cookie 已过期
        -412: 请求被拦截（风控限频）
        """
        code = data.get("code")
        if code is None or code == 0:
            return
        msg = data.get("message", "")
        if code == -101:
            raise AuthExpiredError(f"登录态已过期 (code={code}): {msg}")
        if code == -412:
            raise RateLimitError(f"请求被风控拦截 (code={code}): {msg}")
        if code == -404:
            # 资源不存在（如视频已删），属于预期情况
            log.debug(f"资源不存在 (code={code}): {msg}")
            return
        # 其他非零 code 仅记录警告，不中断
        log.warning(f"API 返回非零 code={code}: {msg}")

    def get_uid(self) -> int:
        """获取当前登录用户 UID"""
        data = self.get_json("https://api.bilibili.com/x/member/web/account")
        return data["data"]["mid"]


# ============================================================
# 二维码登录
# ============================================================

def qr_login(api: ApiService) -> bool:
    """
    扫码登录流程：
    1. 获取二维码 URL 和 qrcode_key
    2. 在终端显示 ASCII 二维码
    3. 轮询扫码状态直到成功/过期
    
    返回 True 表示登录成功
    """
    try:
        import qrcode
    except ImportError:
        print("请先安装 qrcode 库: pip install qrcode")
        return False

    print("\n正在获取二维码...")
    data = api.get_json(
        "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
    )
    if data.get("code") != 0:
        print(f"获取二维码失败: {data}")
        return False

    qr_url = data["data"]["url"]
    qrcode_key = data["data"]["qrcode_key"]

    # 终端打印 ASCII 二维码
    qr = qrcode.QRCode(border=1)
    qr.add_data(qr_url)
    qr.make(fit=True)
    qr.print_ascii(invert=True)
    print("\n请使用哔哩哔哩 APP 扫描上方二维码")

    # 轮询
    poll_url = (
        "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
        f"?qrcode_key={qrcode_key}"
    )
    while True:
        time.sleep(2)
        try:
            resp = api.get_json(poll_url)
        except Exception as e:
            log.warning(f"轮询出错: {e}")
            continue

        code = resp["data"]["code"]
        if code == 0:
            # 登录成功 — Session 中已自动包含 Cookie
            # 从返回的 URL 中提取 csrf
            res_url = resp["data"].get("url", "")
            m = re.search(r"bili_jct=([^&]+)", res_url)
            if m:
                api.set_csrf(m.group(1))
            else:
                # 从 Session Cookie 中获取
                jct = api.session.cookies.get("bili_jct")
                if jct:
                    api.set_csrf(jct)
                else:
                    print("警告: 无法提取 CSRF Token，后续操作可能失败")
            print("扫码登录成功!\n")
            return True
        elif code == 86101:
            print("  等待扫码...", end="\r")
        elif code == 86090:
            print("  已扫码，请在手机上确认...", end="\r")
        elif code == 86038:
            print("\n二维码已过期，正在刷新...")
            return qr_login(api)  # 递归刷新
        else:
            print(f"\n未知状态码: {code}")


# ============================================================
# OID 解析 & CID 提取
# ============================================================

_VIDEO_RE = re.compile(r"bilibili://video/(\d+)")
_CID_RE = re.compile(r"cid=(\d+)")


def parse_oid(uri: str, native_uri: str, business_id: int = 0) -> tuple[int, int]:
    """
    从通知详情解析评论的 oid 和 type
    
    返回 (oid, type)
    """
    # 防御 business_id 为 None 或非数字
    try:
        business_id = int(business_id or 0)
    except (ValueError, TypeError):
        business_id = 0

    if "t.bilibili.com" in uri:
        # 动态
        oid = int(uri.rstrip("/").split("/")[-1])
        tp = business_id if business_id != 0 else 17
        return oid, tp

    if "h.bilibili.com" in uri:
        # 带图动态
        oid = int(uri.rstrip("/").split("/")[-1])
        return oid, 11

    if "bilibili.com/read/cv" in uri:
        # 专栏
        oid = int(uri.rstrip("/").split("/")[-1].lstrip("cv"))
        return oid, 12

    if "bilibili.com/video/" in uri or "bilibili.com/bangumi/play/" in uri:
        # 视频 / 番剧
        m = _VIDEO_RE.search(native_uri)
        if m:
            return int(m.group(1)), 1

    raise ValueError(f"无法识别的 URI: {uri} / {native_uri}")


def extract_cid(native_uri: str) -> Optional[int]:
    """从 native_uri 中提取弹幕 cid"""
    m = _CID_RE.search(native_uri)
    return int(m.group(1)) if m else None


def get_cid(api: ApiService, aid: int) -> Optional[int]:
    """通过视频 aid 获取首P的 cid"""
    try:
        data = api.get_json(
            f"https://api.bilibili.com/x/player/pagelist?aid={aid}"
        )
        pages = data.get("data")
        if pages and len(pages) > 0:
            return pages[0]["cid"]
    except Exception as e:
        log.warning(f"获取 cid 失败 (aid={aid}): {e}")
    return None


# ============================================================
# 随机延迟
# ============================================================

def sleep_random(min_ms=1000, max_ms=2000):
    """随机延迟，防止触发风控"""
    time.sleep(random.randint(min_ms, max_ms) / 1000)


# ============================================================
# 数据获取 — 官方消息中心
# ============================================================

def fetch_liked(api: ApiService) -> tuple[dict, dict, dict]:
    """
    获取被点赞列表，返回 (通知dict, 评论dict, 弹幕dict)
    key 为各自的 ID
    """
    notifies: dict[int, Notify] = {}
    comments: dict[int, Comment] = {}
    danmus: dict[int, Danmu] = {}

    cursor_id = None
    cursor_time = None

    while True:
        if cursor_id is None:
            url = "https://api.bilibili.com/x/msgfeed/like?platform=web&build=0&mobi_app=web"
        else:
            url = (
                f"https://api.bilibili.com/x/msgfeed/like?platform=web&build=0&mobi_app=web"
                f"&id={cursor_id}&like_time={cursor_time}"
            )

        try:
            resp = api.get_json(url)
        except Exception as e:
            log.warning(f"获取被点赞列表出错: {e}")
            break

        total = resp.get("data", {}).get("total", {})
        items = total.get("items", [])
        cursor = total.get("cursor")

        if not items and (cursor is None or cursor.get("is_end", True)):
            break

        for item in items:
            item_id = item["id"]
            detail = item.get("item", {})
            item_type = detail.get("type", "")
            title = detail.get("title", "")
            uri = detail.get("uri", "")
            native_uri = detail.get("native_uri", "")
            business_id = detail.get("business_id", 0)
            sub_item_id = detail.get("item_id", 0)

            # 通知
            notifies[item_id] = Notify(
                content=f"{title} ({item_type})", tp=0
            )

            # 评论
            if item_type == "reply":
                rpid = sub_item_id
                try:
                    oid, otype = parse_oid(uri, native_uri, business_id)
                    comments[rpid] = Comment(
                        oid=oid, type=otype, content=title,
                        notify_id=item_id, tp=0,
                    )
                except ValueError as e:
                    log.warning(f"解析评论 OID 失败: {e}")

            # 弹幕
            if item_type == "danmu":
                cid = extract_cid(native_uri)
                if cid is not None:
                    danmus[sub_item_id] = Danmu(
                        content=title, cid=cid, notify_id=item_id,
                    )

        if cursor is None or cursor.get("is_end", True):
            break

        cursor_id = cursor.get("id")
        cursor_time = cursor.get("time")
        sleep_random()

    log.info(f"被点赞: {len(notifies)} 通知, {len(comments)} 评论, {len(danmus)} 弹幕")
    return notifies, comments, danmus


def fetch_replyed(api: ApiService) -> tuple[dict, dict]:
    """
    获取被回复列表，返回 (通知dict, 评论dict)
    """
    notifies: dict[int, Notify] = {}
    comments: dict[int, Comment] = {}

    cursor_id = None
    cursor_time = None

    while True:
        if cursor_id is None:
            url = "https://api.bilibili.com/x/msgfeed/reply?platform=web&build=0&mobi_app=web"
        else:
            url = (
                f"https://api.bilibili.com/x/msgfeed/reply?platform=web&build=0&mobi_app=web"
                f"&id={cursor_id}&reply_time={cursor_time}"
            )

        try:
            resp = api.get_json(url)
        except Exception as e:
            log.warning(f"获取被回复列表出错: {e}")
            break

        data = resp.get("data", {})
        items = data.get("items", [])
        cursor = data.get("cursor")

        if not items and (cursor is None or cursor.get("is_end", True)):
            break

        for item in items:
            item_id = item["id"]
            detail = item.get("item", {})
            item_type = detail.get("type", "")
            title = detail.get("title", "")
            uri = detail.get("uri", "")
            native_uri = detail.get("native_uri", "")
            business_id = detail.get("business_id", 0)
            target_id = detail.get("target_id", 0)
            target_reply_content = detail.get("target_reply_content")

            # 通知
            notifies[item_id] = Notify(
                content=f"{title} ({item_type})", tp=1
            )

            # 评论（使用 target_id 作为 rpid）
            if item_type == "reply":
                rpid = target_id
                try:
                    oid, otype = parse_oid(uri, native_uri, business_id)
                    content = title
                    if target_reply_content:
                        content = target_reply_content
                    comments[rpid] = Comment(
                        oid=oid, type=otype, content=content,
                        notify_id=item_id, tp=1,
                    )
                except ValueError as e:
                    log.warning(f"解析评论 OID 失败: {e}")

        if cursor is None or cursor.get("is_end", True):
            break

        cursor_id = cursor.get("id")
        cursor_time = cursor.get("time")
        sleep_random()

    log.info(f"被回复: {len(notifies)} 通知, {len(comments)} 评论")
    return notifies, comments


def fetch_ated(api: ApiService) -> dict:
    """获取被@列表，返回通知dict"""
    notifies: dict[int, Notify] = {}
    cursor_id = None
    cursor_time = None

    while True:
        if cursor_id is None:
            url = "https://api.bilibili.com/x/msgfeed/at?build=0&mobi_app=web"
        else:
            url = (
                f"https://api.bilibili.com/x/msgfeed/at?build=0&mobi_app=web"
                f"&id={cursor_id}&at_time={cursor_time}"
            )

        try:
            resp = api.get_json(url)
        except Exception as e:
            log.warning(f"获取被@列表出错: {e}")
            break

        data = resp.get("data", {})
        items = data.get("items", [])
        cursor = data.get("cursor")

        if not items and (cursor is None or cursor.get("is_end", True)):
            break

        for item in items:
            item_id = item["id"]
            detail = item.get("item", {})
            title = detail.get("title", "")
            item_type = detail.get("type", "")
            notifies[item_id] = Notify(
                content=f"{title} ({item_type})", tp=2
            )

        if cursor is None or cursor.get("is_end", True):
            break

        cursor_id = cursor.get("id")
        cursor_time = cursor.get("time")
        sleep_random()

    log.info(f"被@: {len(notifies)} 通知")
    return notifies


def fetch_system_notify(api: ApiService) -> dict:
    """获取系统通知，返回通知dict"""
    notifies: dict[int, Notify] = {}
    cursor = None
    api_type = 0

    while True:
        try:
            if cursor is None:
                # 首次获取
                if api_type == 0:
                    url = (
                        f"https://message.bilibili.com/x/sys-msg/query_user_notify"
                        f"?csrf={api.csrf}&page_size=20&build=0&mobi_app=web"
                    )
                else:
                    url = (
                        f"https://message.bilibili.com/x/sys-msg/query_unified_notify"
                        f"?csrf={api.csrf}&page_size=10&build=0&mobi_app=web"
                    )
                resp = api.get_json(url)
                data_obj = resp.get("data")

                items = []
                if data_obj and isinstance(data_obj, dict):
                    items = data_obj.get("system_notify_list") or []
                
                # API 0 为空时尝试 API 1
                if not items and api_type == 0:
                    api_type = 1
                    sleep_random()
                    continue

                if not items:
                    log.info("没有系统通知")
                    break
            else:
                # 分页获取
                url = (
                    f"https://message.bilibili.com/x/sys-msg/query_notify_list"
                    f"?csrf={api.csrf}&data_type=1&cursor={cursor}&build=0&mobi_app=web"
                )
                resp = api.get_json(url)
                items = resp.get("data") or []
                if isinstance(items, dict):
                    items = []

                if not items:
                    break

        except Exception as e:
            log.warning(f"获取系统通知出错: {e}")
            break

        for item in items:
            nid = item.get("id")
            ntype = item.get("type", 0)
            title = item.get("title", "")
            content = item.get("content", "")
            item_cursor = item.get("cursor")

            if nid is not None:
                notifies[nid] = Notify(
                    content=f"{title}\n{content}",
                    tp=ntype,
                    system_notify_api=api_type,
                )
            cursor = item_cursor

        sleep_random()

    log.info(f"系统通知: {len(notifies)} 条")
    return notifies


# ============================================================
# 数据获取 — aicu.cc 第三方 API
# ============================================================

def fetch_aicu_comments(api: ApiService, uid: int) -> dict:
    """从 aicu.cc 获取历史评论"""
    comments: dict[int, Comment] = {}

    # 获取总条数
    count_url = f"{AICU_API_BASE}/getreply?uid={uid}&pn=1&ps=0&mode=0&keyword="
    try:
        resp = _aicu_get_json(count_url)
    except Exception as e:
        log.warning(f"aicu 评论计数请求失败: {e}")
        return comments

    data = resp.get("data")
    if not data:
        log.info("aicu: 无评论数据")
        return comments

    # 解析总数 — data.cursor.all_count
    all_count = 0
    if isinstance(data, dict):
        cursor_obj = data.get("cursor")
        if cursor_obj and isinstance(cursor_obj, dict):
            all_count = cursor_obj.get("all_count", 0)
        if all_count == 0:
            all_count = data.get("all_count", 0)

    if all_count == 0:
        log.info("aicu: 评论总数为 0")
        return comments

    total_pages = (all_count + 499) // 500
    log.info(f"aicu 评论: 共 {all_count} 条, {total_pages} 页")

    for page in range(1, total_pages + 1):
        url = f"{AICU_API_BASE}/getreply?uid={uid}&pn={page}&ps=500&mode=0&keyword="
        try:
            resp = _aicu_get_json(url)
        except Exception as e:
            log.warning(f"aicu 评论第 {page} 页出错: {e}")
            break

        data = resp.get("data", {})
        replies = data.get("replies") or []

        for r in replies:
            rpid = _to_int(r.get("rpid"))
            if rpid is None:
                continue

            # 实际结构: replies[].dyn.oid (字符串), replies[].dyn.type (int)
            dyn_obj = r.get("dyn", r)
            oid = _to_int(dyn_obj.get("oid", r.get("oid")))
            rtype = dyn_obj.get("type", r.get("type", 1))
            message = r.get("message", "")

            if oid is not None:
                comments[rpid] = Comment(oid=oid, type=int(rtype), content=message)

        print(f"  aicu 评论: {page}/{total_pages} 页, 已获取 {len(comments)} 条", end="\r")
        sleep_random(2000, 4000)

    print()
    log.info(f"aicu 评论: 共获取 {len(comments)} 条")
    return comments


def fetch_aicu_danmus(api: ApiService, uid: int) -> dict:
    """从 aicu.cc 获取历史弹幕"""
    danmus: dict[int, Danmu] = {}

    # 获取总条数
    count_url = f"{AICU_API_BASE}/getvideodm?uid={uid}&pn=1&ps=0&mode=0&keyword="
    try:
        resp = _aicu_get_json(count_url)
    except Exception as e:
        log.warning(f"aicu 弹幕计数请求失败: {e}")
        return danmus

    data = resp.get("data")
    if not data:
        log.info("aicu: 无弹幕数据")
        return danmus

    all_count = 0
    if isinstance(data, dict):
        cursor_obj = data.get("cursor")
        if cursor_obj and isinstance(cursor_obj, dict):
            all_count = cursor_obj.get("all_count", 0)
        if all_count == 0:
            all_count = data.get("all_count", 0)

    if all_count == 0:
        log.info("aicu: 弹幕总数为 0")
        return danmus

    total_pages = (all_count + 499) // 500
    log.info(f"aicu 弹幕: 共 {all_count} 条, {total_pages} 页")

    for page in range(1, total_pages + 1):
        url = f"{AICU_API_BASE}/getvideodm?uid={uid}&pn={page}&ps=500&mode=0&keyword="
        try:
            resp = _aicu_get_json(url)
        except Exception as e:
            log.warning(f"aicu 弹幕第 {page} 页出错: {e}")
            break

        data = resp.get("data", {})
        # 兼容 videodmlist 和 danmus 两种字段名
        dm_list = data.get("videodmlist") or data.get("danmus") or []

        for dm in dm_list:
            dmid = _to_int(dm.get("id", dm.get("dmid")))
            if dmid is None:
                continue

            oid = _to_int(dm.get("oid"))
            content = dm.get("content", "")

            # 需要通过 aid 获取 cid
            if oid:
                cid = get_cid(api, oid)
                if cid is not None:
                    danmus[dmid] = Danmu(content=content, cid=cid)
                else:
                    log.warning(f"无法获取 cid (oid={oid}), 跳过弹幕 {dmid}")

        print(f"  aicu 弹幕: {page}/{total_pages} 页, 已获取 {len(danmus)} 条", end="\r")
        sleep_random(2000, 4000)

    print()
    log.info(f"aicu 弹幕: 共获取 {len(danmus)} 条")
    return danmus


def _to_int(val) -> Optional[int]:
    """安全转换为 int"""
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


# ============================================================
# 删除操作
# ============================================================

def delete_comment(api: ApiService, rpid: int, comment: Comment) -> bool:
    """
    删除单条评论
    type==11 时 csrf 放 query param
    其他情况 csrf 放 form data
    """
    try:
        if comment.type == 11:
            data = {
                "oid": str(comment.oid),
                "type": str(comment.type),
                "rpid": str(rpid),
            }
            url = f"https://api.bilibili.com/x/v2/reply/del?csrf={api.csrf}"
        else:
            data = {
                "oid": str(comment.oid),
                "type": str(comment.type),
                "rpid": str(rpid),
                "csrf": api.csrf,
            }
            url = "https://api.bilibili.com/x/v2/reply/del"

        api.post_form(url, data)

        # 级联删除关联通知
        if comment.notify_id is not None and comment.tp is not None:
            delete_notify(api, comment.notify_id, Notify("", comment.tp))
        return True
    except (AuthExpiredError, RateLimitError):
        raise
    except Exception as e:
        log.error(f"删除评论异常 (rpid={rpid}): {e}")
        return False


def delete_danmu(api: ApiService, dmid: int, danmu: Danmu) -> bool:
    """删除单条弹幕"""
    try:
        data = {
            "dmid": str(dmid),
            "cid": str(danmu.cid),
            "type": "1",
            "csrf": api.csrf,
        }
        api.post_form("https://api.bilibili.com/x/msgfeed/del", data)

        # 级联删除关联的点赞通知
        if danmu.notify_id is not None:
            delete_notify(api, danmu.notify_id, Notify("", 0))
        return True
    except (AuthExpiredError, RateLimitError):
        raise
    except Exception as e:
        log.error(f"删除弹幕异常 (dmid={dmid}): {e}")
        return False


def delete_notify(api: ApiService, nid: int, notify: Notify) -> bool:
    """删除单条通知"""
    try:
        if notify.system_notify_api is not None:
            # 系统通知
            csrf = api.csrf
            if notify.system_notify_api == 0:
                json_data = {
                    "csrf": csrf, "ids": [nid], "station_ids": [],
                    "type": notify.tp, "build": 8140300, "mobi_app": "android",
                }
            else:
                json_data = {
                    "csrf": csrf, "ids": [], "station_ids": [nid],
                    "type": notify.tp, "build": 8140300, "mobi_app": "android",
                }
            url = (
                f"https://message.bilibili.com/x/sys-msg/del_notify_list"
                f"?build=8140300&mobi_app=android&csrf={csrf}"
            )
            resp = api.post_json(url, json_data)
        else:
            # 普通通知
            data = {
                "tp": str(notify.tp),
                "id": str(nid),
                "build": "0",
                "mobi_app": "web",
                "csrf_token": api.csrf,
                "csrf": api.csrf,
            }
            api.post_form("https://api.bilibili.com/x/msgfeed/del", data)

        return True
    except (AuthExpiredError, RateLimitError):
        raise
    except Exception as e:
        log.error(f"删除通知异常 (id={nid}): {e}")
        return False


def batch_delete(items: dict, delete_fn, label: str, sleep_seconds: float = 2.0,
                 skip_confirm: bool = False):
    """
    批量删除通用函数
    
    items: {id: obj} 字典
    delete_fn: 接受 (id, obj) 的删除函数，返回 bool
    label: 显示名称
    skip_confirm: 为 True 时跳过二次确认
    """
    if not items:
        print(f"没有需要删除的{label}")
        return

    total = len(items)
    if not skip_confirm:
        confirm = input(f"确认删除 {total} 条{label}？此操作不可逆 [y/N]: ").strip().lower()
        if confirm != "y":
            print("已取消")
            return

    success = 0
    failed = 0
    start_time = time.time()

    print(f"\n开始删除 {total} 条{label}...")
    ids = list(items.keys())

    for i, item_id in enumerate(ids, 1):
        obj = items[item_id]
        try:
            ok = delete_fn(item_id, obj)
        except AuthExpiredError as e:
            print(f"\n\n登录态已过期，终止删除: {e}")
            print(f"已完成: 成功 {success}, 失败 {failed}, 剩余 {total - i + 1}")
            return
        except RateLimitError:
            print(f"\n触发风控限频，等待 30 秒后重试...")
            time.sleep(30)
            try:
                ok = delete_fn(item_id, obj)
            except (AuthExpiredError, RateLimitError) as e:
                print(f"\n重试仍失败，终止删除: {e}")
                print(f"已完成: 成功 {success}, 失败 {failed}, 剩余 {total - i + 1}")
                return

        if ok:
            success += 1
            del items[item_id]
        else:
            failed += 1

        # 预估剩余时间
        elapsed = time.time() - start_time
        avg = elapsed / i
        remaining = avg * (total - i)
        eta_min, eta_sec = divmod(int(remaining), 60)
        eta_str = f"{eta_min:02d}:{eta_sec:02d}"

        print(f"  进度: {i}/{total} (成功:{success} 失败:{failed}) 预计剩余 {eta_str}", end="\r")

        if i < total:
            time.sleep(sleep_seconds)

    elapsed_total = time.time() - start_time
    print(f"\n{label}删除完成: 成功 {success}, 失败 {failed}, 耗时 {elapsed_total:.1f}s")


# ============================================================
# 数据导出
# ============================================================

def export_data(comments: dict, danmus: dict, notifies: dict, filepath: str):
    """将数据导出为 JSON 文件"""
    export = {
        "comments": {
            str(k): {
                "rpid": k, "oid": v.oid, "type": v.type, "content": v.content,
            }
            for k, v in comments.items()
        },
        "danmus": {
            str(k): {
                "dmid": k, "cid": v.cid, "content": v.content,
            }
            for k, v in danmus.items()
        },
        "notifies": {
            str(k): {
                "id": k, "tp": v.tp, "content": v.content,
            }
            for k, v in notifies.items()
        },
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(export, f, ensure_ascii=False, indent=2)
    print(f"数据已导出到: {filepath}")


# ============================================================
# CLI 美化辅助
# ============================================================

def _enable_win_ansi() -> bool:
    """在 Windows 上启用 ANSI 转义码支持（PowerShell/cmd 需要）"""
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        # STD_OUTPUT_HANDLE = -11
        handle = kernel32.GetStdHandle(-11)
        # 获取当前模式
        mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)
        return True
    except Exception:
        return False


def _supports_color() -> bool:
    """检测终端是否支持 ANSI 颜色"""
    import os
    if os.environ.get("NO_COLOR"):
        return False
    if sys.platform == "win32":
        return _enable_win_ansi()
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


class _Style:
    """ANSI 颜色/样式封装"""
    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    def _wrap(self, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.enabled else text

    def bold(self, t):    return self._wrap("1", t)
    def dim(self, t):     return self._wrap("2", t)
    def green(self, t):   return self._wrap("32", t)
    def yellow(self, t):  return self._wrap("33", t)
    def cyan(self, t):    return self._wrap("36", t)
    def red(self, t):     return self._wrap("31", t)
    def magenta(self, t): return self._wrap("35", t)

    def ok(self, t):      return self.green(f"{_SYM['ok']} {t}")
    def warn(self, t):    return self.yellow(f"{_SYM['warn']} {t}")
    def err(self, t):     return self.red(f"{_SYM['err']} {t}")


S = _Style(_supports_color())

# 检测终端是否支持 Unicode 字符，GBK 终端不支持
_USE_UNICODE = (getattr(sys.stdout, "encoding", "") or "").lower().replace("-", "") in (
    "utf8", "utf16", "utf32", "utf_8",
)

# 框线字符
if _USE_UNICODE:
    _BOX = {"tl": "┌", "tr": "┐", "bl": "└", "br": "┘", "h": "─", "v": "│", "lm": "├", "rm": "┤"}
    _SYM = {"ok": "✓", "warn": "!", "err": "✗"}
else:
    _BOX = {"tl": "+", "tr": "+", "bl": "+", "br": "+", "h": "-", "v": "|", "lm": "+", "rm": "+"}
    _SYM = {"ok": "[OK]", "warn": "[!]", "err": "[X]"}

VERSION = "1.0.0"


def _banner():
    h = _BOX["h"] * 41
    print()
    print(S.cyan(f"  {_BOX['tl']}{h}{_BOX['tr']}"))
    print(S.cyan(f"  {_BOX['v']}") + S.bold("   Bilibili 评论/弹幕/通知 清理工具      ") + S.cyan(_BOX['v']))
    print(S.cyan(f"  {_BOX['v']}") + S.dim(f"   v{VERSION}  Python CLI Edition            ") + S.cyan(_BOX['v']))
    print(S.cyan(f"  {_BOX['bl']}{h}{_BOX['br']}"))
    print()


def _section(title: str):
    d = _BOX["h"] * 3
    print(f"\n{S.bold(S.cyan(d + ' ' + title + ' ' + d))}")


def _step(n: int, total: int, text: str):
    tag = S.dim(f"[{n}/{total}]")
    print(f"  {tag} {text}")


def _summary_box(comments: int, danmus: int, notifies: int):
    v = _BOX["v"]
    h = _BOX["h"] * 30
    def _row(label, count):
        num = str(count).rjust(6)
        return S.cyan(f"  {v}") + f"  {label}  {S.bold(num)} 条             " + S.cyan(v)
    print()
    print(S.cyan(f"  {_BOX['tl']}{h}{_BOX['tr']}"))
    print(S.cyan(f"  {v}") + S.bold("  数据汇总                    ") + S.cyan(v))
    print(S.cyan(f"  {_BOX['lm']}{h}{_BOX['rm']}"))
    print(_row("评论", comments))
    print(_row("弹幕", danmus))
    print(_row("通知", notifies))
    print(S.cyan(f"  {_BOX['bl']}{h}{_BOX['br']}"))


# ============================================================
# 主程序 CLI
# ============================================================

def main():
    _banner()

    # === 登录 ===
    _section("登录")
    api = ApiService()

    print(f"  {S.bold('1.')} 扫码登录")
    print(f"  {S.bold('2.')} Cookie 登录")
    choice = input(f"  请选择 {S.dim('[1/2]')}: ").strip()

    if choice == "1":
        if not qr_login(api):
            print(f"  {S.err('登录失败')}")
            return
    elif choice == "2":
        print(f"\n  {S.bold('获取 Cookie 步骤:')}")
        print(f"  {S.dim('1.')} 用浏览器打开并登录 bilibili.com")
        print(f"  {S.dim('2.')} 按 F12 打开开发者工具 → 「网络/Network」标签")
        print(f"  {S.dim('3.')} 访问 https://api.bilibili.com/x/member/web/account")
        print(f"  {S.dim('4.')} 点击该请求 → 「请求标头」→ 找到 Cookie 字段")
        print(f"  {S.dim('5.')} 复制完整的 Cookie 值（需含 bili_jct 和 SESSDATA）")
        print()
        print(f"  {S.dim('示例:')} SESSDATA=abc123%2C1234567890%2Cxxxxx*xx; bili_jct=0a1b2c3d4e5f; ...")
        ck = input(f"  请粘贴 Cookie{S.dim('>')} ").strip()
        if not ck:
            print(f"  {S.err('Cookie 不能为空')}")
            return
        try:
            api = ApiService.from_cookie(ck)
        except ValueError as e:
            print(f"  {S.err(str(e))}")
            return
        print(f"  {S.ok('Cookie 登录成功')}")
    else:
        print(f"  {S.err('无效选择')}")
        return

    # 验证登录状态
    try:
        uid = api.get_uid()
        print(f"  {S.ok(f'UID: {uid}')}")
    except Exception as e:
        print(f"  {S.err(f'登录验证失败: {e}')}")
        return

    # === 数据源选择 ===
    ans = input(f"\n  启用 aicu.cc 数据源？{S.dim('(获取更多历史评论)')} [Y/n]: ").strip().lower()
    use_aicu = ans != "n"

    step_total = 6 if use_aicu else 4
    _section("获取数据")

    _step(1, step_total, "被点赞通知")
    liked_n, liked_c, liked_d = fetch_liked(api)
    all_notifies: dict[int, Notify] = dict(liked_n)
    all_comments: dict[int, Comment] = dict(liked_c)
    all_danmus: dict[int, Danmu] = dict(liked_d)

    _step(2, step_total, "被回复通知")
    replyed_n, replyed_c = fetch_replyed(api)
    all_notifies.update(replyed_n)
    all_comments.update(replyed_c)

    _step(3, step_total, "被@通知")
    ated_n = fetch_ated(api)
    all_notifies.update(ated_n)

    _step(4, step_total, "系统通知")
    sys_n = fetch_system_notify(api)
    all_notifies.update(sys_n)

    if use_aicu:
        global _aicu_proxy
        _aicu_proxy = _detect_proxy()
        if _aicu_proxy:
            log.info(f"aicu.cc 使用代理: {_aicu_proxy}")
        else:
            log.info("aicu.cc 直连模式（未检测到代理）")

        _step(5, step_total, "aicu.cc 历史评论")
        aicu_c = fetch_aicu_comments(api, uid)
        all_comments.update(aicu_c)

        _step(6, step_total, "aicu.cc 历史弹幕")
        aicu_d = fetch_aicu_danmus(api, uid)
        all_danmus.update(aicu_d)

    # === 汇总 ===
    _summary_box(len(all_comments), len(all_danmus), len(all_notifies))

    # === 交互式操作菜单 ===
    while True:
        _section("操作菜单")
        c_count = S.bold(str(len(all_comments)))
        d_count = S.bold(str(len(all_danmus)))
        n_count = S.bold(str(len(all_notifies)))
        print(f"  {S.bold('1.')} 删除所有评论 ({c_count} 条)")
        print(f"  {S.bold('2.')} 删除所有弹幕 ({d_count} 条)")
        print(f"  {S.bold('3.')} 删除所有通知 ({n_count} 条)")
        print(f"  {S.bold('4.')} 删除全部（评论+弹幕+通知）")
        print(f"  {S.bold('5.')} 导出数据到 JSON")
        print(f"  {S.bold('0.')} 退出")
        op = input(f"  请选择{S.dim('>')}: ").strip()

        if op in ("1", "2", "3", "4"):
            try:
                delay = float(input(f"  删除间隔 {S.dim('(秒, 默认2)')}: ").strip() or "2")
            except ValueError:
                delay = 2.0

            if op == "1":
                batch_delete(
                    all_comments,
                    lambda rid, c: delete_comment(api, rid, c),
                    "评论", delay,
                )
            elif op == "2":
                batch_delete(
                    all_danmus,
                    lambda did, d: delete_danmu(api, did, d),
                    "弹幕", delay,
                )
            elif op == "3":
                batch_delete(
                    all_notifies,
                    lambda nid, n: delete_notify(api, nid, n),
                    "通知", delay,
                )
            elif op == "4":
                batch_delete(
                    all_comments,
                    lambda rid, c: delete_comment(api, rid, c),
                    "评论", delay,
                )
                batch_delete(
                    all_danmus,
                    lambda did, d: delete_danmu(api, did, d),
                    "弹幕", delay,
                )
                batch_delete(
                    all_notifies,
                    lambda nid, n: delete_notify(api, nid, n),
                    "通知", delay,
                )
        elif op == "5":
            path = input(f"  导出路径 {S.dim('(默认 bilibili_data.json)')}: ").strip()
            if not path:
                path = "bilibili_data.json"
            export_data(all_comments, all_danmus, all_notifies, path)
        elif op in ("0", "q", "Q"):
            print(f"\n  {S.dim('再见！')}\n")
            break
        else:
            print(f"  {S.warn('无效选择')}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n  {S.dim('已中断，再见！')}\n")
        sys.exit(0)
    except EOFError:
        print(f"\n\n  {S.dim('输入结束，退出')}\n")
        sys.exit(0)
