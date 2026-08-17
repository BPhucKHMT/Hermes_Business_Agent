from dataclasses import dataclass
import os
from typing import Mapping, Optional

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient, SearchIndexerClient
from azure.storage.blob import BlobServiceClient

REQUIRED_ENV = (
    "AZURE_STORAGE_CONNECTION_STRING", "AZURE_STORAGE_LAYOUT_CONTAINER", "AZURE_STORAGE_TEXT_CONTAINER",
    "AZURE_STORAGE_IMAGE_CONTAINER", "AZURE_SEARCH_ENDPOINT", "AZURE_SEARCH_ADMIN_KEY", "AZURE_SEARCH_QUERY_KEY", "AZURE_SEARCH_INDEX",
    "AZURE_SEARCH_LAYOUT_INDEXER", "AZURE_SEARCH_TEXT_INDEXER", "AZURE_SEARCH_IMAGE_INDEXER", "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "AZURE_OPENAI_EMBEDDING_MODEL", "AZURE_OPENAI_EMBEDDING_DIMENSIONS",
)
OPTIONAL_ENV = ("AZURE_OPENAI_MULTIMODAL_DEPLOYMENT",)


@dataclass(frozen=True)
class AzureClients:
    layout_container: object
    text_container: object
    image_container: object
    indexes: SearchIndexClient
    indexers: SearchIndexerClient
    search: SearchClient


def load_config(environ: Optional[Mapping[str, str]] = None) -> Mapping[str, str]:
    source = os.environ if environ is None else environ
    missing = [name for name in REQUIRED_ENV if not source.get(name, "").strip()]
    if missing:
        raise ValueError("missing Azure configuration: " + ", ".join(missing))
    config = {name: source[name].strip() for name in REQUIRED_ENV}
    config.update({name: source.get(name, "").strip() for name in OPTIONAL_ENV})
    for name in ("AZURE_SEARCH_ENDPOINT", "AZURE_OPENAI_ENDPOINT"):
        if not config[name].startswith("https://"):
            raise ValueError(name + " must use https")
    try:
        dimensions = int(config["AZURE_OPENAI_EMBEDDING_DIMENSIONS"])
    except ValueError:
        raise ValueError("AZURE_OPENAI_EMBEDDING_DIMENSIONS must be an integer")
    if dimensions < 1:
        raise ValueError("AZURE_OPENAI_EMBEDDING_DIMENSIONS must be positive")
    return config


def create_clients(config: Mapping[str, str]) -> AzureClients:
    blobs = BlobServiceClient.from_connection_string(config["AZURE_STORAGE_CONNECTION_STRING"])
    endpoint = config["AZURE_SEARCH_ENDPOINT"].rstrip("/")
    admin = AzureKeyCredential(config["AZURE_SEARCH_ADMIN_KEY"])
    return AzureClients(
        layout_container=blobs.get_container_client(config["AZURE_STORAGE_LAYOUT_CONTAINER"]),
        text_container=blobs.get_container_client(config["AZURE_STORAGE_TEXT_CONTAINER"]),
        image_container=blobs.get_container_client(config["AZURE_STORAGE_IMAGE_CONTAINER"]),
        indexes=SearchIndexClient(endpoint, admin),
        indexers=SearchIndexerClient(endpoint, admin),
        search=SearchClient(endpoint, config["AZURE_SEARCH_INDEX"], AzureKeyCredential(config["AZURE_SEARCH_QUERY_KEY"])),
    )
