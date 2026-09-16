"""Google connection command handlers."""

from .auth import (
    disconnect_user,
    get_account_service_states,
    initiate_google_connection,
    list_user_connections,
)

_SERVICE_LABELS = {
    "gmail": "Gmail (read, send, drafts, labels)",
    "calendar": "Google Calendar (view, schedule, reschedule/cancel)",
    "drive": "Google Drive (find, read, upload, share)",
    "docs": "Google Docs (read, create, edit)",
    "sheets": "Google Sheets (read, write cells/formulas, tabs)",
    "slides": "Google Slides (read, create, edit)",
}


def _capability_line(service: str, state: str, needs_consent: bool) -> str:
    label = _SERVICE_LABELS.get(service, service)
    if state == "ready":
        return f"  • **{label}:** ✅ Ready"
    if state == "not_connected":
        return f"  • **{label}:** ⚠️ Not connected"
    marker = "🔒" if needs_consent else "❌"
    return f"  • **{label}:** {marker} Additional permission required"


def handle_connect_google(telegram_user_id: int | str) -> str:
    """Generate response containing a single all-in-one Google Workspace authorization link (Gmail, Calendar, Drive)."""
    try:
        url_super = initiate_google_connection(telegram_user_id, toolkit="googlesuper")
        return (
            "🔗 **All-in-One Google Account Link (Gmail & Calendar)**\n\n"
            "Tap the link below to grant Hermes full access in a single one-time consent:\n\n"
            f"👉 {url_super}\n\n"
            "💡 *One login is all it takes — your account unlocks Gmail (read, send, drafts) "
            "and Google Calendar (view, schedule) at the same time!*"
        )
    except Exception as exc:  # noqa: BLE001 -- command boundary renders user-facing error text
        return f"❌ Failed to generate the account connection link: {str(exc)}"


def handle_connect_calendar(telegram_user_id: int | str) -> str:
    """Generate response containing the magic authorization link specifically for Google Calendar."""
    try:
        url_cal = initiate_google_connection(telegram_user_id, toolkit="googlecalendar")
        return (
            "📅 **Google Calendar Link**\n\n"
            "Tap the secure link below to connect your Calendar to Hermes:\n"
            f"{url_cal}\n\n"
            "💡 *After you sign in with the Google account you want for Calendar, "
            "Hermes will automatically enable viewing and managing your schedule!*"
        )
    except Exception as exc:  # noqa: BLE001 -- command boundary renders user-facing error text
        return f"❌ Failed to generate the Calendar connection link: {str(exc)}"


def handle_google_status(telegram_user_id: int | str) -> str:
    """Report connection status with per-service capability, not a fixed list."""
    connections = list_user_connections(telegram_user_id)
    if not connections:
        return (
            "⚠️ **Google Account Status:** DISCONNECTED\n\n"
            "No Google account is linked to Hermes yet.\n"
            "Send `/connect-google` to get a quick sign-in link!"
        )

    email_map: dict[str, list[str]] = {}
    for conn in connections:
        em = conn.get("email") or "unknown address"
        cid = conn.get("id", "")
        email_map.setdefault(em, []).append(cid)

    lines = [
        f"✅ **Google Account Status:** CONNECTED ({len(email_map)} mailbox/mailboxes)\n",
        "📧 **Linked email accounts:**",
    ]
    for idx, (em, cids) in enumerate(email_map.items(), 1):
        cids_str = ", ".join(f"`{c}`" for c in cids)
        lines.append(f"  {idx}. **`{em}`** (Session: {cids_str})")

    try:
        states = get_account_service_states(telegram_user_id)
    except Exception:  # noqa: BLE001 -- status renders degrade, not crash
        states = {}
    lines.append("\n📋 **Available services:**")
    for service in _SERVICE_LABELS:
        state = states.get(service, {}).get("state", "not_connected")
        needs_consent = any(
            row.get("reason") == "scope_missing"
            for row in states.get(service, {}).get("accounts", [])
        )
        lines.append(_capability_line(service, state, needs_consent))
    lines.extend(
        [
            f"\n*(Total connected sessions: {len(connections)})*",
            "\n💡 *You can disconnect anytime with `/disconnect-google`.*",
        ]
    )
    return "\n".join(lines)


def handle_disconnect_google(
    telegram_user_id: int | str,
    target: str = "",
) -> str:
    """Disconnect and revoke Google access for the user with interactive selection menu."""
    connections = list_user_connections(telegram_user_id)
    if not connections:
        return "⚠️ You have no Google account connected to Hermes."

    target_clean = target.strip().lower()

    # If no target specified and multiple connections exist -> present interactive selection menu
    if not target_clean and len(connections) > 1:
        lines = [
            f"📋 **You have {len(connections)} connected Google sessions:**",
        ]
        for idx, conn in enumerate(connections, 1):
            lbl = conn.get("email") or conn.get("id") or "Google Account"
            tk = conn.get("toolkit") or "Workspace"
            cid = conn.get("id", "")
            lines.append(f"  {idx}. **{lbl}** ({tk} - ID: `{cid}`)")
        lines.extend(
            [
                "\n👉 **Choose the account you want to disconnect:**",
                "• Type: `/disconnect-google 1` to remove account #1",
                "• Or type: `/disconnect-google <email_address>` to remove that email",
                "\n👉 **To disconnect ALL accounts at once:**",
                "• Type: `/disconnect-google all`",
            ]
        )
        return "\n".join(lines)

    try:
        success, disconnected = disconnect_user(
            telegram_user_id,
            app="",
            target_identifier=target_clean,
        )
        if not success:
            return "❌ Failed to disconnect the account. Please try again later."

        if target_clean and target_clean != "all":
            disc_label = (
                ", ".join(f"`{d}`" for d in disconnected)
                if disconnected
                else f"`{target.strip()}`"
            )
            remaining = [
                c.get("email") or c.get("id")
                for c in connections
                if c.get("email") not in disconnected
            ]
            rem_msg = (
                f"\n💡 *Remaining account:* {', '.join(f'`{r}`' for r in remaining)} is still active."
                if remaining
                else "\n💡 *All Google accounts have been disconnected.*"
            )
            return f"🔒 **Successfully disconnected account:** {disc_label}\n{rem_msg}"

        return (
            "🔒 **All Google accounts disconnected successfully!**\n\n"
            "All Gmail and Google Calendar authorizations have been revoked from the system. "
            "Hermes can no longer access your email or calendar unless you re-authorize via `/connect-google`."
        )
    except ValueError as exc:
        return f"❌ Invalid Google account: {exc}"
    except Exception as exc:  # noqa: BLE001 -- command boundary renders user-facing error text
        return f"❌ Failed to disconnect the account: {str(exc)}"
