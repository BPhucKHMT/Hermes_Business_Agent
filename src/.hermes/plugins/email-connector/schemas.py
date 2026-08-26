from typing import Any, Dict

EMAIL_SEARCH_SCHEMA = {
    "name": "email_search",
    "description": "Search accessible Gmail threads for the authenticated user using Gmail search syntax (e.g. 'from:supplier@example.com newer_than:7d'). Personal mail results in group chats will be redirected to DM.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Gmail search query string",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum threads to retrieve (1 to 20)",
                "default": 10,
            },
        },
        "required": ["query"],
    },
}

EMAIL_GET_THREAD_SCHEMA = {
    "name": "email_get_thread",
    "description": "Retrieve full plain-text message contents of a specific Gmail thread ID returned by email_search.",
    "parameters": {
        "type": "object",
        "properties": {
            "thread_id": {
                "type": "string",
                "description": "Gmail thread ID to retrieve",
            },
        },
        "required": ["thread_id"],
    },
}

EMAIL_CONNECTION_STATUS_SCHEMA = {
    "name": "email_connection_status",
    "description": "Check the status of connected Gmail mailboxes accessible to the user.",
    "parameters": {
        "type": "object",
        "properties": {},
    },
}
