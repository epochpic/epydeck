from epydeck import dumps, loads

from textwrap import dedent


def test_basic_block():
    expected = dedent(
        """\
        begin:block
          a = 1
          b = 2.3
          c = electron
          d = 10 * femto
          e = F
          f = T
        end:block

        """
    )

    deck = {
        "block": {
            "a": 1,
            "b": 2.3,
            "c": "electron",
            "d": "10 * femto",
            "e": False,
            "f": True,
        }
    }
    result = dumps(deck)

    assert expected == result


def test_repeated_line():
    expected = dedent(
        """\
        begin:block
          a = 1
          b = 2
          c = 3
          c = 4
        end:block

        """
    )

    deck = {"block": {"a": 1, "b": 2, "c": [3, 4]}}
    result = dumps(deck)

    assert expected == result


def test_repeated_block():
    expected = dedent(
        """\
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
    )

    deck = {
        "block": {
            "first": {"name": "first", "a": 1, "b": 2, "c": 3},
            "second": {"name": "second", "a": 4, "b": 5, "c": 6},
        }
    }
    result = dumps(deck)

    assert expected == result


def test_include_species():
    expected = dedent(
        """\
        begin:dist_fn
          a = 1
          include_species: electron
          include_species: proton
        end:dist_fn
    
        """
    )

    deck = {"dist_fn": {"a": 1, "include_species": ["electron", "proton"]}}
    result = dumps(deck)

    assert expected == result
