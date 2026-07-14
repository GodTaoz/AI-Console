from __future__ import annotations

import argparse
import os
import secrets
from pathlib import Path

import uvicorn

from qingluo_console.runtime_bridge.app import create_bridge_app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-runtime-bridge", description="Run the capability-limited local agent runtime bridge")
    parser.add_argument("--socket", default=os.getenv("QINGLUO_AGENT_BRIDGE_SOCKET", str(Path.home() / ".local/state/ai-console/runtime-bridge.sock")))
    parser.add_argument("--token-file", default=os.getenv("QINGLUO_AGENT_BRIDGE_TOKEN_FILE", str(Path.home() / ".local/state/ai-console/token")))
    return parser


def main() -> None:
    args = build_parser().parse_args()
    socket_path = Path(args.socket).expanduser()
    token_path = Path(args.token_file).expanduser()
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    if token_path.exists():
        token = token_path.read_text(encoding="utf-8").strip()
    else:
        token = secrets.token_urlsafe(48)
        token_path.write_text(token + "\n", encoding="utf-8")
        token_path.chmod(0o600)
    socket_path.unlink(missing_ok=True)
    uvicorn.run(create_bridge_app(token=token), uds=str(socket_path), log_level="info")


if __name__ == "__main__":
    main()
