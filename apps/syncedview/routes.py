import asyncio
from dataclasses import dataclass
from pathlib import Path
from time import time
from typing import Dict, List, Literal
import json
import re

import httpx
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket, WebSocketDisconnect


@dataclass
class YoutubeWatching:
    id: str
    type: Literal["youtube"] = "youtube"


@dataclass
class RawURIWatching:
    uri: str
    type: Literal["rawuri"] = "rawuri"


type RoomWatching = YoutubeWatching | RawURIWatching


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
httpx_client = httpx.AsyncClient(headers={"User-Agent": "Mozilla/5.0"})


def start_yt_download(video_dir: Path, video_id: str, quality: str):
    async def task():
        await asyncio.create_subprocess_exec(
            "yt-dlp",
            "-f",
            f"b[height<={quality}]",
            "-o",
            str(video_dir / video_id),
            "--",
            video_id,
        )

    def is_already_downloaded():
        for file in video_dir.iterdir():
            if file.name.startswith(video_id):
                return True
        return False

    if not is_already_downloaded():
        asyncio.create_task(task())


def room_watching_to_dict(watching: RoomWatching) -> dict:
    dict = {"type": watching.type}
    match watching:
        case YoutubeWatching(id=id):
            dict["videoId"] = id
        case RawURIWatching(uri=uri):
            dict["uri"] = uri
    return dict


def serialize_room_state(room: Room) -> str:
    dict = {
        "time": room.time.time,
        "paused": room.time.paused,
        "watching": room_watching_to_dict(room.watching),
    }
    return json.dumps(dict)


async def get_youtube_title_from_id(video_id: str) -> str | None:
    r = await httpx_client.get(f"https://www.youtube.com/watch?v={video_id}")
    match = re.search(r'"title":"([^"]+)"', r.text)
    return match.group(1) if match else None


async def describe_watching(watching: RoomWatching) -> str:
    match watching:
        case YoutubeWatching(id=id):
            return f"youtube -- {await get_youtube_title_from_id(id)}"
        case RawURIWatching(uri=uri):
            return f"raw uri -- {uri}"


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

    async def list_rooms():
        html = ""
        for room in rooms:
            html = (
                html
                + f'<li><a href="./rooms/{room.name}">{room.name} - watching: {await describe_watching(room.watching)}</a></li>\n'
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

        start_yt_download(data_dir / "yt", video_id, quality)

        room = Room(
            name=room_name,
            watching=YoutubeWatching(id=video_id),
            time=TimeState(base_time=0, paused=True, started_at=time()),
        )
        rooms.append(room)
        return JSONResponse({"ok": True})

    async def create_rawuri_room(req: Request):
        room_name = req.query_params.get("name")
        uri = req.query_params.get("uri")
        if room_name is None or uri is None:
            return JSONResponse(
                {"ok": False, "err": "need room_name and uri arguments"},
                status_code=400,
            )

        room = Room(
            name=room_name,
            watching=RawURIWatching(uri=uri),
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
        match room.watching:
            case YoutubeWatching(id=id):
                for file in data_dir.iterdir():
                    if file.name.startswith(id):
                        return JSONResponse(
                            {"ok": True, "path": f"/syncedview/static_yt/{file.name}"}
                        )
                return JSONResponse({"ok": False, "err": "no file for this youtube id"})
            case RawURIWatching(uri=uri):
                return JSONResponse({"ok": True, "path": uri})

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
                elif parts[0] == "switchvideoyt":
                    room.watching = YoutubeWatching(id=parts[1])
                    room.time.base_time = 0
                    room.time.paused = True
                    room.time.started_at = time()
                    start_yt_download(data_dir / "yt", room.watching.id, parts[2])
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
        Route("/create_rawuri_room", create_rawuri_room),
        Route("/list_rooms", list_rooms),
        Route("/rooms/{name}", get_room),
        Route("/room_video_path", get_room_video_path),
        WebSocketRoute("/ws/{name}", room_ws),
        Mount(
            "/static_yt", StaticFiles(directory=str(data_dir / "yt")), name="yt_static"
        ),
    ]

    return {"routes": routes}
