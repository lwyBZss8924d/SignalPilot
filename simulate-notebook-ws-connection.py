"""
Simulate a direct WebSocket connection to the notebook server (no gateway proxy).

Usage:
    python simulate-notebook-ws-connection.py

Connects directly to the notebook container on port 2718, bypassing the
gateway proxy entirely. This isolates notebook-server issues from proxy issues.
"""

import asyncio
import json
import sys
import time
from urllib.parse import urlencode

import httpx
import websockets

# ── Configuration ────────────────────────────────────────────────
NOTEBOOK_URL = "http://localhost:2718"
GATEWAY_URL = "http://localhost:3300"
PROJECT_ID = "c90eacbf-3f69-45d3-a7e9-2bff3266ede7"
BRANCH = "main"
FILE_PATH = "notebooks/intro.py"

WS_TIMEOUT = 20  # seconds to wait for kernel-ready


async def sync_project(client: httpx.AsyncClient) -> None:
    """Sync project files onto the notebook pod via gateway."""
    print("\n[1/4] Syncing project files...")
    # Sync goes through the gateway (it has the git repos)
    # First get a session for the proxy cookie
    r = await client.get(f"{GATEWAY_URL}/api/notebook-sessions")
    session = r.json()
    if not session or not session.get("id"):
        print("  No session — creating one...")
        r = await client.post(
            f"{GATEWAY_URL}/api/notebook-sessions",
            json={"project_id": PROJECT_ID, "branch": BRANCH},
        )
        session = r.json()
    session_id = session["id"]
    import re
    token = ""
    if session.get("notebook_url"):
        m = re.search(r"token=([^&]+)", session["notebook_url"])
        if m:
            token = m.group(1)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Gateway-Project-Id": PROJECT_ID,
        "X-Gateway-Branch-Id": BRANCH,
    }
    r = await client.post(
        f"{GATEWAY_URL}/notebook/{session_id}/api/project/sync-down",
        headers=headers,
        timeout=60,
    )
    print(f"  Sync: {r.status_code} — {r.text[:200]}")


async def health_check(client: httpx.AsyncClient) -> bool:
    """Check notebook server health directly."""
    print("\n[2/4] Health-checking notebook server directly...")
    try:
        r = await client.get(f"{NOTEBOOK_URL}/health")
        print(f"  Health: {r.status_code}")
        return r.status_code == 200
    except Exception as e:
        print(f"  Failed: {e}")
        return False


async def check_sessions(client: httpx.AsyncClient) -> None:
    """Check existing kernel sessions."""
    print("\n[3/4] Checking existing kernel sessions...")
    try:
        r = await client.get(f"{NOTEBOOK_URL}/api/sessions")
        sessions = r.json()
        if sessions:
            print(f"  Active sessions: {json.dumps(sessions, indent=2)}")
        else:
            print("  No active sessions")
    except Exception as e:
        print(f"  Failed: {e}")


