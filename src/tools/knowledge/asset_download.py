from __future__ import annotations

from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from web import validate_public_target


class _ImageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.figure_depth = 0
        self.current = []
        self.images = []
        self.caption = False

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "figure":
            self.figure_depth += 1
            self.current = []
        elif tag == "img":
            item = {
                "source_url": values.get("src", ""),
                "alt": values.get("alt", ""),
                "caption": "",
                "width": int(values.get("width", 0) or 0),
                "height": int(values.get("height", 0) or 0),
                "in_figure": self.figure_depth > 0,
            }
            self.images.append(item)
            if self.figure_depth:
                self.current.append(item)
        elif tag == "figcaption" and self.figure_depth:
            self.caption = True

    def handle_data(self, data):
        if self.caption:
            text = " ".join(data.split())
            for item in self.current:
                item["caption"] = " ".join(filter(None, (item["caption"], text)))

    def handle_endtag(self, tag):
        if tag == "figcaption":
            self.caption = False
        elif tag == "figure":
            self.figure_depth = max(0, self.figure_depth - 1)
            self.current = []


def select_relevant_images(
    html: str,
    page_url: str,
    media_images: list[dict] | None = None,
) -> list[dict]:
    if media_images:
        candidates = [
            {
                "source_url": item.get("src") or item.get("source_url", ""),
                "alt": str(item.get("alt", "")),
                "caption": str(item.get("desc") or item.get("caption", "")),
                "width": int(item.get("width", 0) or 0),
                "height": int(item.get("height", 0) or 0),
                "in_figure": bool(item.get("desc") or item.get("caption")),
            }
            for item in media_images
        ]
    else:
        parser = _ImageParser()
        parser.feed(html)
        candidates = parser.images

    selected = []
    for candidate in candidates:
        item = dict(candidate)
        source = urljoin(page_url, item.pop("source_url"))
        label = " ".join((item["alt"] + " " + item["caption"]).lower().split())
        decorative = any(word in label for word in ("avatar", "icon", "logo", "sprite"))
        meaningful = item.pop("in_figure") and bool(item["caption"]) or bool(item["alt"] and not decorative)
        if meaningful and not decorative and item["width"] >= 100 and item["height"] >= 100:
            selected.append({"source_url": source, **item})
    return selected


def download_asset(
    image: dict,
    artifact_dir: Path,
    resolver,
    byte_limit: int,
    opener=urlopen,
) -> dict:
    source = validate_public_target(str(image.get("source_url", "")), resolver)
    request = Request(source, headers={"User-Agent": "Hermes-Crawl4AI/1.0"})
    with opener(request, timeout=30) as response:
        final = validate_public_target(response.geturl(), resolver)
        mime = str(response.headers.get("Content-Type", "")).split(";", 1)[0].lower()
        suffixes = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/svg+xml": ".svg",
            "image/webp": ".webp",
        }
        if mime not in suffixes:
            raise ValueError("website asset has unsupported image MIME type")
        declared = int(response.headers.get("Content-Length", 0) or 0)
        if declared > byte_limit:
            raise ValueError("website asset exceeds byte budget")
        chunks, total = [], 0
        while True:
            chunk = response.read(min(65536, byte_limit - total + 1))
            if not chunk:
                break
            total += len(chunk)
            if total > byte_limit:
                raise ValueError("website asset exceeds byte budget")
            chunks.append(chunk)

    content = b"".join(chunks)
    if not content:
        raise ValueError("website asset is empty")
    digest = sha256(content).hexdigest()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    path = (artifact_dir / (f"asset-{digest[:20]}{suffixes[mime]}")).resolve()
    path.write_bytes(content)
    return {
        "asset_id": f"asset-{digest[:20]}",
        "source_url": final,
        "path": str(path),
        "sha256": digest,
        "mime_type": mime,
        "byte_count": total,
        "alt": str(image.get("alt", "")),
        "caption": str(image.get("caption", "")),
        "describe_image": False,
    }
