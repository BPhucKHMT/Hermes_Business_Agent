from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Mapping, Optional
from urllib.parse import quote

from contracts import validate_source_path

LAYOUT_SUFFIXES = {".pdf", ".docx", ".pptx", ".xlsx", ".html"}
WEB_ASSET_SUFFIXES = {".png", ".jpg", ".jpeg", ".svg", ".webp"}


def _groups(access_groups: Iterable[str]) -> list[str]:
    groups = sorted({group.strip() for group in access_groups if group and group.strip()})
    if not groups: raise ValueError("at least one access group is required")
    return groups


def _metadata(values: Mapping[str, object]) -> dict[str, str]:
    return {str(key): quote(str(value), safe="-._~:/[]\"") for key, value in values.items()}


def upload_source(layout_container, text_container, source_path: str, content: bytes, access_groups: Iterable[str], workspace: Optional[str] = None) -> Mapping[str, object]:
    path = validate_source_path(source_path); groups = _groups(access_groups)
    pipeline = "layout" if "." + path.rsplit(".", 1)[-1].lower() in LAYOUT_SUFFIXES else "text"
    container = layout_container if pipeline == "layout" else text_container
    meta = {"source_path": path, "display_name": path.rsplit("/", 1)[-1], "access_groups": json.dumps(groups, separators=(",", ":"))}
    if workspace:
        meta["workspace"] = workspace.strip().lower()
    container.upload_blob(path, content, overwrite=True, metadata=meta)
    return {"status": "uploaded", "pipeline": pipeline, "source_path": path, "access_groups": groups, "workspace": workspace}


def delete_source(layout_container, text_container, source_path: str) -> Mapping[str, str]:
    path = validate_source_path(source_path)
    pipeline = "layout" if "." + path.rsplit(".", 1)[-1].lower() in LAYOUT_SUFFIXES else "text"
    (layout_container if pipeline == "layout" else text_container).delete_blob(path, delete_snapshots="include")
    return {"status": "deleted", "pipeline": pipeline, "source_path": path}


def upload_website_capture(text_container, image_container, capture: dict, access_groups: Iterable[str]) -> dict:
    required = ("website_id", "page_id", "generation", "canonical_url", "content_hash")
    if any(not str(capture.get(name, "")).strip() for name in required): raise ValueError("website capture identity is incomplete")
    groups = _groups(access_groups); website_id, page_id, generation = (str(capture[name]) for name in required[:3])
    prefix = "websites/%s/%s" % (website_id, generation); source_path = "%s/pages/%s.md" % (prefix, page_id)
    title = str(capture.get("title") or capture["canonical_url"])
    metadata = _metadata({"website_id": website_id, "page_id": page_id, "generation": generation, "source_url": str(capture["canonical_url"]), "source_path": source_path, "display_name": title, "content_hash": str(capture["content_hash"]), "evidence_type": "page_text", "access_groups": json.dumps(groups, separators=(",", ":"))})
    body = ("# %s\n\n%s\n" % (title, capture.get("rendered_text", ""))).encode("utf-8")
    text_container.upload_blob(source_path, body, overwrite=True, metadata=metadata)
    uploaded, failures = [source_path], []
    if image_container is None:
        # Image indexer disabled (HERMES_IMAGE_INDEXER=false) — skip asset uploads.
        return {"status": "uploaded", "website_id": website_id, "generation": generation, "uploaded": uploaded, "failures": failures}
    for asset in capture.get("assets", []):
        try:
            path = Path(str(asset.get("path", ""))); suffix = path.suffix.lower()
            if suffix not in WEB_ASSET_SUFFIXES or not path.is_absolute(): raise ValueError("website asset must be an absolute PNG/JPEG/SVG/WebP path")
            asset_id = str(asset.get("asset_id") or asset.get("id") or "").strip()
            if not asset_id: raise ValueError("website asset id is required")
            blob_path = "%s/assets/%s%s" % (prefix, asset_id, suffix)
            asset_metadata = dict(metadata, **_metadata({
                "source_path": blob_path, "asset_id": asset_id,
                "evidence_type": "image_description" if asset.get("describe_image") else "image_ocr",
                "describe_image": "true" if asset.get("describe_image") else "false",
                "asset_source_url": asset.get("source_url", ""), "asset_sha256": asset.get("sha256", ""),
                "asset_mime_type": asset.get("mime_type", ""), "asset_alt": asset.get("alt", ""),
                "asset_caption": asset.get("caption", ""),
            }))
            image_container.upload_blob(blob_path, path.read_bytes(), overwrite=True, metadata=asset_metadata); uploaded.append(blob_path)
        except (OSError, ValueError) as error:
            failures.append({"asset_id": asset.get("asset_id") or asset.get("id"), "reason": str(error)})
    return {"status": "partial" if failures else "uploaded", "website_id": website_id, "generation": generation, "uploaded": uploaded, "failures": failures}


def delete_website_capture(text_container, image_container, website_id: str, generation: str | None = None) -> dict:
    site = website_id.strip()
    if not site or "/" in site or "\\" in site or site in {".", ".."}: raise ValueError("invalid website id")
    prefix = "websites/%s/" % site
    if generation is not None:
        version = generation.strip()
        if not version or "/" in version or "\\" in version or version in {".", ".."}: raise ValueError("invalid website generation")
        prefix += version + "/"
    deleted, failures = [], []
    for container in (text_container, image_container):
        for blob in container.list_blobs(name_starts_with=prefix):
            name = blob.name if hasattr(blob, "name") else blob["name"]
            try: container.delete_blob(name, delete_snapshots="include"); deleted.append(name)
            except Exception as error: failures.append({"source_path": name, "reason": str(error)})
    return {"status": "partial" if failures else "deleted", "website_id": site, "generation": generation, "deleted": deleted, "failures": failures}
