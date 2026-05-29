from dataclasses import dataclass
from pathlib import Path
from time import time
from typing import Dict, List, Literal

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
class Room:
    name: str
    watching: YoutubeWatching
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


def start(render, data_dir: Path):
    async def get_room(req: Request):
        room_name = req.path_params.get("name")
        room = None
        for room2 in rooms:
            if room2.name == room_name:
                room = room2
        if room is None:
            return HTMLResponse(f"error!\nunknown room: {room_name}")
        room_dict = {"name": room.name, "watching_type": room.watching.type}
        if room.watching.type == "youtube":
            room_dict["watching_id"] = room.watching.id
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
        room_name = req.query_params.get("name", None)
        video_id = req.query_params.get("videoId", None)
        if room_name is None:
            return JSONResponse({"ok": False, "err": "no room name provided"})
        if video_id is None:
            return JSONResponse({"ok": False, "err": "no video id provided"})
        room = Room(
            name=room_name,
            watching=YoutubeWatching(id=video_id),
            time=TimeState(base_time=0, paused=True, started_at=time()),
        )
        rooms.append(room)
        return JSONResponse({"ok": True})

    async def get_room_video_path(req: Request):
        room_name = req.query_params.get("name", None)
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
        await ws.send_text(
            " ".join(
                [
                    "timeupdate",
                    "1" if room.time.paused else "0",
                    str(room.time.base_time),
                    str(room.time.started_at),
                ]
            )
        )

        room_ws: List[WebSocket] | None = websockets.get(room_name)
        if room_ws is None:
            room_ws = []
            websockets[room_name] = room_ws

        room_ws.append(ws)

        try:
            while True:
                msg = await ws.receive_text()
                parts = msg.split(" ")
                cmd = parts[0]
                args = parts[1:]
                if cmd == "timeupdate":
                    room.time.paused = args[0] == "1"
                    room.time.base_time = float(args[1])
                    room.time.started_at = time()
                    for update_ws in room_ws:
                        await update_ws.send_text(
                            " ".join(
                                [
                                    "timeupdate",
                                    "1" if room.time.paused else "0",
                                    str(room.time.base_time),
                                    str(room.time.started_at),
                                    "1" if update_ws is ws else "0",
                                ]
                            )
                        )
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
