import sys
import os
import inspect

# Add parent to path so we can import cuber modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import csv
import tempfile

from cuber.cli import _ops_tokenize, _parse_count_modifier
from cuber import cube_manager
from cuber.cube_manager import remove_cards, scale_cards, add_cards
from cuber.cube import CUBECOBRA_CSV_COLUMNS


def assert_eq(actual, expected, msg=""):
    if actual != expected:
        raise AssertionError(f"Expected {expected!r}, got {actual!r}. {msg}")


def test_parse_count_modifier():
    # No modifier
    names, count = _parse_count_modifier(["Bolt", "Serra", "Angel"])
    assert_eq(names, ["Bolt", "Serra", "Angel"])
    assert_eq(count, None)

    # x N modifier
    names, count = _parse_count_modifier(["Bolt", "x", "3"])
    assert_eq(names, ["Bolt"])
    assert_eq(count, 3)

    # * N modifier
    names, count = _parse_count_modifier(["Bolt", "*", "2"])
    assert_eq(names, ["Bolt"])
    assert_eq(count, 2)

    # Inline *N modifier
    names, count = _parse_count_modifier(["Bolt", "*4"])
    assert_eq(names, ["Bolt"])
    assert_eq(count, 4)

    print("  [OK] _parse_count_modifier tests passed")


def test_tokenizer_position_free():
    # Operator at start
    op, data, mod = _ops_tokenize('+ "Bolt"')
    assert_eq(op, "+")
    assert_eq(len(data), 1)
    assert_eq(data[0]["name"], "Bolt")
    assert_eq(data[0]["count"], 1)

    # Operator at end
    op, data, mod = _ops_tokenize('"Bolt" +')
    assert_eq(op, "+")
    assert_eq(len(data), 1)
    assert_eq(data[0]["name"], "Bolt")

    # Operator in middle
    op, data, mod = _ops_tokenize('"Bolt" + "Serra Angel"')
    assert_eq(op, "+")
    assert_eq(len(data), 2)
    assert_eq(data[0]["name"], "Bolt")
    assert_eq(data[1]["name"], "Serra Angel")

    print("  [OK] Position-free parsing tests passed")


def test_tokenizer_separator():
    # Repeated plus as separator
    op, data, mod = _ops_tokenize('+ "Bolt" + "Serra Angel"')
    assert_eq(op, "+")
    assert_eq(len(data), 2)
    assert_eq(data[0]["name"], "Bolt")
    assert_eq(data[1]["name"], "Serra Angel")

    # Repeated equals as separator
    op, data, mod = _ops_tokenize('= "Bolt" = "Serra Angel" 2')
    assert_eq(op, "=")
    assert_eq(len(data), 2)
    assert_eq(data[0]["name"], "Bolt")
    assert_eq(data[0]["target"], 1)
    assert_eq(data[1]["name"], "Serra Angel")
    assert_eq(data[1]["target"], 2)

    print("  [OK] Redundant separator tests passed")


def test_tokenizer_equals():
    # Basic equals
    op, data, mod = _ops_tokenize('= "Bolt" 4')
    assert_eq(op, "=")
    assert_eq(len(data), 1)
    assert_eq(data[0]["name"], "Bolt")
    assert_eq(data[0]["target"], 4)

    # Equals at end
    op, data, mod = _ops_tokenize('"Bolt" = 4')
    assert_eq(op, "=")
    assert_eq(data[0]["name"], "Bolt")
    assert_eq(data[0]["target"], 4)

    # Equals zero
    op, data, mod = _ops_tokenize('= "Bolt" 0')
    assert_eq(op, "=")
    assert_eq(data[0]["target"], 0)

    print("  [OK] Equals operator tests passed")


def test_tokenizer_per_card_quantities():
    # Single card with quantity
    op, data, mod = _ops_tokenize('+ "Bolt" * 3')
    assert_eq(op, "+")
    assert_eq(data[0]["name"], "Bolt")
    assert_eq(data[0]["count"], 3)

    # Mixed quantities
    op, data, mod = _ops_tokenize('+ "Bolt" * 3 "Serra Angel" * 2')
    assert_eq(op, "+")
    assert_eq(len(data), 2)
    assert_eq(data[0]["name"], "Bolt")
    assert_eq(data[0]["count"], 3)
    assert_eq(data[1]["name"], "Serra Angel")
    assert_eq(data[1]["count"], 2)

    # Default quantity
    op, data, mod = _ops_tokenize('+ "Bolt" "Serra Angel"')
    assert_eq(data[0]["count"], 1)
    assert_eq(data[1]["count"], 1)

    print("  [OK] Per-card quantity tests passed")


