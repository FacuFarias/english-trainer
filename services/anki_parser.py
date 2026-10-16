import zipfile
import sqlite3
import json
import os
import re
import shutil
import tempfile
from sqlalchemy.orm import Session
from database.models import Deck, Card


FIELD_SEPARATOR = "\x1f"


def parse_apkg(file_path: str, db: Session) -> dict:
    result = {"decks": 0, "cards": 0, "media": 0, "errors": []}

    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                zf.extractall(tmp_dir)
        except zipfile.BadZipFile:
            result["errors"].append("Invalid .apkg file: not a valid ZIP archive")
            return result

        anki2_file = None
        media_map = {}

        for f in os.listdir(tmp_dir):
            if f.endswith(".anki2"):
                anki2_file = os.path.join(tmp_dir, f)
            elif f == "media" and os.path.isfile(os.path.join(tmp_dir, f)):
                with open(os.path.join(tmp_dir, f), "r") as mf:
                    media_map = json.load(mf)

        if not anki2_file:
            result["errors"].append("No .anki2 database found in package")
            return result

        media_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "media")
        os.makedirs(media_dir, exist_ok=True)

        for media_id, media_name in media_map.items():
            src = os.path.join(tmp_dir, media_id)
            if os.path.exists(src):
                dst = os.path.join(media_dir, media_name)
                shutil.copy2(src, dst)
                result["media"] += 1

        try:
            conn = sqlite3.connect(anki2_file)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM col")
            col_row = cursor.fetchone()
            if col_row:
                decks_json = json.loads(col_row["decks"])
                models_json = json.loads(col_row["models"])

                deck_map = {}
                for deck_id, deck_data in decks_json.items():
                    if deck_id == "1" and deck_data.get("name") == "Default":
                        continue

                    existing = db.query(Deck).filter(Deck.name == deck_data["name"]).first()
                    if existing:
                        deck_map[int(deck_id)] = existing
                    else:
                        new_deck = Deck(
                            name=deck_data["name"],
                            description=deck_data.get("desc", "")
                        )
                        db.add(new_deck)
                        db.flush()
                        deck_map[int(deck_id)] = new_deck
                        result["decks"] += 1

                cursor.execute("SELECT * FROM notes")
                notes = {row["id"]: row for row in cursor.fetchall()}

                cursor.execute("SELECT * FROM cards")
                anki_cards = cursor.fetchall()

                for anki_card in anki_cards:
                    note = notes.get(anki_card["nid"])
                    if not note:
                        continue

                    model = models_json.get(str(note["mid"]))
                    if not model:
                        continue

                    fields = note["flds"].split(FIELD_SEPARATOR)
                    templates = model.get("tmpls", [])

                    ord_val = anki_card["ord"]
                    if ord_val < len(templates):
                        template = templates[ord_val]
                    elif templates:
                        template = templates[0]
                    else:
                        continue

                    front = _render_template(template.get("qfmt", ""), fields, model)
                    back = _render_template(template.get("afmt", ""), fields, model)

                    if not front.strip():
                        front = fields[0] if fields else ""
                    if not back.strip():
                        back = fields[1] if len(fields) > 1 else ""

                    front = _clean_html(front)
                    back = _clean_html(back)

                    deck = deck_map.get(anki_card["did"])
                    if not deck:
                        for dk in deck_map.values():
                            deck = dk
                            break
                    if not deck:
                        continue

                    media_files_list = _extract_media_refs(front + back, media_map)
                    media_str = ",".join(media_files_list)

                    new_card = Card(
                        deck_id=deck.id,
                        front=front,
                        back=back,
                        media_files=media_str,
                        card_type=anki_card["type"],
                        queue=anki_card["queue"],
                        due=anki_card["due"],
                        interval=anki_card["ivl"],
                        ease_factor=anki_card["factor"] / 1000.0 if anki_card["factor"] > 0 else 2.5,
                        reps=anki_card["reps"],
                        lapses=anki_card["lapses"],
                        left=anki_card["left"],
                    )
                    db.add(new_card)
                    result["cards"] += 1

            conn.close()

        except Exception as e:
            result["errors"].append(f"Error parsing Anki database: {str(e)}")

        db.commit()

    return result


def _render_template(template: str, fields: list, model: dict) -> str:
    if not template:
        return ""

    field_names = [f.get("name", f"Field{i}") for i, f in enumerate(model.get("flds", []))]

    result = template
    for i, (name, value) in enumerate(zip(field_names, fields)):
        placeholder = "{{" + name + "}}"
        result = result.replace(placeholder, value)
    result = result.replace("{{FrontSide}}", "")

    result = re.sub(r"\{\{[^}]+\}\}", "", result)

    return result


def _clean_html(text: str) -> str:
    text = re.sub(r'\[sound:[^\]]*\]', '', text)
    text = re.sub(r'<br\s*/?\s*>', '\n', text)
    text = re.sub(r'</div>\s*<div', '</div>\n<div', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(
        r'<img\s+([^>]*?)src=["\']([^"\':/]+)["\']',
        r'<img \1src="/static/media/\2"',
        text
    )
    return text.strip()


def _extract_media_refs(text: str, media_map: dict) -> list:
    media_files = []

    for match in re.findall(r'src=["\']([^"\']+)["\']', text):
        clean = match.strip()
        if clean and not clean.startswith("http"):
            media_files.append(clean)

    for match in re.findall(r'\[sound:([^\]]+)\]', text):
        clean = match.strip()
        if clean:
            media_files.append(clean)

    return list(dict.fromkeys(media_files))
