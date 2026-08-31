SOCIAL_PREPARE_SCHEMA = {
    "name": "social_prepare_facebook_post",
    "description": (
        "Prepare a Facebook personal-profile post in the approved browser and "
        "stop before the human-only Publish action."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "account_label": {"type": "string"},
            "text": {"type": "string"},
            "media_paths": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 1,
                "default": [],
            },
            "audience": {
                "type": "string",
                "enum": ["friends", "only-me"],
            },
        },
        "required": ["account_label", "text", "audience"],
        "additionalProperties": False,
    },
}

SOCIAL_STATUS_SCHEMA = {
    "name": "social_browser_status",
    "description": "Read the durable status of a Facebook preparation run.",
    "parameters": {
        "type": "object",
        "properties": {"run_id": {"type": "string"}},
        "required": ["run_id"],
        "additionalProperties": False,
    },
}

SOCIAL_VERIFY_SCHEMA = {
    "name": "social_verify_facebook_post",
    "description": (
        "After the human publishes, read back a Facebook post permalink; absence "
        "remains ready_for_human."
    ),
    "parameters": {
        "type": "object",
        "properties": {"run_id": {"type": "string"}},
        "required": ["run_id"],
        "additionalProperties": False,
    },
}
