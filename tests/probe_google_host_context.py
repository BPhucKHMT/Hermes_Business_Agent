"""Probe native Desktop command context without credentials or provider calls.

Run with the installed Hermes interpreter and --hermes-root. Exit 2 means
native command context is unavailable, not that Google authentication failed.
All native state modifications below are isolated test fixtures in a temporary
Hermes home. No installed source, real profile, or provider is modified.
"""

from argparse import ArgumentParser
import json
import os
from pathlib import Path
from queue import Queue
import socket
import sys
import tempfile


class ProbeTransport:
    def __init__(self):
        self.messages = Queue()

    def write(self, message):
        self.messages.put(message)
        return True

    def close(self):
        return None


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--hermes-root", type=Path, required=True)
    args = parser.parse_args()
    output = sys.stdout
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(args.hermes_root.resolve()))
    original_connect = socket.socket.connect

    def no_external_network(sock, address):
        if isinstance(address, tuple) and address[0] not in ("127.0.0.1", "::1"):
            raise RuntimeError("probe forbids external network connections")
        return original_connect(sock, address)

    socket.socket.connect = no_external_network
    with tempfile.TemporaryDirectory(prefix="hermes-command-context-") as temp:
        home = Path(temp) / "home"
        home.mkdir()
        os.environ["HERMES_HOME"] = str(home)
        os.environ["HERMES_ENABLE_PROJECT_PLUGINS"] = "0"
        os.environ["COMPOSIO_API_KEY"] = "probe-no-provider-key"
        for name in tuple(os.environ):
            if name.startswith("HERMES_SESSION_"):
                os.environ.pop(name)

        from gateway.session_context import (  # noqa: PLC0415 -- imports follow hermes-root path and isolated HOME bootstrap
            get_session_env,
        )
        from hermes_cli.plugins import (  # noqa: PLC0415 -- imports follow hermes-root path and isolated HOME bootstrap
            PluginContext,
            PluginManifest,
            get_plugin_manager,
        )
        from hermes_constants import (  # noqa: PLC0415 -- imports follow hermes-root path and isolated HOME bootstrap
            get_hermes_home,
        )
        from tui_gateway import (  # noqa: PLC0415 -- imports follow hermes-root path and isolated HOME bootstrap
            server,
        )
        from tui_gateway.transport import (  # noqa: PLC0415 -- imports follow hermes-root path and isolated HOME bootstrap
            current_transport,
        )

        manager = get_plugin_manager()
        # The probe owns the only plugin; discovery is covered independently.
        manager._discovered = True
        context = PluginContext(PluginManifest(name="h017-context-probe"), manager)
        transport = ProbeTransport()

        def sample_context(raw_args):
            del raw_args
            return json.dumps(
                {
                    "session_id": get_session_env("HERMES_SESSION_ID"),
                    "session_key": get_session_env("HERMES_SESSION_KEY"),
                    "source": get_session_env("HERMES_SESSION_SOURCE"),
                    "user_id": get_session_env("HERMES_SESSION_USER_ID"),
                    "profile": context.profile_name,
                    "home_is_launch_home": Path(get_hermes_home()) == home,
                    "same_transport": current_transport() is transport,
                }
            )

        registration = context.register_command("h017-context-probe", sample_context)
        rows = []
        try:
            for profile in ("audit-a", "audit-b"):
                sid = f"session-{profile}"
                profile_home = home / "profiles" / profile
                profile_home.mkdir(parents=True)
                # Seed two native session records on one Desktop transport.
                server._sessions[sid] = {
                    "session_key": sid,
                    "profile_home": str(profile_home),
                    "source": "desktop",
                    "transport": transport,
                    "cwd": str(profile_home),
                }
                for method, command in (
                    ("command.dispatch", {"name": "h017-context-probe", "arg": ""}),
                    ("slash.exec", {"command": "/h017-context-probe"}),
                ):
                    rid = f"{profile}-{method}"
                    response = server.dispatch(
                        {
                            "jsonrpc": "2.0",
                            "id": rid,
                            "method": method,
                            "params": {"session_id": sid, **command},
                        },
                        transport=transport,
                    )
                    if response is None:
                        response = transport.messages.get(timeout=30)
                    if "error" in response:
                        raise RuntimeError(json.dumps(response["error"]))
                    observed = json.loads(response["result"]["output"])
                    rows.append(
                        {
                            "method": method,
                            "requested_profile": profile,
                            "requested_session": sid,
                            "observed": observed,
                        }
                    )
        finally:
            if registration is not None:
                registration.dispose()
            server._sessions.clear()
            server._pool.shutdown(wait=True)

        missing = [
            row
            for row in rows
            if row["observed"]["session_id"] != row["requested_session"]
            or row["observed"]["profile"] != row["requested_profile"]
            or not row["observed"]["user_id"]
        ]
        json.dump(
            {
                "status": "HOST_CONTEXT_UNAVAILABLE" if missing else "context_present",
                "rows": rows,
                "note": "Context presence alone does not prove authenticated-owner provenance.",
            },
            output,
            indent=2,
        )
        output.write("\n")
        return 2 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
