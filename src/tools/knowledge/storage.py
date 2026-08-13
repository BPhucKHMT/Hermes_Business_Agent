from typing import Iterable, Mapping

from contracts import validate_source_path

LAYOUT_SUFFIXES = {".pdf", ".docx", ".pptx", ".xlsx", ".html"}


def upload_source(layout_container, text_container, source_path: str, content: bytes, access_groups: Iterable[str]) -> Mapping[str, object]:
    path = validate_source_path(source_path)
    groups = sorted({group.strip() for group in access_groups if group and group.strip()})
    if not groups:
        raise ValueError("at least one access group is required")
    pipeline = "layout" if "." + path.rsplit(".", 1)[-1].lower() in LAYOUT_SUFFIXES else "text"
    container = layout_container if pipeline == "layout" else text_container
    container.upload_blob(path, content, overwrite=True, metadata={
        "source_path": path,
        "display_name": path.rsplit("/", 1)[-1],
        "access_groups": ",".join(groups),
    })
    return {"status": "uploaded", "pipeline": pipeline, "source_path": path, "access_groups": groups}


def delete_source(layout_container, text_container, source_path: str) -> Mapping[str, str]:
    path = validate_source_path(source_path)
    pipeline = "layout" if "." + path.rsplit(".", 1)[-1].lower() in LAYOUT_SUFFIXES else "text"
    container = layout_container if pipeline == "layout" else text_container
    container.delete_blob(path, delete_snapshots="include")
    return {"status": "deleted", "pipeline": pipeline, "source_path": path}
