from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database.db import get_db
from services.stats import get_daily_stats, get_streak, get_all_decks_stats, get_deck_stats

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/stats", response_class=HTMLResponse)
async def stats_page(request: Request, db: Session = Depends(get_db)):
    daily = get_daily_stats(db, days=30)
    streak = get_streak(db)
    decks_stats = get_all_decks_stats(db)
    overall = get_deck_stats(db)

    return templates.TemplateResponse("stats.html", {
        "request": request,
        "daily_stats": daily,
        "streak": streak,
        "decks_stats": decks_stats,
        "overall": overall,
    })


@router.get("/api/stats/daily")
async def api_daily_stats(days: int = 30, db: Session = Depends(get_db)):
    return get_daily_stats(db, days)


@router.get("/api/stats/streak")
async def api_streak(db: Session = Depends(get_db)):
    return {"streak": get_streak(db)}


@router.get("/api/stats/overview")
async def api_overview(db: Session = Depends(get_db)):
    return get_deck_stats(db)
