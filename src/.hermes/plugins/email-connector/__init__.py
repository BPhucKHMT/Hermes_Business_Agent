from .gmail_tools import PersonalGmailGuard


def register(ctx):
    guard = PersonalGmailGuard()
    ctx.register_hook("pre_gateway_dispatch", guard.pre_gateway_dispatch)
    ctx.register_hook("pre_tool_call", guard.pre_tool_call)
    ctx.register_hook("on_session_finalize", guard.on_session_finalize)
    return guard
