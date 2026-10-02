"""
正文补抓：给送入 AI 的候选补充原文摘录，让摘要基于更多事实而不是只看标题。

- GitHub 仓库 / Hugging Face 模型：读 README 原文（比页面更干净）
- 普通网页：读 meta 描述 + <article>/<main> 里的段落文字（不执行 JavaScript）
- 可选 Jina Reader 兜底：页面需要浏览器渲染时使用（JINA_READER_FALLBACK=true）
- X、Reddit、YouTube 等无法直接读取的站点跳过

只在描述不足时补抓，单条失败不影响其他条目；补抓结果放进 item.extra["body"]，不改原始描述。
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup

from fetchers.base import ContentItem

TIMEOUT = (5, 12)
MAX_BYTES = 3 * 1024 * 1024
MIN_BODY_CHARS = 120
USER_AGENT = "Mozilla/5.0 (compatible; daily-hot-tracker/1.0; +https://github.com/reformdai/daily-hot-tracker)"
SKIP_HOSTS = (
    "x.com", "twitter.com", "reddit.com", "youtube.com", "youtu.be",
    "news.ycombinator.com", "linkedin.com", "facebook.com", "instagram.com", "mp.weixin.qq.com",
)
# 已自带摘要的来源，不再补抓
SKIP_SOURCES = ("ArXiv", "Hugging Face Papers")


def _host(url: str) -> str:
    try:
        host = (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def _get(url: str, headers: Optional[dict] = None) -> Optional[Tuple[bytes, str]]:
    """单次请求，限制体积，返回 (内容, Content-Type)；补抓是锦上添花，不重试。"""
    try:
        with requests.get(url, headers={"User-Agent": USER_AGENT, **(headers or {})},
                          timeout=TIMEOUT, stream=True) as resp:
            if not resp.ok:
                return None
            chunks, size = [], 0
            for chunk in resp.iter_content(64 * 1024):
                chunks.append(chunk)
                size += len(chunk)
                if size > MAX_BYTES:
                    break
            return b"".join(chunks), resp.headers.get("Content-Type", "")
    except requests.RequestException:
        return None


def _get_text(url: str, headers: Optional[dict] = None) -> str:
    got = _get(url, headers)
    return got[0].decode("utf-8", "replace") if got else ""


def markdown_to_text(md: str) -> str:
    """README → 纯文本：去 front matter、HTML、图片/徽章、代码块，保留段落文字。"""
    md = re.sub(r"\A---\n.*?\n---\n", "", md, flags=re.S)
    md = re.sub(r"```.*?```", " ", md, flags=re.S)
    md = re.sub(r"<!--.*?-->", " ", md, flags=re.S)
    md = BeautifulSoup(md, "html.parser").get_text(" ")
    md = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", md)
    md = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", md)
    lines = []
    for line in md.splitlines():
        line = re.sub(r"^[#>*\-+|\s]+", "", line).strip()
        line = re.sub(r"[`*_|]+", "", line)
        if len(line) >= 20 and not re.fullmatch(r"[\W\d_]+", line):
            lines.append(line)
    return " ".join(" ".join(lines).split())


def html_to_text(html: bytes | str) -> Tuple[str, str]:
    """返回 (meta 描述, 正文段落)。"""
    soup = BeautifulSoup(html, "html.parser")
    meta = ""
    for attrs in ({"property": "og:description"}, {"name": "description"}, {"name": "twitter:description"}):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content", "").strip():
            meta = " ".join(tag["content"].split())
            break
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "aside", "form", "svg", "figure"]):
        tag.decompose()
    root = soup.find("article") or soup.find("main") or soup.body or soup
    paragraphs = []
    for p in root.find_all(["p", "li"]):
        text = " ".join(p.get_text(" ", strip=True).split())
        if len(text) >= 40:
            paragraphs.append(text)
    return meta, " ".join(paragraphs)


def _github_readme(url: str) -> str:
    segs = [s for s in urlsplit(url).path.split("/") if s]
    if len(segs) < 2:
        return ""
    owner, repo = segs[0], segs[1]
    for name in ("README.md", "readme.md", "README.rst", "README"):
        text = _get_text(f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{name}")
        if text:
            return markdown_to_text(text)
    return ""


def _hf_readme(url: str) -> str:
    segs = [s for s in urlsplit(url).path.split("/") if s]
    if len(segs) < 2 or segs[0] in ("papers", "blog", "spaces", "datasets", "docs", "learn"):
        return ""
    return markdown_to_text(_get_text(f"https://huggingface.co/{segs[0]}/{segs[1]}/raw/main/README.md"))


def _jina(url: str, api_key: str) -> str:
    headers = {"Accept": "text/plain", "X-Return-Format": "markdown"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    text = _get_text(f"https://r.jina.ai/{url}", headers=headers)
    if "\nMarkdown Content:\n" in text:
        text = text.split("\nMarkdown Content:\n", 1)[1]
    return markdown_to_text(text)


def extract_body(url: str, jina_fallback: bool = False, jina_key: str = "") -> Tuple[str, str]:
    """返回 (正文摘录, 方式)；读不到返回 ("", 原因)。"""
    host = _host(url)
    if not host:
        return "", "invalid-url"
    if any(host == h or host.endswith("." + h) for h in SKIP_HOSTS):
        return "", "skipped-host"
    if host == "github.com":
        text = _github_readme(url)
        return (text, "readme") if len(text) >= MIN_BODY_CHARS else ("", "no-readme")
    if host == "huggingface.co":
        text = _hf_readme(url)
        if len(text) >= MIN_BODY_CHARS:
            return text, "readme"

    got = _get(url)
    if got is not None and "html" in got[1].lower():
        meta, body = html_to_text(got[0])
        text = body if len(body) >= MIN_BODY_CHARS else " ".join(x for x in (meta, body) if x)
        if len(text) >= MIN_BODY_CHARS:
            return text, "html"
        if meta and not jina_fallback:
            return meta, "meta"
    if jina_fallback:
        text = _jina(url, jina_key)
        if len(text) >= MIN_BODY_CHARS:
            return text, "jina"
    return "", "unreadable"


def enrich_items(
    items: List[ContentItem],
    min_description: int = 280,
    max_chars: int = 1500,
    workers: int = 8,
    jina_fallback: bool = False,
    jina_key: str = "",
) -> Dict[str, int]:
    """并发补抓描述不足的条目，返回各方式的计数。"""
    targets = [
        item for item in items
        if len(item.description or "") < min_description
        and item.source not in SKIP_SOURCES
        and not (item.extra or {}).get("body")
    ]
    stats: Dict[str, int] = {}
    if not targets:
        return stats

    def work(item: ContentItem):
        try:
            return item, extract_body(item.url, jina_fallback, jina_key)
        except Exception as exc:  # 单条失败不影响其他条目
            return item, ("", f"error-{type(exc).__name__}")

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for item, (text, via) in pool.map(work, targets):
            stats[via] = stats.get(via, 0) + 1
            if text:
                item.extra = item.extra or {}
                item.extra["body"] = text[:max_chars]
                item.extra["body_via"] = via
    return stats
