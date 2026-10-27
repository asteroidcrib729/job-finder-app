"""Normalize public description markup without splitting inline requirements."""
import re
from html import unescape

from bs4 import BeautifulSoup


def description_text(node):
    for tag in node.find_all(["script", "style"]):
        tag.decompose()
    for tag in node.find_all("br"):
        tag.replace_with("\n")
    for tag in node.find_all(["p", "li", "div", "h1", "h2", "h3", "h4"]):
        tag.insert_before("\n")
        tag.insert_after("\n")
    return "\n".join(re.sub(r"[ \t\r\f\v]+", " ", line).strip()
        for line in node.get_text(" ").splitlines() if line.strip())


def plain_description(markup):
    for _ in range(2):
        if not re.search(r"&(?:amp;)?lt;/?(?:br|p|div|li|ul|ol|strong|b|h[1-6])(?:\s|/|&)", markup, re.I):
            break
        markup = unescape(markup)
    return description_text(BeautifulSoup(markup, "html.parser"))
