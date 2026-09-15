EMAIL_SEARCH_SCHEMA = {
    "name": "email_search",
    "description": (
        "Search accessible Gmail threads for the authenticated user using Gmail search "
        "syntax (e.g. 'from:supplier@example.com newer_than:7d' or 'in:inbox'). "
        "If the user names a connected account (full address or unique prefix), pass it "
        "in 'account_email'. With exactly one connected mailbox, run the search "
        "immediately without asking which account. Only ask which mailbox to use when "
        "several accounts are connected and the user has not named one."
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
                    "Optional connected mailbox to search. Accepts a full address "
                    "(e.g. 'work@company.com'), a unique local-part prefix such as "
                    "'work', or a 1-based index from the connected list. "
                    "If omitted, searches the default connected mailbox. Ambiguous "
                    "or unknown prefixes fail closed; the tool never guesses."
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
        "returned by email_search. Optionally specify account_email if known; "
        "with one connected mailbox, pass nothing and run immediately."
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
                "description": (
                    "Optional sender address when multiple accounts are connected; "
                    "with one connected mailbox, omit it and send immediately."
                ),
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
                "description": (
                    "Optional target account when multiple accounts are connected; "
                    "with one connected mailbox, omit it and run immediately."
                ),
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
                "description": (
                    "Optional sender address when multiple accounts are connected; "
                    "with one connected mailbox, omit it and run immediately."
                ),
            },
        },
        "required": ["thread_id", "body"],
    },
}
