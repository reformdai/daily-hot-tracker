"""配置驱动的公开网页/JSON 列表，不执行脚本、不抓取文章全文。"""
from datetime import datetime, timezone
from itertools import zip_longest
from urllib.parse import urljoin, urlsplit, urldefrag

from bs4 import BeautifulSoup

from .base import BaseFetcher, ContentItem, get_with_retry, stable_id


def clean_text(value):
    if not isinstance(value, str):
        return ""
    soup = BeautifulSoup(value, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return " ".join(soup.get_text(" ", strip=True).split())


def parse_date(value):
    """ISO 8601 或英文列表日期；统一 naive UTC，无日期不补当前时间。"""
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        for fmt in ("%b %d, %Y", "%B %d, %Y", "%Y/%m/%d"):
            try:
                dt = datetime.strptime(value, fmt)
                break
            except ValueError:
                continue
        else:
            return None
    if dt.tzinfo:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def http_url(value, base):
    if not isinstance(value, str) or not value.strip():
        return ""
    try:
        url = urldefrag(urljoin(base, value.strip()))[0]
        parts = urlsplit(url)
        if parts.scheme in ("http", "https") and parts.hostname and not parts.username and not parts.password:
            return url
    except ValueError:
        pass
    return ""


def get_path(value, path):
    """点分路径支持字典与数组下标，空路径表示根节点。"""
    for part in path.split(".") if path else []:
        if isinstance(value, dict):
            value = value.get(part)
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            return None
    return value


class ListSourceFetcher(BaseFetcher):
    name = "List Sources"
    COMMON = {"name", "url", "category", "enabled"}
    FIELDS = set()
    REQUIRED = {"name", "url"}
    kind = "list"

    def __init__(self, sources=None):
        self.sources = sources or []

    def fetch(self, limit=20):
        if limit <= 0:
            return []
        batches = []
        for config in self.sources:
            if config.get("enabled", True) is False:
                continue
            label = f"{self.kind} {config.get('name', 'unnamed')}"
            try:
                unknown = set(config) - self.COMMON - self.FIELDS
                missing = [key for key in self.REQUIRED if not isinstance(config.get(key), str) or not config[key].strip()]
                if unknown or missing:
                    raise ValueError(f"unsupported keys {sorted(unknown)}; missing fields {sorted(missing)}")
                if not http_url(config["url"], ""):
                    raise ValueError("source url must be an absolute HTTP(S) URL")
                resp = get_with_retry(config["url"], label)
                if resp is None:
                    continue
                items = self.parse(resp, config)
                items.sort(key=lambda item: item.published_at or datetime.min, reverse=True)
                print(f"[{label}] {len(items)} valid items" + ("; check selectors/field paths if unexpected" if not items else ""))
                batches.append(items)
            except Exception as exc:
                # 不输出响应正文或异常中的请求信息。
                print(f"[{label}] failed ({type(exc).__name__})" + (f": {exc}" if isinstance(exc, ValueError) else ""))
        # 每个信源先取第一条，然后第二条，避免配置顺序吞掉后续源。
        return [item for row in zip_longest(*batches) for item in row if item is not None][:limit]

    def item(self, config, base, title, link, summary="", date=None, author=""):
        title = clean_text(title)
        url = http_url(link, base)
        if not title or not url:
            return None
        return ContentItem(
            id=stable_id(self.kind, url), title=title, url=url,
            source=config["name"], category=config.get("category", "News"),
            description=clean_text(summary)[:500], author=clean_text(author),
            published_at=parse_date(date), extra={"source_url": config["url"], "source_kind": self.kind},
        )


class WebListFetcher(ListSourceFetcher):
    """item_selector 定位条目；省略 link_selector/title_selector 时使用条目本身。"""
    kind = "web_list"
    FIELDS = {"item_selector", "link_selector", "title_selector", "summary_selector", "date_selector", "allow_url_prefixes"}
    REQUIRED = ListSourceFetcher.REQUIRED | {"item_selector"}

    def parse(self, response, config):
        soup = BeautifulSoup(response.content, "html.parser")
        base = response.url or config["url"]
        out, seen = [], set()
        for node in soup.select(config["item_selector"]):
            def select(key):
                return node.select_one(config[key]) if config.get(key) else None
            link = select("link_selector") if config.get("link_selector") else node
            title = select("title_selector") if config.get("title_selector") else node
            summary, date = select("summary_selector"), select("date_selector")
            item = self.item(config, base,
                title.get_text(" ", strip=True) if title else "",
                link.get("href", "") if link else "",
                summary.get_text(" ", strip=True) if summary else "",
                (date.get("datetime") or date.get_text(" ", strip=True)) if date else None)
            if item is None or item.url in seen or item.url.rstrip('/') == urldefrag(base)[0].rstrip('/'):
                continue
            prefixes = config.get("allow_url_prefixes", [])
            if prefixes and not any(item.url.startswith(prefix) for prefix in prefixes):
                continue
            seen.add(item.url)
            out.append(item)
        return out


class JsonListFetcher(ListSourceFetcher):
    """纯 JSON GET 接口，以点分字段路径映射；不接受 token/header 配置。"""
    kind = "json_list"
    FIELDS = {"items_path", "title_path", "url_path", "summary_path", "date_path", "author_path"}
    REQUIRED = ListSourceFetcher.REQUIRED | {"title_path", "url_path"}

    def parse(self, response, config):
        try:
            data = response.json()
        except ValueError:
            raise ValueError("response is not JSON") from None
        rows = get_path(data, config.get("items_path", ""))
        if not isinstance(rows, list):
            raise ValueError("items_path did not resolve to an array")
        out, seen = [], set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            def value(key):
                return get_path(row, config[key]) if config.get(key) else None
            item = self.item(config, response.url or config["url"], value("title_path"), value("url_path"),
                             value("summary_path"), value("date_path"), value("author_path"))
            if item and item.url not in seen:
                seen.add(item.url)
                out.append(item)
        if rows and not out:
            raise ValueError("no valid items mapped; check title_path/url_path")
        return out
