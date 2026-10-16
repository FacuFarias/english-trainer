import time
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from database.models import Card, ReviewLog

CARD_NEW = 0
CARD_LEARNING = 1
CARD_REVIEW = 2
CARD_RELEARNING = 3

QUEUE_NEW = 0
QUEUE_LRN = 1
QUEUE_REV = 2
QUEUE_DAY_LRN = 3

EASE_AGAIN = 1
EASE_HARD = 2
EASE_GOOD = 3
EASE_EASY = 4

INITIAL_EASE = 2.5
MIN_EASE = 1.3
EASE_BONUS_EASY = 0.15
EASE_PENALTY_AGAIN = -0.2
EASE_PENALTY_HARD = -0.15

GRADUATING_INTERVAL = 1
EASY_INTERVAL = 4
MAX_INTERVAL = 36500


def get_due_cards(db: Session, deck_id: int = None, limit: int = 20) -> list:
    now_epoch = int(time.time())
    collection_start = _get_collection_start(db)

    query = db.query(Card).filter(
        Card.queue.in_([QUEUE_LRN, QUEUE_DAY_LRN, QUEUE_REV, QUEUE_NEW])
    )

    if deck_id:
        query = query.filter(Card.deck_id == deck_id)

    due_cards = []

    learning_cards = query.filter(
        Card.queue.in_([QUEUE_LRN]),
        Card.due <= now_epoch
    ).order_by(Card.due).limit(limit).all()
    due_cards.extend(learning_cards)

    remaining = limit - len(due_cards)
    if remaining > 0:
        day_learning = query.filter(
            Card.queue == QUEUE_DAY_LRN,
            Card.due <= collection_start + 86400
        ).order_by(Card.due).limit(remaining).all()
        due_cards.extend(day_learning)

    remaining = limit - len(due_cards)
    if remaining > 0:
        today_num = (now_epoch - collection_start) // 86400
        review_cards = query.filter(
            Card.queue == QUEUE_REV,
            Card.due <= today_num
        ).order_by(Card.due).limit(remaining).all()
        due_cards.extend(review_cards)

    remaining = limit - len(due_cards)
    if remaining > 0:
        new_cards = query.filter(
            Card.queue == QUEUE_NEW
        ).order_by(Card.due).limit(remaining).all()
        due_cards.extend(new_cards)

    return due_cards[:limit]


def review_card(db: Session, card_id: int, ease: int, time_ms: int = 0) -> Card:
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise ValueError("Card not found")

    old_interval = card.interval
    old_ease = card.ease_factor

    if card.card_type == CARD_NEW:
        _review_new(card, ease)
    elif card.card_type == CARD_LEARNING:
        _review_learning(card, ease)
    elif card.card_type == CARD_REVIEW:
        _review_review(card, ease)
    elif card.card_type == CARD_RELEARNING:
        _review_relearning(card, ease)

    card.reps += 1
    card.updated_at = datetime.now(timezone.utc)

    log = ReviewLog(
        card_id=card.id,
        ease=ease,
        interval=card.interval,
        last_interval=old_interval,
        ease_factor=card.ease_factor,
        time_ms=time_ms,
        review_type=card.card_type,
    )
    db.add(log)
    db.commit()
    db.refresh(card)

    return card


def _review_new(card: Card, ease: int):
    if ease == EASE_AGAIN:
        card.card_type = CARD_LEARNING
        card.queue = QUEUE_LRN
        card.left = 1001
        card.due = int(time.time()) + 60
    elif ease == EASE_HARD:
        card.card_type = CARD_LEARNING
        card.queue = QUEUE_LRN
        card.left = 2002
        card.due = int(time.time()) + 300
    elif ease == EASE_GOOD:
        card.card_type = CARD_LEARNING
        card.queue = QUEUE_LRN
        card.left = 2003
        card.due = int(time.time()) + 600
    elif ease == EASE_EASY:
        card.card_type = CARD_REVIEW
        card.queue = QUEUE_REV
        card.interval = EASY_INTERVAL
        card.due = _days_since_creation() + EASY_INTERVAL
        card.ease_factor = max(MIN_EASE, card.ease_factor + EASE_BONUS_EASY)


def _review_learning(card: Card, ease: int):
    steps_left = card.left % 1000
    reps_today = card.left // 1000

    if ease == EASE_AGAIN:
        card.left = 1001
        card.due = int(time.time()) + 60
    elif ease == EASE_HARD:
        card.due = int(time.time()) + 300
    elif ease == EASE_GOOD:
        if steps_left <= 1:
            card.card_type = CARD_REVIEW
            card.queue = QUEUE_REV
            card.interval = GRADUATING_INTERVAL
            card.due = _days_since_creation() + GRADUATING_INTERVAL
            card.left = 0
        else:
            card.left = (reps_today + 1) * 1000 + (steps_left - 1)
            card.due = int(time.time()) + 600
    elif ease == EASE_EASY:
        card.card_type = CARD_REVIEW
        card.queue = QUEUE_REV
        card.interval = EASY_INTERVAL
        card.due = _days_since_creation() + EASY_INTERVAL
        card.ease_factor = max(MIN_EASE, card.ease_factor + EASE_BONUS_EASY)
        card.left = 0


def _review_review(card: Card, ease: int):
    current_interval = card.interval

    if ease == EASE_AGAIN:
        card.card_type = CARD_RELEARNING
        card.queue = QUEUE_LRN
        card.lapses += 1
        card.ease_factor = max(MIN_EASE, card.ease_factor + EASE_PENALTY_AGAIN)
        card.interval = max(1, int(current_interval * 0.5))
        card.left = 1001
        card.due = int(time.time()) + 60
    elif ease == EASE_HARD:
        card.ease_factor = max(MIN_EASE, card.ease_factor + EASE_PENALTY_HARD)
        card.interval = max(1, int(current_interval * 1.2))
        card.due = _days_since_creation() + card.interval
    elif ease == EASE_GOOD:
        card.interval = min(MAX_INTERVAL, int(current_interval * card.ease_factor))
        card.due = _days_since_creation() + card.interval
    elif ease == EASE_EASY:
        card.ease_factor = max(MIN_EASE, card.ease_factor + EASE_BONUS_EASY)
        card.interval = min(MAX_INTERVAL, int(current_interval * card.ease_factor * 1.3))
        card.due = _days_since_creation() + card.interval


def _review_relearning(card: Card, ease: int):
    if ease == EASE_AGAIN:
        card.left = 1001
        card.due = int(time.time()) + 60
    elif ease == EASE_HARD:
        card.due = int(time.time()) + 300
    elif ease == EASE_GOOD:
        card.card_type = CARD_REVIEW
        card.queue = QUEUE_REV
        card.due = _days_since_creation() + card.interval
        card.left = 0
    elif ease == EASE_EASY:
        card.card_type = CARD_REVIEW
        card.queue = QUEUE_REV
        card.interval = min(MAX_INTERVAL, int(card.interval * card.ease_factor * 1.3))
        card.due = _days_since_creation() + card.interval
        card.ease_factor = max(MIN_EASE, card.ease_factor + EASE_BONUS_EASY)
        card.left = 0


def _days_since_creation() -> int:
    return int((time.time() - 1609459200) / 86400)


def _get_collection_start(db: Session) -> int:
    return 1609459200
