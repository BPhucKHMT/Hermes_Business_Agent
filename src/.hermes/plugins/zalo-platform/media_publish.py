"""Publish local images to Azure Blob Storage with short-lived SAS URLs.

The Zalo Bot Platform ``sendPhoto`` API only accepts public HTTP(S) image
URLs, so locally generated images must be exposed through a URL that Zalo's
servers can fetch. This module uploads an image to a dedicated container and
returns a read-only SAS URL that expires after :data:`SAS_EXPIRY_MINUTES`.

Configuration (runtime environment):

- ``AZURE_STORAGE_CONNECTION_STRING``: existing storage account credential.
- ``ZALO_MEDIA_CONTAINER``: container for outbound bot media
  (default ``hermes-zalo-media``; created on first use).
- ``ZALO_MEDIA_SAS_MINUTES``: SAS lifetime override (default 60 minutes).
"""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime, timedelta
import logging
import mimetypes
import os
from pathlib import Path

try:
    from azure.storage.blob import (
        BlobSasPermissions,
        BlobServiceClient,
        ContentSettings,
        generate_blob_sas,
    )
except ImportError:  # pragma: no cover - optional at import time
    BlobServiceClient = None
    generate_blob_sas = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

SAS_EXPIRY_MINUTES = 60
_ALLOWED_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif"})
_MAX_IMAGE_BYTES = 20 * 1024 * 1024


class PhotoPublishError(RuntimeError):
    """Raised when a local image cannot be published for Zalo delivery."""


def _container_name() -> str:
    return (
        os.environ.get("ZALO_MEDIA_CONTAINER", "hermes-zalo-media").strip()
        or "hermes-zalo-media"
    )


def _sas_expiry_minutes() -> int:
    raw = os.environ.get("ZALO_MEDIA_SAS_MINUTES", "").strip()
    try:
        value = int(raw) if raw else SAS_EXPIRY_MINUTES
    except ValueError:
        return SAS_EXPIRY_MINUTES
    return value if value > 0 else SAS_EXPIRY_MINUTES


def _content_type(path: Path) -> str:
    guessed = mimetypes.guess_type(path.name)[0]
    return (
        guessed
        if guessed and guessed.startswith("image/")
        else "application/octet-stream"
    )


def validate_local_image(path: str | Path) -> Path:
    """Return the resolved path when it is a supported local image."""
    image_path = Path(path).resolve()
    if image_path.suffix.lower() not in _ALLOWED_SUFFIXES:
        raise PhotoPublishError(
            f"unsupported image type: {image_path.suffix or '<none>'}"
        )
    if not image_path.is_file():
        raise PhotoPublishError("image file does not exist")
    if image_path.stat().st_size > _MAX_IMAGE_BYTES:
        raise PhotoPublishError("image exceeds the 20 MiB upload cap")
    return image_path


def publish_image(path: str | Path) -> str:
    """Upload a local image and return a short-lived read-only SAS URL."""
    if BlobServiceClient is None:
        raise PhotoPublishError("azure-storage-blob is not installed")
    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "").strip()
    if not connection_string:
        raise PhotoPublishError("AZURE_STORAGE_CONNECTION_STRING is not configured")

    image_path = validate_local_image(path)
    blob_name = f"zalo-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}-{os.getpid()}{image_path.suffix.lower()}"

    service = BlobServiceClient.from_connection_string(connection_string)
    try:
        container = service.get_container_client(_container_name())
        try:
            container.create_container()
        except Exception as error:
            if (
                "ContainerAlreadyExists" not in type(error).__name__
                and "already exists" not in str(error).lower()
            ):
                raise
        with image_path.open("rb") as image_file:
            container.upload_blob(
                name=blob_name,
                data=image_file,
                overwrite=False,
                content_settings=ContentSettings(
                    content_type=_content_type(image_path)
                ),
            )
        account = service.account_name
    finally:
        with contextlib.suppress(Exception):
            service.close()

    assert generate_blob_sas is not None  # guarded by BlobServiceClient check
    sas = generate_blob_sas(
        account_name=account,
        container_name=_container_name(),
        blob_name=blob_name,
        account_key=_account_key(connection_string),
        permission=BlobSasPermissions(read=True),
        expiry=datetime.now(UTC) + timedelta(minutes=_sas_expiry_minutes()),
    )
    url = (
        f"https://{account}.blob.core.windows.net/{_container_name()}/{blob_name}?{sas}"
    )
    logger.info(
        "[zalo] published %s (%d bytes) for photo delivery",
        blob_name,
        image_path.stat().st_size,
    )
    return url


def _account_key(connection_string: str) -> str:
    for part in connection_string.split(";"):
        if part.strip().lower().startswith("accountkey="):
            return part.split("=", 1)[1]
    raise PhotoPublishError("connection string has no AccountKey for SAS signing")