def test_tokenizer_scale():
    # Multiply prefix
    op, data, mod = _ops_tokenize('* 2 "Bolt"')
    assert_eq(op, "*")
    assert_eq(mod, 2)
    assert_eq(data[0]["name"], "Bolt")

    # Multiply suffix
    op, data, mod = _ops_tokenize('"Bolt" * 2')
    assert_eq(op, "*")
    assert_eq(mod, 2)
    assert_eq(data[0]["name"], "Bolt")

    # Divide
    op, data, mod = _ops_tokenize('/ 2 "Bolt"')
    assert_eq(op, "/")
    assert_eq(mod, 2)

    print("  [OK] Scale operator tests passed")


def test_tokenizer_priority():
    # Action-class priority
    op, data, mod = _ops_tokenize('* 2 "Bolt" + 1')
    assert_eq(op, "+")

    print("  [OK] Action-class priority tests passed")


def test_tokenizer_control():
    op, data, mod = _ops_tokenize('quit')
    assert_eq(op, "quit")

    op, data, mod = _ops_tokenize('list')
    assert_eq(op, "list")

    op, data, mod = _ops_tokenize('undo 3')
    assert_eq(op, "undo")
    assert_eq(mod, 3)

    op, data, mod = _ops_tokenize('')
    assert_eq(op, "empty")

    op, data, mod = _ops_tokenize('foo')
    assert_eq(op, "unknown")

    print("  [OK] Control command tests passed")


def test_remove_cards_default():
    sig = inspect.signature(remove_cards)
    default = sig.parameters['count'].default
    assert_eq(default, 1)
    print("  [OK] remove_cards default is 1")


def test_scale_cards_multiply_zero():
    source = inspect.getsource(scale_cards)
    assert "delta < 0" in source, "scale_cards should handle negative deltas"
    print("  [OK] scale_cards handles negative deltas")


def _add_cards_in_tmp(board, csv_filename):
    """Run add_cards in an isolated temp cube dir; return the written rows."""
    with tempfile.TemporaryDirectory() as d:
        csv_path = os.path.join(d, csv_filename)
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            csv.DictWriter(f, fieldnames=CUBECOBRA_CSV_COLUMNS).writeheader()
        orig = cube_manager.find_cube_dir
        cube_manager.find_cube_dir = lambda _id: d
        try:
            add_cards("dummy", ["Lightning Bolt"], board=board, verify=False)
        finally:
            cube_manager.find_cube_dir = orig
        with open(csv_path, encoding="utf-8") as f:
            return list(csv.DictReader(f))


def test_add_cards_sets_mainboard_board():
    rows = _add_cards_in_tmp("mainboard", "mainboard.csv")
    assert_eq(len(rows), 1)
    assert_eq(rows[0]["name"], "Lightning Bolt")
    assert_eq(rows[0]["board"], "mainboard", "stub must mark board=mainboard")
    assert_eq(rows[0]["maybeboard"], "false", "mainboard stub must have maybeboard=false")
    print("  [OK] add_cards sets board=mainboard on stub rows")


def test_add_cards_sets_maybeboard_board():
    rows = _add_cards_in_tmp("maybeboard", "maybeboard.csv")
    assert_eq(rows[0]["board"], "maybeboard", "stub must mark board=maybeboard")
    assert_eq(rows[0]["maybeboard"], "true", "maybeboard stub must have maybeboard=true")
    print("  [OK] add_cards sets board=maybeboard on maybeboard stub rows")


def run_all():
    tests = [
        test_parse_count_modifier,
        test_tokenizer_position_free,
        test_tokenizer_separator,
        test_tokenizer_equals,
        test_tokenizer_per_card_quantities,
        test_tokenizer_scale,
        test_tokenizer_priority,
        test_tokenizer_control,
        test_remove_cards_default,
        test_scale_cards_multiply_zero,
        test_add_cards_sets_mainboard_board,
        test_add_cards_sets_maybeboard_board,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  [FAIL] {test.__name__}: {type(e).__name__}: {e}")
            failed += 1

    print(f"\n{passed}/{passed+failed} tests passed")
    return failed == 0


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)
