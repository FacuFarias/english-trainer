import os
import shutil
from fastapi import APIRouter, Depends, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database.db import get_db
from services.anki_parser import parse_apkg
from config import UPLOAD_DIR

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/import", response_class=HTMLResponse)
async def import_page(request: Request):
    return templates.TemplateResponse("import.html", {"request": request})


@router.post("/import")
async def upload_apkg(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith(".apkg"):
        return templates.TemplateResponse("import.html", {
            "request": request,
            "error": "Please upload a valid .apkg file",
        })

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIR, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    result = parse_apkg(file_path, db)

    os.remove(file_path)

    if result["errors"]:
        return templates.TemplateResponse("import.html", {
            "request": request,
            "error": "; ".join(result["errors"]),
        })

    return templates.TemplateResponse("import.html", {
        "request": request,
        "success": True,
        "decks_imported": result["decks"],
        "cards_imported": result["cards"],
        "media_imported": result["media"],
    })
