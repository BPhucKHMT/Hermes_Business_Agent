TIKTOK_CREATOR_INFO_SCHEMA = {
    "name": "tiktok_creator_info",
    "description": "Inspect connected TikTok creator account details (nickname, username, avatar, max duration, allowed privacy settings).",
    "parameters": {
        "type": "object",
        "properties": {},
    },
}

TIKTOK_CREATE_DRAFT_POST_SCHEMA = {
    "name": "tiktok_create_draft_post",
    "description": "Stage a new TikTok video post draft (Tier 2) with caption, video file path, and privacy settings. Does NOT publish until confirmed.",
    "parameters": {
        "type": "object",
        "properties": {
            "caption": {
                "type": "string",
                "description": "Post caption and hashtags (max 2200 characters).",
            },
            "video_file_path": {
                "type": "string",
                "description": "Path to local video file (.mp4, .mov, .webm).",
            },
            "privacy_level": {
                "type": "string",
                "enum": [
                    "PUBLIC_TO_EVERYONE",
                    "MUTUAL_FOLLOW_FRIENDS",
                    "SELF_ONLY",
                    "FOLLOWER_OF_CREATOR",
                ],
                "description": "Privacy visibility setting. Default 'SELF_ONLY'.",
                "default": "SELF_ONLY",
            },
            "disable_comment": {
                "type": "boolean",
                "description": "Disable comments on this video.",
                "default": False,
            },
            "disable_duet": {
                "type": "boolean",
                "description": "Disable duet on this video.",
                "default": False,
            },
            "disable_stitch": {
                "type": "boolean",
                "description": "Disable stitch on this video.",
                "default": False,
            },
            "brand_content_toggle": {
                "type": "boolean",
                "description": "Flag as commercial / brand content.",
                "default": False,
            },
        },
        "required": ["caption", "video_file_path"],
    },
}

TIKTOK_PUBLISH_VIDEO_SCHEMA = {
    "name": "tiktok_publish_video",
    "description": "Confirm and initiate publication of a staged TikTok draft post via the Content Posting API. Returns a publish ID.",
    "parameters": {
        "type": "object",
        "properties": {
            "draft_id": {
                "type": "string",
                "description": "Draft ID returned by tiktok_create_draft_post.",
            },
        },
        "required": ["draft_id"],
    },
}

TIKTOK_POST_STATUS_SCHEMA = {
    "name": "tiktok_post_status",
    "description": "Query the processing and publication status of a submitted TikTok video post using its publish ID.",
    "parameters": {
        "type": "object",
        "properties": {
            "publish_id": {
                "type": "string",
                "description": "Publish ID returned by tiktok_publish_video.",
            },
        },
        "required": ["publish_id"],
    },
}
