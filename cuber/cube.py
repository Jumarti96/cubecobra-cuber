"""Card and Cube data models; enriched.json / raw.csv / meta.json I/O."""

from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

CUBES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cubes")

CUBECOBRA_CSV_COLUMNS = [
    "name", "CMC", "Type", "Color", "Set", "Collector Number", "Rarity",
    "Color Category", "status", "Finish", "board", "maybeboard",
    "image URL", "image Back URL", "tags", "Notes", "MTGO ID", "Custom", "Voucher",
]

BASIC_LAND_NAMES = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"}


def find_cube_dir(id_or_slug: str) -> str:
    """Resolve a short_id or slug to the cube directory path.

    Priority: direct folder name match (slug) > short_id scan (meta.json).
    """
    # 1. Direct folder name match — slug takes priority
    direct = os.path.join(CUBES_DIR, id_or_slug)
    if os.path.isdir(direct) and os.path.exists(os.path.join(direct, "meta.json")):
        return direct

    # 2. Fall back to scanning meta.json files for a matching short_id
    if os.path.isdir(CUBES_DIR):
        for entry in os.scandir(CUBES_DIR):
            if not entry.is_dir():
                continue
            meta_path = os.path.join(entry.path, "meta.json")
            if not os.path.exists(meta_path):
                continue
            try:
                with open(meta_path, encoding="utf-8") as f:
                    meta = json.load(f)
                if meta.get("short_id") == id_or_slug:
                    return entry.path
            except (json.JSONDecodeError, OSError):
                continue

    raise FileNotFoundError(
        f"No cube found for '{id_or_slug}'. Run: python -m cuber fetch {id_or_slug}"
    )


@dataclass
class CardFace:
    name: str
    oracle_text: str
    mana_cost: str
    type_line: str
    power: Optional[str] = None
    toughness: Optional[str] = None


@dataclass
class Card:
    name: str
    scryfall_id: str
    cmc: float
    type_line: str
    color_identity: List[str]
    oracle_text: str
    rarity: str
    set_code: str
    collector_number: str
    color_category: str
    board: str
    finish: str
    status: str
    image_url: str
    # optional / enriched fields
    colors: List[str] = field(default_factory=list)
    power: Optional[str] = None
    toughness: Optional[str] = None
    mana_cost: Optional[str] = None
    layout: Optional[str] = None
    image_back_url: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    notes: Optional[str] = None
    mtgo_id: Optional[str] = None
    card_faces: Optional[List[CardFace]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "name": self.name,
            "scryfall_id": self.scryfall_id,
            "cmc": self.cmc,
            "type_line": self.type_line,
            "color_identity": self.color_identity,
            "oracle_text": self.oracle_text,
            "rarity": self.rarity,
            "set": self.set_code,
            "collector_number": self.collector_number,
            "color_category": self.color_category,
            "board": self.board,
            "finish": self.finish,
            "status": self.status,
            "image_url": self.image_url,
            "colors": self.colors,
            "power": self.power,
            "toughness": self.toughness,
            "mana_cost": self.mana_cost,
            "layout": self.layout,
            "image_back_url": self.image_back_url,
            "tags": self.tags,
            "notes": self.notes,
            "mtgo_id": self.mtgo_id,
        }
        if self.card_faces:
            d["card_faces"] = [
                {
                    "name": f.name,
                    "oracle_text": f.oracle_text,
                    "mana_cost": f.mana_cost,
                    "type_line": f.type_line,
                    "power": f.power,
                    "toughness": f.toughness,
                }
                for f in self.card_faces
            ]
        return d

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Card":
        faces = None
        if "card_faces" in d and d["card_faces"]:
            faces = [
                CardFace(
                    name=f.get("name", ""),
                    oracle_text=f.get("oracle_text", ""),
                    mana_cost=f.get("mana_cost", ""),
                    type_line=f.get("type_line", ""),
                    power=f.get("power"),
                    toughness=f.get("toughness"),
                )
                for f in d["card_faces"]
            ]
        return Card(
            name=d["name"],
            scryfall_id=d.get("scryfall_id", ""),
            cmc=float(d.get("cmc", 0)),
            type_line=d.get("type_line", ""),
            color_identity=d.get("color_identity", []),
            oracle_text=d.get("oracle_text", ""),
            rarity=d.get("rarity", ""),
            set_code=d.get("set", ""),
            collector_number=d.get("collector_number", ""),
            color_category=d.get("color_category", ""),
            board=d.get("board", "mainboard"),
            finish=d.get("finish", "Non-Foil"),
            status=d.get("status", ""),
            image_url=d.get("image_url", ""),
            colors=d.get("colors", []),
            power=d.get("power"),
            toughness=d.get("toughness"),
            mana_cost=d.get("mana_cost"),
            layout=d.get("layout"),
            image_back_url=d.get("image_back_url"),
            tags=d.get("tags", []),
            notes=d.get("notes"),
            mtgo_id=d.get("mtgo_id"),
            card_faces=faces,
        )


