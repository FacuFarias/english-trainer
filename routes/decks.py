from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database.db import get_db
from database.models import Deck
from services.stats import get_all_decks_stats, get_deck_stats

router = APIRouter()
templates = Jinja2Templates(directory="templates")


class DeckUpdate(BaseModel):
    name: str = None
    category: str = None
    favorite: int = None
    hidden: int = None


@router.get("/decks", response_class=HTMLResponse)
async def list_decks(request: Request, show_hidden: int = 0, db: Session = Depends(get_db)):
    query = db.query(Deck)
    if not show_hidden:
        query = query.filter(Deck.hidden == 0)
    decks = query.order_by(Deck.favorite.desc(), Deck.name).all()

    decks_data = []
    for d in decks:
        stats = get_deck_stats(db, d.id)
        decks_data.append({
            "id": d.id,
            "name": d.name,
            "category": d.category or "",
            "favorite": d.favorite,
            "hidden": d.hidden,
            **stats,
        })

    categories = sorted(set(d["category"] for d in decks_data if d["category"]))

    return templates.TemplateResponse("decks.html", {
        "request": request,
        "decks": decks_data,
        "categories": categories,
        "show_hidden": show_hidden,
    })


@router.get("/api/decks")
async def get_decks(db: Session = Depends(get_db)):
    decks = db.query(Deck).filter(Deck.hidden == 0).order_by(Deck.name).all()
    return [{"id": d.id, "name": d.name, "category": d.category, "favorite": d.favorite} for d in decks]


@router.put("/api/decks/{deck_id}")
async def update_deck(deck_id: int, data: DeckUpdate, db: Session = Depends(get_db)):
    deck = db.query(Deck).filter(Deck.id == deck_id).first()
    if not deck:
        return {"error": "Deck not found"}
    if data.name is not None:
        deck.name = data.name
    if data.category is not None:
        deck.category = data.category
    if data.favorite is not None:
        deck.favorite = data.favorite
    if data.hidden is not None:
        deck.hidden = data.hidden
    db.commit()
    return {"success": True}


@router.delete("/api/decks/{deck_id}")
async def delete_deck(deck_id: int, db: Session = Depends(get_db)):
    deck = db.query(Deck).filter(Deck.id == deck_id).first()
    if not deck:
        return {"error": "Deck not found"}
    db.delete(deck)
    db.commit()
    return {"success": True}
