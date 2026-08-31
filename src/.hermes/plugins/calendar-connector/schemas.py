CALENDAR_LIST_EVENTS_SCHEMA = {
    "name": "calendar_list_events",
    "description": "List upcoming Google Calendar events for the authenticated Telegram user within an optional time range.",
    "parameters": {
        "type": "object",
        "properties": {
            "time_min": {
                "type": "string",
                "description": "Start of time range in ISO 8601 format (e.g. '2026-08-31T09:00:00Z'). Defaults to now.",
            },
            "time_max": {
                "type": "string",
                "description": "End of time range in ISO 8601 format (e.g. '2026-09-07T23:59:59Z').",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum events to retrieve (1 to 50). Default 20.",
                "default": 20,
            },
            "calendar_id": {
                "type": "string",
                "description": "Calendar ID to query. Default 'primary'.",
                "default": "primary",
            },
        },
    },
}

CALENDAR_FIND_FREE_SLOTS_SCHEMA = {
    "name": "calendar_find_free_slots",
    "description": "Find available free time windows on a specific date based on working hours (09:00 - 18:00 ICT) and existing events.",
    "parameters": {
        "type": "object",
        "properties": {
            "date": {
                "type": "string",
                "description": "Date to inspect in YYYY-MM-DD format (e.g. '2026-09-01').",
            },
            "duration_minutes": {
                "type": "integer",
                "description": "Minimum slot duration in minutes. Default 30.",
                "default": 30,
            },
            "calendar_id": {
                "type": "string",
                "description": "Calendar ID to check. Default 'primary'.",
                "default": "primary",
            },
        },
        "required": ["date"],
    },
}

CALENDAR_CREATE_DRAFT_EVENT_SCHEMA = {
    "name": "calendar_create_draft_event",
    "description": "Stage a new calendar event draft (Tier 2). Does NOT commit to Google Calendar until user confirms with calendar_confirm_event.",
    "parameters": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "Title / summary of the event.",
            },
            "start_time": {
                "type": "string",
                "description": "Event start time in ISO 8601 format (e.g. '2026-09-01T10:00:00Z').",
            },
            "end_time": {
                "type": "string",
                "description": "Event end time in ISO 8601 format (e.g. '2026-09-01T11:00:00Z').",
            },
            "location": {
                "type": "string",
                "description": "Location or meeting link.",
                "default": "",
            },
            "description": {
                "type": "string",
                "description": "Event description or agenda notes.",
                "default": "",
            },
            "attendees": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of attendee email addresses.",
                "default": [],
            },
            "calendar_id": {
                "type": "string",
                "description": "Target calendar ID. Default 'primary'.",
                "default": "primary",
            },
        },
        "required": ["summary", "start_time", "end_time"],
    },
}

CALENDAR_CONFIRM_EVENT_SCHEMA = {
    "name": "calendar_confirm_event",
    "description": "Confirm and commit a previously staged calendar draft event to Google Calendar. Returns the verified Google Event ID and URL.",
    "parameters": {
        "type": "object",
        "properties": {
            "draft_id": {
                "type": "string",
                "description": "ID of the event draft returned by calendar_create_draft_event.",
            },
        },
        "required": ["draft_id"],
    },
}

CALENDAR_STATUS_SCHEMA = {
    "name": "calendar_status",
    "description": "Check Google Calendar connection status and primary calendar information for the user.",
    "parameters": {
        "type": "object",
        "properties": {},
    },
}
