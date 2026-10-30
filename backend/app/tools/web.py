"""Public-page retrieval with DNS pinning, response limits, and no redirects."""

import ipaddress
import socket
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx
from starlette.concurrency import run_in_threadpool


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg"}:
            self.depth += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg"}:
            self.depth = max(0, self.depth - 1)

    def handle_data(self, data):
        if not self.depth and data.strip():
            self.parts.append(data.strip())


async def fetch_page(url: str):
    from backend.app.tools.registry import public_url

    public_url(url)
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("Page retrieval requires HTTPS")
    addresses = await run_in_threadpool(
        socket.getaddrinfo, parsed.hostname, 443, socket.AF_UNSPEC, socket.SOCK_STREAM
    )
    ips = {record[4][0] for record in addresses}
    if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
        raise ValueError("Page resolves to a private or reserved address")
    address = sorted(ips)[0]
    host = f"[{address}]" if ":" in address else address
    target = f"https://{host}{parsed.path or '/'}"
    if parsed.query:
        target += "?" + parsed.query
    content = bytearray()
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=15) as client:
        async with client.stream(
            "GET",
            target,
            headers={"Host": parsed.hostname, "User-Agent": "JARVIS-Research/0.2"},
            extensions={"sni_hostname": parsed.hostname},
        ) as response:
            if 300 <= response.status_code < 400:
                raise ValueError("Page redirects are blocked; provide its final HTTPS URL")
            response.raise_for_status()
            kind = response.headers.get("content-type", "")
            if not any(t in kind for t in ["text/html", "text/plain"]):
                raise ValueError("Only HTML or plain text pages can be retrieved")
            async for chunk in response.aiter_bytes():
                content.extend(chunk)
                if len(content) > 1_000_000:
                    raise ValueError("Page exceeds the 1 MB limit")
    parser = TextExtractor()
    parser.feed(content.decode("utf-8", errors="replace"))
    return {"source": url, "text": "\n".join(parser.parts)[:16000], "untrusted_data": True}
