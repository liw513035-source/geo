import ipaddress
import socket
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

import truststore

truststore.inject_into_ssl()

from app.errors import AppError

MAX_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 5
REDIRECTS = {301, 302, 303, 307, 308}


@dataclass
class FetchResult:
    url: str
    status: int
    html: str
    truncated: bool


class ResponseLike:
    def __init__(self, status: int, headers: dict[str, str], body: bytes = b""):
        self.status = status
        self.headers = {key.lower(): value for key, value in headers.items()}
        self.body = body

    def get(self, key: str, default: str = "") -> str:
        return self.headers.get(key.lower(), default)


def assert_public_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"}:
        raise AppError("INVALID_URL", "只支持 http 或 https 地址")
    if parts.username or parts.password:
        raise AppError("INVALID_URL", "地址不能包含用户名或密码")
    host = parts.hostname
    if not host:
        raise AppError("INVALID_URL", "地址缺少主机名")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise AppError("FETCH_FAILED", "目标不可达") from exc
    if not infos:
        raise AppError("FETCH_FAILED", "目标不可达")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not _is_public(ip):
            raise AppError("FORBIDDEN_TARGET", "只处理公开可访问的页面")


# 部分本机 DNS 会把公网域名解析到 198.18.0.0/15，再由本地代理转发出去。
_FAKE_IP = ipaddress.ip_network("198.18.0.0/15")


def _is_public(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv4Address) and ip in _FAKE_IP:
        return True
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified:
        return False
    if isinstance(ip, ipaddress.IPv4Address) and ip in ipaddress.ip_network("169.254.0.0/16"):
        return False
    return True


def fetch(url: str, opener=None) -> FetchResult:
    current = url
    redirects = 0
    open_url = opener or _open
    while True:
        assert_public_url(current)
        try:
            response = open_url(current)
        except TimeoutError as exc:
            raise AppError("FETCH_FAILED", "抓取超时") from exc
        except (URLError, OSError) as exc:
            raise AppError("FETCH_FAILED", "目标不可达") from exc
        except AppError:
            raise
        if response.status in REDIRECTS:
            redirects += 1
            location = response.get("location")
            if redirects > MAX_REDIRECTS or not location:
                raise AppError("FETCH_FAILED", "重定向次数过多" if location else "目标不可达")
            current = urljoin(current, location)
            continue
        content_type = response.get("content-type")
        if "html" not in content_type.lower():
            raise AppError("FETCH_FAILED", "目标不是 HTML 页面")
        if len(response.body) > MAX_BYTES:
            raise AppError("FETCH_FAILED", "页面过大")
        text = response.body.decode("utf-8", errors="replace")
        return FetchResult(url=current, status=response.status, html=text, truncated=False)


def _open(url: str) -> ResponseLike:
    request = Request(url, headers={"User-Agent": "VertiGEO/0.1"})
    try:
        with urlopen(request, timeout=15) as response:
            body = response.read(MAX_BYTES + 1)
            headers = {key: value for key, value in response.headers.items()}
            return ResponseLike(response.status, headers, body)
    except HTTPError as exc:
        body = exc.read(MAX_BYTES + 1)
        headers = {key: value for key, value in exc.headers.items()} if exc.headers else {}
        return ResponseLike(exc.code, headers, body)
