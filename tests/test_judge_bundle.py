import sys
import os
import json
import hashlib
import tempfile

# Add parent to path so we can import repo modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.make_judge_bundle import build_bundle


def _mk_deck_dir(root, name, spell):
    d = os.path.join(root, name)
    os.makedirs(d)
    deck = {
        "deck_name": name,                       # must NOT survive into the bundle
        "cube_id": "uuid-x",
        "cube_slug": "test-cube",
        "built_at": "2026-01-01T00:00:00Z",      # must NOT survive into the bundle
        "format": "40-card",
        "strategy": "test strategy",
        "colors": "R",
        "identity": "a test deck",
        "dossier_sha256": "deadbeef",            # must NOT survive into the bundle
        "mana_audit": {"overall_status": "PASS"},
        "mainboard": [
            {"name": spell, "qty": 1, "board": "mainboard", "cmc": 1,
             "type_line": "Instant", "mana_cost": "{R}", "colors": ["R"],
             "color_identity": ["R"], "rarity": "common",
             "oracle_text": "Deal 3 damage to any target.",
             "image_url": "http://leak.example/x.png", "mtgo_id": 123},
        ],
        "sideboard": [],
    }
    with open(os.path.join(d, "deck.json"), "w", encoding="utf-8") as f:
        json.dump(deck, f)
    return d


def _mk_cube_dir(root):
    d = os.path.join(root, "cubes", "test-cube")
    os.makedirs(d)
    enriched = {"id": "uuid-x", "title": "Test Cube", "cards": [
        {"name": "Bolt A", "board": "mainboard", "oracle_text": "Deal 3 damage to any target.",
         "mana_cost": "{R}", "colors": ["R"], "color_identity": ["R"], "cmc": 1,
         "type_line": "Instant", "rarity": "common", "power": None, "toughness": None,
         "image_url": "http://leak.example/a.png", "taxonomic_profile": {"x": 1}},
        {"name": "Maybe Card", "board": "maybeboard", "oracle_text": "irrelevant",
         "mana_cost": "{U}", "colors": ["U"], "color_identity": ["U"], "cmc": 1,
         "type_line": "Instant", "rarity": "common", "power": None, "toughness": None},
    ]}
    with open(os.path.join(d, "enriched.json"), "w", encoding="utf-8") as f:
        json.dump(enriched, f)
    with open(os.path.join(d, "dossier.json"), "w", encoding="utf-8") as f:
        json.dump({"threat_profile": {"graveyard": 3}}, f)
    return d


def test_build_bundle_blinds_and_hashes():
    with tempfile.TemporaryDirectory() as root:
        deck1 = _mk_deck_dir(root, "opus-old-something", "Bolt A")
        deck2 = _mk_deck_dir(root, "new-skill-something", "Bolt A")
        cube = _mk_cube_dir(root)
        out = os.path.join(root, "bundle")

        result = build_bundle(deck1, deck2, cube, out, seed=1)

        bundle_path = os.path.join(out, "judge_input.json")
        assert result["bundle_path"] == bundle_path
        raw = open(bundle_path, "rb").read()
        assert hashlib.sha256(raw).hexdigest() == result["sha256"]

        bundle = json.loads(raw)
        assert set(bundle["decks"].keys()) == {"A", "B"}
        # pool ships mainboard only, without display/taxonomy fields
        pool_names = [c["name"] for c in bundle["card_pool"]]
        assert pool_names == ["Bolt A"]
        assert "taxonomic_profile" not in bundle["card_pool"][0]
        assert bundle["dossier"]["threat_profile"] == {"graveyard": 3}
        # nothing origin-identifying anywhere in the bundle bytes
        text = raw.decode("utf-8")
        for leak in ("opus-old", "new-skill", "deck_name", "built_at",
                     "dossier_sha256", "leak.example", "mtgo_id"):
            assert leak not in text, leak

        # label key lives OUTSIDE the bundle dir and maps labels to inputs
        key_path = result["key_path"]
        assert os.path.dirname(key_path) != out
        key = json.load(open(key_path, encoding="utf-8"))
        assert sorted(key["labels"].keys()) == ["A", "B"]
        assert sorted(key["labels"].values()) == sorted([deck1, deck2])


def test_build_bundle_label_assignment_is_seed_deterministic():
    def assignment(seed):
        with tempfile.TemporaryDirectory() as root:
            deck1 = _mk_deck_dir(root, "one", "Bolt A")
            deck2 = _mk_deck_dir(root, "two", "Bolt A")
            cube = _mk_cube_dir(root)
            result = build_bundle(deck1, deck2, cube, os.path.join(root, "b"), seed=seed)
            key = json.load(open(result["key_path"], encoding="utf-8"))
            return os.path.basename(key["labels"]["A"])

    assert assignment(7) == assignment(7)
    # seeds 0..9 must not all agree — the coin actually flips
    assert len({assignment(s) for s in range(10)}) == 2
