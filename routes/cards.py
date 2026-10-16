import re
import random
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database.db import get_db
from database.models import Card
from services.scheduler import get_due_cards, review_card

router = APIRouter()
templates = Jinja2Templates(directory="templates")


class ReviewRequest(BaseModel):
    card_id: int
    ease: int
    time_ms: int = 0


def _extract_word(html: str) -> str:
    match = re.search(r'class="green[^"]*"[^>]*>([^<]+)<', html)
    if match:
        return match.group(1).strip()
    clean = re.sub(r'<[^>]+>', '', html)
    return clean.strip().split('\n')[0].strip()


def _extract_meaning(html: str) -> str:
    match = re.search(r'class="orange[^"]*"[^>]*>([^<]+)<', html)
    if match:
        return match.group(1).strip()
    return ""


def _extract_example(html: str) -> str:
    matches = re.findall(r'class="example"[^>]*>([^<]+)<', html)
    for m in matches:
        if m.strip().startswith('Example:') or m.strip().startswith('Ejemplo:'):
            return m.strip()
    return matches[0].strip() if matches else ""


def _extract_pronunciation(html: str) -> str:
    greens = re.findall(r'class="green[^"]*"[^>]*>([^<]+)<', html)
    for g in greens:
        t = g.strip()
        if t and not t.isspace() and re.search(r'[əˈː\-\u0250-\u02AF]', t):
            return t
    return greens[-1].strip() if len(greens) > 1 else ""


def _extract_image(html: str) -> str:
    match = re.search(r'<img[^>]+src="([^"]+)"', html)
    return match.group(1) if match else ""


@router.get("/review/{deck_id}", response_class=HTMLResponse)
async def review_page(request: Request, deck_id: int, db: Session = Depends(get_db)):
    cards = get_due_cards(db, deck_id, limit=4)
    total_due = len(get_due_cards(db, deck_id, limit=1000))

    cards_data = []
    for c in cards:
        cards_data.append({
            "id": c.id,
            "word": _extract_word(c.front),
            "meaning": _extract_meaning(c.back),
            "example": _extract_example(c.back),
            "pronunciation": _extract_pronunciation(c.front),
            "image": _extract_image(c.back),
            "audio_files": [m for m in (c.media_files or "").split(",") if m.endswith((".mp3", ".ogg", ".wav", ".m4a"))],
        })

    return templates.TemplateResponse("review.html", {
        "request": request,
        "cards": cards_data,
        "deck_id": deck_id,
        "total_due": total_due,
    })


@router.get("/api/cards/due/{deck_id}")
async def get_due(deck_id: int, limit: int = 20, db: Session = Depends(get_db)):
    cards = get_due_cards(db, deck_id, limit)
    return [{
        "id": c.id,
        "front": c.front,
        "back": c.back,
        "media_files": c.media_files,
        "card_type": c.card_type,
    } for c in cards]


@router.get("/api/cards/{card_id}")
async def get_card(card_id: int, db: Session = Depends(get_db)):
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        return {"error": "Card not found"}
    return {
        "id": card.id,
        "front": card.front,
        "back": card.back,
        "media_files": card.media_files,
        "word": _extract_word(card.front),
        "meaning": _extract_meaning(card.back),
        "example": _extract_example(card.back),
    }


@router.get("/api/cards/random/{deck_id}")
async def get_random_cards(deck_id: int, exclude: int = 0, count: int = 3, db: Session = Depends(get_db)):
    cards = db.query(Card).filter(
        Card.deck_id == deck_id,
        Card.id != exclude
    ).all()

    if len(cards) < count:
        cards = db.query(Card).filter(Card.id != exclude).all()

    selected = random.sample(cards, min(count, len(cards)))
    return [{
        "id": c.id,
        "word": _extract_word(c.front),
        "meaning": _extract_meaning(c.back),
    } for c in selected]


@router.post("/api/cards/review")
async def submit_review(review: ReviewRequest, db: Session = Depends(get_db)):
    try:
        card = review_card(db, review.card_id, review.ease, review.time_ms)
        return {
            "success": True,
            "card_id": card.id,
            "next_interval": card.interval,
            "ease_factor": card.ease_factor,
        }
    except ValueError as e:
        return {"error": str(e)}
