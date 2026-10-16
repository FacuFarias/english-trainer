from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from database.models import Card, ReviewLog, Deck


def get_daily_stats(db: Session, days: int = 7) -> list:
    now = datetime.now(timezone.utc)
    stats = []

    for i in range(days):
        day = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        reviewed = db.query(func.count(ReviewLog.id)).filter(
            and_(
                ReviewLog.reviewed_at >= day_start,
                ReviewLog.reviewed_at < day_end
            )
        ).scalar() or 0

        correct = db.query(func.count(ReviewLog.id)).filter(
            and_(
                ReviewLog.reviewed_at >= day_start,
                ReviewLog.reviewed_at < day_end,
                ReviewLog.ease >= 3
            )
        ).scalar() or 0

        stats.append({
            "date": day_start.strftime("%Y-%m-%d"),
            "reviewed": reviewed,
            "correct": correct,
            "accuracy": round(correct / reviewed * 100, 1) if reviewed > 0 else 0,
        })

    stats.reverse()
    return stats


def get_deck_stats(db: Session, deck_id: int = None) -> dict:
    query = db.query(Card)
    if deck_id:
        query = query.filter(Card.deck_id == deck_id)

    total = query.count()
    new_count = query.filter(Card.card_type == 0).count()
    learning = query.filter(Card.card_type == 1).count()
    review = query.filter(Card.card_type == 2).count()
    relearning = query.filter(Card.card_type == 3).count()

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    reviewed_today = db.query(func.count(ReviewLog.id)).filter(
        and_(
            ReviewLog.reviewed_at >= today_start,
            ReviewLog.reviewed_at < today_end
        )
    ).scalar() or 0

    correct_today = db.query(func.count(ReviewLog.id)).filter(
        and_(
            ReviewLog.reviewed_at >= today_start,
            ReviewLog.reviewed_at < today_end,
            ReviewLog.ease >= 3
        )
    ).scalar() or 0

    return {
        "total": total,
        "new": new_count,
        "learning": learning + relearning,
        "review": review,
        "reviewed_today": reviewed_today,
        "correct_today": correct_today,
        "accuracy_today": round(correct_today / reviewed_today * 100, 1) if reviewed_today > 0 else 0,
    }


def get_streak(db: Session) -> int:
    now = datetime.now(timezone.utc)
    streak = 0

    for i in range(365):
        day = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        count = db.query(func.count(ReviewLog.id)).filter(
            and_(
                ReviewLog.reviewed_at >= day_start,
                ReviewLog.reviewed_at < day_end
            )
        ).scalar() or 0

        if count > 0:
            streak += 1
        else:
            break

    return streak


def get_all_decks_stats(db: Session) -> list:
    decks = db.query(Deck).all()
    result = []

    for deck in decks:
        stats = get_deck_stats(db, deck.id)
        result.append({
            "id": deck.id,
            "name": deck.name,
            **stats,
        })

    return result
