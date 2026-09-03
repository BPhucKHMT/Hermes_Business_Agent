EMAIL_SEARCH_SCHEMA = {
    "name": "email_search",
    "description": (
        "Search accessible Gmail threads for the authenticated user using Gmail search "
        "syntax (e.g. 'from:supplier@example.com newer_than:7d' or 'in:inbox'). "
        "If the user wants to check a specific connected email account (e.g. 'baophuc1204vn@gmail.com' "
        "or 'nguyenlam.baophuc@gmail.com'), pass that address in 'account_email'."
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
            "account_email": {
                "type": "string",
                "description": (
                    "Optional email address of the specific connected mailbox to search "
                    "(e.g. 'baophuc1204vn@gmail.com' or 'nguyenlam.baophuc@gmail.com'). "
                    "If omitted, searches the default connected mailbox."
                ),
            },
        },
        "required": ["query"],
    },
}

EMAIL_GET_THREAD_SCHEMA = {
    "name": "email_get_thread",
    "description": (
        "Retrieve full plain-text message contents of a specific Gmail thread ID "
        "returned by email_search. Optionally specify account_email if known."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "thread_id": {
                "type": "string",
                "description": "Gmail thread ID to retrieve",
            },
            "account_email": {
                "type": "string",
                "description": "Optional email address of the connected mailbox holding the thread.",
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
            "account_email": {
                "type": "string",
                "description": "Optional sender email address to send from when multiple accounts are connected.",
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
            "account_email": {
                "type": "string",
                "description": "Optional account email address to create the draft in.",
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
            "account_email": {
                "type": "string",
                "description": "Optional account email address to reply from.",
            },
        },
        "required": ["thread_id", "body"],
    },
}
