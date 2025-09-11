import re
from bs4 import BeautifulSoup

def clean_html(raw_html: str, max_len: int = 80000) -> str:
    soup = BeautifulSoup(raw_html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    cleaned = soup.get_text(separator="\n")
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned[:max_len]