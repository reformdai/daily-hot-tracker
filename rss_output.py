"""
RSS Feed 输出模块
将精选结果生成标准 RSS 2.0 格式，可部署到 GitHub Pages 供订阅。
"""
import os
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import format_datetime
from pathlib import Path
from typing import List

from fetchers.base import ContentItem


def generate_rss_feed(
    items: List[ContentItem],
    output_dir: str = "output",
    title: str = "AI 每日精选",
    description: str = "AI 领域每日精选热点，由 AI 自动筛选评分",
    link: str = "",
) -> str:
    if not items:
        return ""

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text = title
    ET.SubElement(channel, "description").text = description
    ET.SubElement(channel, "link").text = link or "https://github.com"
    ET.SubElement(channel, "language").text = "zh-CN"
    ET.SubElement(channel, "lastBuildDate").text = format_datetime(datetime.now().astimezone())
    ET.SubElement(channel, "generator").text = "daily-hot-tracker"

    for item in items:
        entry = ET.SubElement(channel, "item")

        display_title = item.ai_title or item.title
        if item.ai_category:
            display_title = f"【{item.ai_category}】{display_title}"

        ET.SubElement(entry, "title").text = display_title
        ET.SubElement(entry, "link").text = item.url
        ET.SubElement(entry, "description").text = item.ai_summary or item.description
        ET.SubElement(entry, "source").text = item.source
        ET.SubElement(entry, "guid", isPermaLink="false").text = item.id

        if item.ai_category:
            ET.SubElement(entry, "category").text = item.ai_category

        if item.published_at:
            try:
                ET.SubElement(entry, "pubDate").text = format_datetime(
                    item.published_at.astimezone()
                )
            except Exception:
                pass

    tree = ET.ElementTree(rss)
    ET.indent(tree, space="  ")
    feed_path = out / "feed.xml"
    tree.write(str(feed_path), encoding="unicode", xml_declaration=True)

    return str(feed_path)
