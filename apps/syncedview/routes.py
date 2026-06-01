import asyncio
from dataclasses import dataclass
from pathlib import Path
from time import time
from typing import Dict, List, Literal
import json

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket, WebSocketDisconnect


@dataclass
class YoutubeWatching:
    id: str
    type: Literal["youtube"] = "youtube"


type RoomWatching = YoutubeWatching


@dataclass
class Room:
    name: str
    watching: RoomWatching
    time: TimeState


@dataclass
class TimeState:
    paused: bool
    base_time: float
    """Seconds into the video as a base."""
    started_at: float
    """Time this state was started, in seconds since Unix epoch."""

    @property
    def time(self) -> float:
        if self.paused:
            return self.base_time
        time_passed = time() - self.started_at
        return self.base_time + time_passed


rooms: List[Room] = []
websockets: Dict[str, List[WebSocket]] = {}


def start_download(data_dir: Path, video_id: str, quality: str):
    async def task():
        await asyncio.create_subprocess_exec(
            "yt-dlp",
            "-f",
            f"b[height<={quality}]",
            "-o",
            str(data_dir / video_id),
            "--",
            video_id,
        )

    def is_already_downloaded():
        for file in data_dir.iterdir():
            if file.name.startswith(video_id):
                return True
        return False

    if not is_already_downloaded():
        asyncio.create_task(task())


def room_watching_to_dict(watching: RoomWatching) -> Dict[str, any]:
    dict: Dict[str, any] = {"type": watching.type}
    if watching.type == "youtube":
        dict["videoId"] = watching.id
    return dict


def serialize_room_state(room: Room) -> str:
    dict = {
        "time": room.time.time,
        "paused": room.time.paused,
        "watching": room_watching_to_dict(room.watching),
    }
    return json.dumps(dict)


def start(render, data_dir: Path):
    async def get_room(req: Request):
        room_name = req.path_params.get("name")
        room = None
        for room2 in rooms:
            if room2.name == room_name:
                room = room2
        if room is None:
            return HTMLResponse(f"error!\nunknown room: {room_name}")
        room_dict = {
            "name": room.name,
            "watching": room_watching_to_dict(room.watching),
        }
        return render("room.html", room=room, room_dict=room_dict)

    async def list_rooms(req):
        html = ""
        for room in rooms:
            html = (
                html
                + f'<li><a href="./rooms/{room.name}">{room.name} - watching: {room.watching.id if room.watching.type == "youtube" else "idk"}</a></li>\n'
            )
        return HTMLResponse(html)

    async def create_yt_room(req: Request):
        room_name = req.query_params.get("name")
        video_id = req.query_params.get("videoId")
        quality = req.query_params.get("quality")
        if room_name is None:
            return JSONResponse({"ok": False, "err": "no room name provided"})
        if video_id is None:
            return JSONResponse({"ok": False, "err": "no video id provided"})
        if quality is None:
            return JSONResponse({"ok": False, "err": "no max quality provided"})

        start_download(data_dir, video_id, quality)

        room = Room(
            name=room_name,
            watching=YoutubeWatching(id=video_id),
            time=TimeState(base_time=0, paused=True, started_at=time()),
        )
        rooms.append(room)
        return JSONResponse({"ok": True})

    async def get_room_video_path(req: Request):
        room_name = req.query_params.get("name")
        if room_name is None:
            return JSONResponse({"ok": False, "err": "room name not provided"})
        room = None
        for room2 in rooms:
            if room_name == room2.name:
                room = room2
        if room is None:
            return JSONResponse({"ok": False, "err": f"no room with name {room_name}"})
        if room.watching.type == "youtube":
            for file in data_dir.iterdir():
                if file.name.startswith(room.watching.id):
                    return JSONResponse(
                        {"ok": True, "path": f"/syncedview/static_yt/{file.name}"}
                    )
            return JSONResponse({"ok": False, "err": "no file for this youtube id"})
        return JSONResponse({"ok": False, "err": "failed"})

    async def room_ws(ws: WebSocket):
        room_name = ws.path_params.get("name")
        if room_name is None:
            await ws.close()
            return

        room = None
        for room2 in rooms:
            if room_name == room2.name:
                room = room2
        if room is None:
            await ws.close()
            return

        await ws.accept()

        async def send_state(ws: WebSocket):
            await ws.send_text(f"state {serialize_room_state(room)}")

        await send_state(ws)

        room_ws: List[WebSocket] | None = websockets.get(room_name)
        if room_ws is None:
            room_ws = []
            websockets[room_name] = room_ws

        room_ws.append(ws)

        try:
            while True:
                msg = await ws.receive_text()
                parts = msg.split(" ")
                if parts[0] == "stateupdate":
                    room.time.base_time = float(parts[1])
                    room.time.paused = parts[2] == "1"
                    room.time.started_at = time()
                elif parts[0] == "switchvideo":
                    room.watching = YoutubeWatching(id=parts[1])
                    room.time.base_time = 0
                    room.time.paused = True
                    room.time.started_at = time()
                    start_download(data_dir, room.watching.id, parts[2])
                for update_ws in room_ws:
                    if update_ws is ws and parts[0] == "stateupdate":
                        continue
                    await send_state(update_ws)
        except WebSocketDisconnect:
            pass
        finally:
            room_ws.remove(ws)

    routes = [
        Route("/create_yt_room", create_yt_room),
        Route("/list_rooms", list_rooms),
        Route("/rooms/{name}", get_room),
        Route("/room_video_path", get_room_video_path),
        WebSocketRoute("/ws/{name}", room_ws),
        Mount("/static_yt", StaticFiles(directory=str(data_dir)), name="yt_static"),
    ]

    return {"routes": routes}