async def connect_websocket() -> None:
    """Connect WebSocket directly to notebook server."""
    print("\n[4/4] Connecting WebSocket directly to notebook server...")

    params = {
        "session_id": "s_direct1",
        "file": FILE_PATH,
        "project": PROJECT_ID,
        "branch": BRANCH,
    }
    url = f"ws://localhost:2718/ws?{urlencode(params)}"
    print(f"  URL: {url}")

    try:
        async with websockets.connect(url, open_timeout=10, close_timeout=5) as ws:
            print("  WebSocket OPEN")
            print(f"  Waiting up to {WS_TIMEOUT}s for messages...")

            messages_received = 0
            kernel_ready_received = False
            deadline = time.time() + WS_TIMEOUT

            while time.time() < deadline:
                try:
                    raw = await asyncio.wait_for(
                        ws.recv(), timeout=max(0.1, deadline - time.time())
                    )
                    messages_received += 1

                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        print(f"  [{messages_received}] Non-JSON ({len(raw)} bytes)")
                        continue

                    op = msg.get("op") or (msg.get("data", {}).get("op"))
                    print(f"\n  [{messages_received}] op={op}")

                    if op == "kernel-ready":
                        kernel_ready_received = True
                        data = msg.get("data", msg)
                        print_kernel_ready(data)
                        deadline = time.time() + 3

                    elif op == "cell-op":
                        data = msg.get("data", msg)
                        print(f"    cell_id={data.get('cell_id', '?')} status={data.get('status', '?')}")

                    elif op == "kernel-startup-error":
                        data = msg.get("data", msg)
                        print(f"    ERROR: {data.get('error', 'unknown')[:300]}")
                        break

                    elif op == "variables":
                        data = msg.get("data", msg)
                        print(f"    {len(data.get('variables', []))} variables")

                    elif op == "alert" or op == "banner":
                        data = msg.get("data", msg)
                        print(f"    title={data.get('title')} desc={data.get('description', '')[:80]}")

                    else:
                        data_str = json.dumps(msg, default=str)
                        print(f"    {data_str[:200]}")

                except asyncio.TimeoutError:
                    break
                except websockets.exceptions.ConnectionClosedError as e:
                    print(f"\n  WebSocket CLOSED: code={e.code} reason='{e.reason}'")
                    break
                except websockets.exceptions.ConnectionClosedOK as e:
                    print(f"\n  WebSocket closed OK: code={e.code} reason='{e.reason}'")
                    break

            print(f"\n  Total messages: {messages_received}")
            if not kernel_ready_received:
                print("  WARNING: kernel-ready NOT received!")
            else:
                print("  SUCCESS: kernel-ready received!")

    except websockets.exceptions.ConnectionClosedError as e:
        print(f"  WebSocket CLOSED: code={e.code} reason='{e.reason}'")
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"  WebSocket rejected: {e}")
    except Exception as e:
        print(f"  Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


def print_kernel_ready(data: dict) -> None:
    codes = data.get("codes", [])
    names = data.get("names", [])
    cell_ids = data.get("cell_ids", [])
    configs = data.get("configs", [])
    layout = data.get("layout")
    resumed = data.get("resumed", False)
    app_config = data.get("app_config", {})
    auto_instantiated = data.get("auto_instantiated", False)

    print(f"\n  +--- KERNEL-READY ------------------------------------")
    print(f"  | Cells:            {len(codes)}")
    print(f"  | Resumed:          {resumed}")
    print(f"  | Auto-instantiated: {auto_instantiated}")
    print(f"  | Layout:           {json.dumps(layout, default=str)[:80] if layout else 'None'}")
    print(f"  | App config:       {json.dumps(app_config, default=str)[:80]}")

    if not codes:
        print(f"  |")
        print(f"  | WARNING: NO CELLS -- file may not exist or failed to parse")
        print(f"  +----------------------------------------------------")
        return

    print(f"  |")
    for i, (code, name, cid) in enumerate(zip(codes, names, cell_ids)):
        config = configs[i] if i < len(configs) else {}
        code_preview = code[:80].replace("\n", "\\n") if code else "(empty)"
        print(f"  | Cell {i}: id={cid}")
        print(f"  |   name:   {name or '(unnamed)'}")
        print(f"  |   config: {json.dumps(config, default=str)[:80]}")
        print(f"  |   code:   {code_preview}")
        if len(code) > 80:
            print(f"  |           ... ({len(code)} chars total)")
        print(f"  |")

    print(f"  +----------------------------------------------------")


async def main():
    print("=" * 60)
    print("Direct Notebook WebSocket Simulator (no proxy)")
    print("=" * 60)
    print(f"Notebook: {NOTEBOOK_URL}")
    print(f"Project:  {PROJECT_ID}")
    print(f"File:     {FILE_PATH}")

    async with httpx.AsyncClient(timeout=30) as client:
        await sync_project(client)
        healthy = await health_check(client)
        if not healthy:
            print("\nFATAL: Notebook server not healthy.")
            sys.exit(1)
        await check_sessions(client)

    await connect_websocket()

    # Also check the log file for kernel spawn info
    print("\n" + "=" * 60)
    print("Checking notebook server log file for kernel spawn details...")
    try:
        import subprocess
        result = subprocess.run(
            ["docker", "exec", "signalpilot-notebook-1", "tail", "-30",
             "/home/notebook/.cache/sp/logs/sp.log"],
            capture_output=True, text=True, timeout=5,
            env={**__import__("os").environ, "MSYS_NO_PATHCONV": "1"},
        )
        if result.stdout.strip():
            print(result.stdout[-2000:])
        else:
            print("  (log file empty or not found)")
    except Exception as e:
        print(f"  Could not read log: {e}")

    print("\n" + "=" * 60)
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
