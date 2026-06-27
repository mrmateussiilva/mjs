import asyncio
import json
from pathlib import Path

from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

HOST = "0.0.0.0"
PORT = 8765
STATE_FILE = Path("notes_state.json")

clients = set()
state = {
    "text": "",
    "author": None,
    "updated_at": None,
}


def load_state() -> None:
    global state
    if not STATE_FILE.exists():
        save_state()
        return

    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        state = {
            "text": str(data.get("text", "")),
            "author": data.get("author"),
            "updated_at": data.get("updated_at"),
        }
    except Exception:
        state = {
            "text": "",
            "author": None,
            "updated_at": None,
        }
        save_state()


def save_state() -> None:
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def make_state_payload() -> str:
    return json.dumps(
        {
            "type": "state",
            "text": state["text"],
            "author": state["author"],
            "updated_at": state["updated_at"],
            "clients": len(clients),
        },
        ensure_ascii=False,
    )


async def broadcast_state() -> None:
    if not clients:
        return

    payload = make_state_payload()
    dead = []

    for ws in clients:
        try:
            await ws.send(payload)
        except Exception:
            dead.append(ws)

    for ws in dead:
        clients.discard(ws)


async def handler(websocket):
    clients.add(websocket)

    try:
        await websocket.send(make_state_payload())

        async for message in websocket:
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type")

            if msg_type == "get_state":
                await websocket.send(make_state_payload())
                continue

            if msg_type == "update":
                state["text"] = str(data.get("text", ""))
                state["author"] = str(data.get("author", "desconhecido"))[:60]
                state["updated_at"] = str(data.get("updated_at", ""))[:80] or None
                save_state()
                await broadcast_state()
    except ConnectionClosed:
        pass
    finally:
        clients.discard(websocket)


async def main():
    load_state()
    print(f"Servidor WebSocket em ws://{HOST}:{PORT}")
    print(f"Arquivo de estado: {STATE_FILE.resolve()}")
    async with serve(handler, HOST, PORT):
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Servidor encerrado.")
