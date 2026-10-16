import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from database.db import init_db
from routes import decks, cards, import_route, stats

app = FastAPI(title="English Trainer", version="1.0.0")

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

app.include_router(decks.router)
app.include_router(cards.router)
app.include_router(import_route.router)
app.include_router(stats.router)


@app.on_event("startup")
async def startup():
    os.makedirs("static/media", exist_ok=True)
    os.makedirs("uploads", exist_ok=True)
    init_db()


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
