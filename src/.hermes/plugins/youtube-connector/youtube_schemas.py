YOUTUBE_CHANNEL_STATUS_SCHEMA = {
    "name": "youtube_channel_status",
    "description": "Inspect connected YouTube channel status, title, custom URL, subscriber count, and video count for the authenticated user.",
    "parameters": {
        "type": "object",
        "properties": {},
    },
}

YOUTUBE_LIST_VIDEOS_SCHEMA = {
    "name": "youtube_list_videos",
    "description": "List recently published and uploaded videos on the connected YouTube channel.",
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Maximum videos to return (1 to 50). Default 10.",
                "default": 10,
            },
        },
    },
}

YOUTUBE_CREATE_DRAFT_VIDEO_SCHEMA = {
    "name": "youtube_create_draft_video",
    "description": "Stage a new YouTube video draft (Tier 2) with title, description, tags, privacy status, and file path. Does NOT upload until confirmed.",
    "parameters": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Video title (max 100 characters).",
            },
            "video_file_path": {
                "type": "string",
                "description": "Path to local video file (.mp4, .mov, .webm, etc.).",
            },
            "description": {
                "type": "string",
                "description": "Video description (max 5000 characters).",
                "default": "",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of video tags/keywords (max 30 tags).",
                "default": [],
            },
            "privacy_status": {
                "type": "string",
                "enum": ["private", "unlisted", "public"],
                "description": "Visibility level. Default 'unlisted'.",
                "default": "unlisted",
            },
            "thumbnail_file_path": {
                "type": "string",
                "description": "Optional path to custom thumbnail image.",
                "default": "",
            },
        },
        "required": ["title", "video_file_path"],
    },
}

YOUTUBE_UPLOAD_VIDEO_SCHEMA = {
    "name": "youtube_upload_video",
    "description": "Confirm and execute the upload of a staged video draft to YouTube. Returns the verified YouTube Video ID and watch URL.",
    "parameters": {
        "type": "object",
        "properties": {
            "draft_id": {
                "type": "string",
                "description": "Draft ID returned by youtube_create_draft_video.",
            },
        },
        "required": ["draft_id"],
    },
}

YOUTUBE_UPDATE_METADATA_SCHEMA = {
    "name": "youtube_update_video_metadata",
    "description": "Update the title, description, tags, or privacy status of an existing YouTube video on the connected channel.",
    "parameters": {
        "type": "object",
        "properties": {
            "video_id": {
                "type": "string",
                "description": "ID of the YouTube video to update.",
            },
            "title": {
                "type": "string",
                "description": "Updated title.",
            },
            "description": {
                "type": "string",
                "description": "Updated description.",
                "default": "",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Updated tags.",
                "default": [],
            },
            "privacy_status": {
                "type": "string",
                "enum": ["private", "unlisted", "public"],
                "description": "Updated privacy level.",
                "default": "unlisted",
            },
        },
        "required": ["video_id", "title"],
    },
}
