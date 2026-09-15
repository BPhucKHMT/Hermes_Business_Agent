from .adapter import ZaloAdapter, ZaloAPIError, check_zalo_requirements, validate_config

__all__ = [
    "ZaloAPIError",
    "ZaloAdapter",
    "check_zalo_requirements",
    "register",
    "validate_config",
]


def register(ctx):
    """Register the official Zalo private-DM platform with Hermes."""
    ctx.register_platform(
        name="zalo",
        label="Zalo",
        adapter_factory=ZaloAdapter,
        check_fn=check_zalo_requirements,
        validate_config=validate_config,
        is_connected=validate_config,
        required_env=["ZALO_BOT_TOKEN"],
        allowed_users_env="ZALO_ALLOWED_USERS",
        allow_all_env="ZALO_ALLOW_ALL_USERS",
        max_message_length=2000,
        platform_hint=(
            "You are chatting via Zalo. Replies support Markdown through "
            "server-side parsing, including bold, italics, headings and lists. "
            "Incoming images and stickers are supplied as media; voice "
            "transcription depends on the configured STT provider. "
            "Interpret incoming media in the context of the ongoing conversation "
            "and the user's latest request. An image without a caption is not "
            "automatically a request for a description. Treat every sticker as "
            "a conversational reaction to answer, never content to describe: "
            "reply to its intent in one short natural sentence (a 'HI!' greeting "
            "gets a greeting back, a blessing gets a brief warm acknowledgment); "
            "never describe its appearance, characters, or visible text, never "
            "explain its message, and never announce that you can see it. Use "
            "any supplied visual description only to grasp intent; do not repeat it. "
            "For images, continue the current task when intent is clear; otherwise "
            "ask one short question about what the user wants. Describe or "
            "transcribe visual details only when requested or needed for the task. "
            "Do not routinely announce that you can see an image. Report a media "
            "failure only when the current attachment's evidence indicates one; "
            "do not carry an earlier attachment failure into a new message. "
            "Keep replies concise; long messages are split into 2000-character chunks."
        ),
        emoji="💬",
    )
