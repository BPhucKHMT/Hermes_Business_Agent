from pathlib import Path
import json
from string import Template
from typing import Mapping

from azure.search.documents.indexes.models import SearchIndex, SearchIndexer, SearchIndexerDataSourceConnection, SearchIndexerSkillset

RESOURCE_DIR = Path(__file__).with_name("azure_resources")


def _definition(name: str, config: Mapping[str, str]):
    text = Template((RESOURCE_DIR / (name + ".json")).read_text(encoding="utf-8")).substitute(config)
    value = json.loads(text)
    if name == "index":
        for field in value["fields"]:
            if field.get("name") == "content_vector":
                field["dimensions"] = int(field["dimensions"])
        return SearchIndex.from_dict(value)
    if name.endswith("datasource"):
        return SearchIndexerDataSourceConnection.from_dict(value)
    if name.endswith("skillset"):
        return SearchIndexerSkillset.from_dict(value)
    return SearchIndexer.from_dict(value)


def provision(clients, config: Mapping[str, str]) -> Mapping[str, object]:
    for container in (clients.layout_container, clients.text_container):
        try:
            container.create_container()
        except Exception as error:
            if getattr(error, "error_code", None) != "ContainerAlreadyExists":
                raise
    clients.indexes.create_or_update_index(_definition("index", config))
    for name in ("layout-datasource", "text-datasource"):
        clients.indexers.create_or_update_data_source_connection(_definition(name, config))
    for name in ("layout-skillset", "text-skillset"):
        clients.indexers.create_or_update_skillset(_definition(name, config))
    for name in ("layout-indexer", "text-indexer"):
        clients.indexers.create_or_update_indexer(_definition(name, config))
    return {"status": "provisioned", "index": config["AZURE_SEARCH_INDEX"]}
