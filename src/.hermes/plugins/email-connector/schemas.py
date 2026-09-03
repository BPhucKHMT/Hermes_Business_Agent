EMAIL_SEARCH_SCHEMA = {
    "name": "email_search",
    "description": (
        "Search accessible Gmail threads for the authenticated user using Gmail search "
        "syntax (e.g. 'from:supplier@example.com newer_than:7d'). Personal mail results "
        "in group chats will be redirected to DM."
    ),
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
    "description": (
        "Retrieve full plain-text message contents of a specific Gmail thread ID "
        "returned by email_search."
    ),
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

EMAIL_SEND_SCHEMA = {
    "name": "email_send",
    "description": "Send an outbound email directly from the user's connected Gmail account.",
    "parameters": {
        "type": "object",
        "properties": {
            "recipient": {
                "type": "string",
                "description": "Recipient email address (To)",
            },
            "subject": {
                "type": "string",
                "description": "Subject line of the email",
            },
            "body": {
                "type": "string",
                "description": "Body text or HTML content of the email",
            },
        },
        "required": ["recipient", "subject", "body"],
    },
}

EMAIL_CREATE_DRAFT_SCHEMA = {
    "name": "email_create_draft",
    "description": "Create an email draft in the user's connected Gmail account without sending it immediately.",
    "parameters": {
        "type": "object",
        "properties": {
            "recipient": {
                "type": "string",
                "description": "Recipient email address (To)",
            },
            "subject": {
                "type": "string",
                "description": "Subject line of the email",
            },
            "body": {
                "type": "string",
                "description": "Draft body text or HTML content",
            },
        },
        "required": ["recipient", "subject", "body"],
    },
}

EMAIL_REPLY_SCHEMA = {
    "name": "email_reply",
    "description": "Reply to an existing Gmail thread from the user's connected Gmail account.",
    "parameters": {
        "type": "object",
        "properties": {
            "thread_id": {
                "type": "string",
                "description": "ID of the email thread to reply to",
            },
            "body": {
                "type": "string",
                "description": "Reply body text or HTML content",
            },
        },
        "required": ["thread_id", "body"],
    },
}
