from importlib import import_module
from logging import info
from pathlib import Path
from typing import Dict

from jinja2 import Environment, FileSystemLoader
from starlette.applications import Starlette
from starlette.responses import HTMLResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles
from uvicorn.main import run

BASE_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = BASE_DIR / "public"
TEMPLATE_DIR = BASE_DIR / "templates"
APPS_DIR = BASE_DIR / "apps"
DATA_DIR = BASE_DIR / "data"

if not DATA_DIR.exists():
    DATA_DIR.mkdir()

app_mounts = []
app_jinjas: Dict[str, Environment] = {}
apps_loaded = []


def make_render(app_name):
    def render(template_name: str, status_code: int = 200, **context) -> HTMLResponse:
        return app_render(app_name, template_name, context)

    return render


for appdir in APPS_DIR.iterdir():
    if not appdir.is_dir() or appdir.name.startswith("_"):
        continue

    app_mount_routes = []

    routes_file = appdir / "routes.py"
    if routes_file.exists():
        module = import_module(f"apps.{appdir.name}.routes")

        app_data = DATA_DIR / appdir.name
        if not app_data.exists():
            app_data.mkdir()

        templates_path = appdir / "templates"
        if templates_path.exists():
            app_jinjas[appdir.name] = Environment(
                autoescape=True, loader=FileSystemLoader(str(templates_path))
            )

        loaded_app = module.start(make_render(appdir.name), app_data)

        app_mount_routes.extend(list(loaded_app.get("routes")))

    public_dir = appdir / "public"
    if public_dir.exists() and public_dir.is_dir():
        app_mount_routes.append(
            Mount(
                "/",
                StaticFiles(
                    directory=str(public_dir),
                    html=True,
                ),
                name="static",
            )
        )

    app_mounts.append(Mount(f"/{appdir.name}", routes=app_mount_routes))

    apps_loaded.append(appdir.name)

jinja = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))


def render(template_name, **context):
    template = jinja.get_template(template_name)
    return HTMLResponse(template.render(**context))


def app_render(app_name: str, template_name: str, context: dict = {}):
    jinja = app_jinjas.get(app_name)
    if not jinja:
        return HTMLResponse(
            f"{app_name} is not registered to use templates", status_code=500
        )

    template = jinja.get_template(template_name)
    return HTMLResponse(template.render(**context))


async def index(req):
    return render("index.html", apps=apps_loaded)


info(f"apps loaded: {', '.join(apps_loaded)}")

app = Starlette(
    routes=[
        Route("/", index),
        *app_mounts,
        Mount("/", StaticFiles(directory=PUBLIC_DIR), name="root_static"),
    ],
    debug=True,
)

if __name__ == "__main__":
    run(app, host="0.0.0.0", port=5000, log_level="info")
