import epydeck

import pathlib


def test_basic_block():
    text = """
    begin:block
      a = 1
      b = 2e3
      c = electron
      d = 10 * femto
      e = F
      f = T
    end:block
    """

    data = epydeck.loads(text)

    expected = {
        "block": {
            "a": 1,
            "b": 2e3,
            "c": "electron",
            "d": "10 * femto",
            "e": False,
            "f": True,
        }
    }

    assert expected == data


def test_repeated_line():
    text = """
    begin:block
      a = 1
      b = 2
      c = 3
      c = 4
    end:block
    """

    data = epydeck.loads(text)

    expected = {"block": {"a": 1, "b": 2, "c": [3, 4]}}

    assert expected == data


def test_repeated_block():
    text = """
    begin:block
      name = first
      a = 1
      b = 2
      c = 3
    end:block

    begin:block
      name = second
      a = 4
      b = 5
      c = 6
    end:block
    """

    data = epydeck.loads(text)

    expected = {
        "block": {
            "first": {"name": "first", "a": 1, "b": 2, "c": 3},
            "second": {"name": "second", "a": 4, "b": 5, "c": 6},
        }
    }

    assert expected == data


def test_include_species():
    text = """
    begin:dist_fn
      a = 1
      include_species:Electron
      include_species:Proton
    end:dist_fn
    """

    data = epydeck.loads(text)

    expected = {"dist_fn": {"a": 1, "include_species": ["Electron", "Proton"]}}

    assert expected == data


def test_include_identify():
    text = """
    begin:dist_fn
      a = 1
      identify:Electron
      identify:Proton
    end:dist_fn
    """

    data = epydeck.loads(text)

    expected = {"dist_fn": {"a": 1, "identify": ["Electron", "Proton"]}}

    assert expected == data


def test_read_file():
    filename = pathlib.Path(__file__).parent / "cone.deck"

    with open(filename) as f:
        data = epydeck.load(f)

    assert "control" in data
    assert "species" in data
    assert "proton" in data["species"]
    assert "electron" in data["species"]


def test_include_identify_with_spaces():
    text = """
    begin:dist_fn
      a = 1
      identify: Electron
      identify : Proton
    end:dist_fn
    """

    data = epydeck.loads(text)

    expected = {"dist_fn": {"a": 1, "identify": ["Electron", "Proton"]}}

    assert expected == data