@dataclass
class Cube:
    short_id: str
    cube_id: str
    title: str
    fetched_at: str
    cards: List[Card] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cube_id": self.cube_id,
            "short_id": self.short_id,
            "title": self.title,
            "fetched_at": self.fetched_at,
            "cards": [c.to_dict() for c in self.cards],
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Cube":
        return Cube(
            short_id=d.get("short_id", ""),
            cube_id=d.get("cube_id", ""),
            title=d.get("title", ""),
            fetched_at=d.get("fetched_at", ""),
            cards=[Card.from_dict(c) for c in d.get("cards", [])],
        )


# ── I/O helpers ──────────────────────────────────────────────────────────────

def cube_dir(short_id: str) -> str:
    """Return the directory for a cube, resolving by slug or short_id if it exists."""
    try:
        return find_cube_dir(short_id)
    except FileNotFoundError:
        return os.path.join(CUBES_DIR, short_id)


def ensure_cube_dir(short_id: str) -> str:
    path = cube_dir(short_id)
    os.makedirs(path, exist_ok=True)
    return path


def load_cube_from_mainboard_csv(id_or_slug: str) -> Cube:
    """Build a Cube from the working mainboard.csv without requiring enriched.json."""
    rows = load_raw_csv(id_or_slug)
    meta = load_meta(id_or_slug)

    cards = []
    for row in rows:
        name = row.get("name", "").strip()
        if not name:
            continue
        color_str = row.get("Color", "")
        color_letters = [c for c in color_str if c in "WUBRG"]
        try:
            cmc = float(row.get("CMC") or 0)
        except (ValueError, TypeError):
            cmc = 0.0
        tags = [t.strip() for t in (row.get("tags", "") or "").split(";") if t.strip()]
        cards.append(Card(
            name=name,
            scryfall_id="",
            cmc=cmc,
            type_line=row.get("Type", ""),
            colors=color_letters,
            color_identity=color_letters,
            oracle_text="",
            rarity=(row.get("Rarity") or "").lower(),
            set_code=(row.get("Set") or "").lower(),
            collector_number=row.get("Collector Number", ""),
            color_category=row.get("Color Category", ""),
            board=row.get("board", "mainboard"),
            finish=row.get("Finish", "Non-Foil"),
            status=row.get("status", ""),
            image_url=row.get("image URL", ""),
            image_back_url=row.get("image Back URL") or None,
            tags=tags,
            notes=row.get("Notes") or None,
            mtgo_id=row.get("MTGO ID") or None,
        ))

    return Cube(
        short_id=meta.get("short_id", id_or_slug),
        cube_id=meta.get("short_id", id_or_slug),
        title=meta.get("title", id_or_slug),
        fetched_at=meta.get("fetched_at", ""),
        cards=cards,
    )


def load_enriched(short_id: str) -> Cube:
    path = os.path.join(cube_dir(short_id), "enriched.json")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"enriched.json not found for cube '{short_id}'. "
            f"Run: python -m cuber enrich {short_id}"
        )
    with open(path, "r", encoding="utf-8") as f:
        return Cube.from_dict(json.load(f))


def save_enriched(cube: Cube, short_id: str) -> str:
    ensure_cube_dir(short_id)
    path = os.path.join(cube_dir(short_id), "enriched.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cube.to_dict(), f, indent=2, ensure_ascii=False)
    return path


def load_meta(short_id: str) -> Dict[str, Any]:
    path = os.path.join(cube_dir(short_id), "meta.json")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_meta(meta: Dict[str, Any], short_id: str) -> str:
    ensure_cube_dir(short_id)
    path = os.path.join(cube_dir(short_id), "meta.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    return path


def load_raw_csv(short_id: str) -> List[Dict[str, str]]:
    """Parse the cube's card list CSV. Tries mainboard.csv (v2) then raw.csv (v1).

    Stub rows (only 'name' set, all other columns empty) are valid —
    they are created by 'add-card' and hydrated on the next 'enrich' run.
    """
    base = cube_dir(short_id)
    for filename in ("mainboard.csv", "raw.csv"):
        path = os.path.join(base, filename)
        if os.path.exists(path):
            break
    else:
        raise FileNotFoundError(
            f"No card list found for cube '{short_id}'. "
            f"Run: python -m cuber fetch {short_id}"
        )

    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        actual_cols = list(reader.fieldnames or [])
        rows = [r for r in reader if r.get("name", "").strip()]

    missing = [c for c in CUBECOBRA_CSV_COLUMNS if c not in actual_cols]
    extra = [c for c in actual_cols if c not in CUBECOBRA_CSV_COLUMNS]
    schema_warning = bool(missing or extra)

    if schema_warning:
        meta = load_meta(short_id)
        meta["schema_warning"] = True
        meta["schema_warning_detail"] = {"missing": missing, "extra": extra}
        save_meta(meta, short_id)

    return rows
