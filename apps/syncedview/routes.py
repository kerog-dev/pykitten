from dataclasses import dataclass
from typing import List, Literal

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route


@dataclass
class YoutubeWatching:
    id: str
    type: Literal["youtube"] = "youtube"


@dataclass
class Room:
    name: str
    watching: YoutubeWatching


rooms: List[Room] = []


def start(render):
    async def get_room(req: Request):
        room_name = req.path_params.get("name")
        room = None
        for room2 in rooms:
            if room2.name == room_name:
                room = room2
        if room is None:
            return HTMLResponse(f"error!\nunknown room: {room_name}")
        return render("room.html", room=room)

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
        room = Room(name=room_name, watching=YoutubeWatching(id=video_id))
        rooms.append(room)
        return JSONResponse({"ok": True})

    routes = [
        Route("/create_yt_room", create_yt_room),
        Route("/list_rooms", list_rooms),
        Route("/rooms/{name}", get_room),
    ]

    return {"routes": routes}
