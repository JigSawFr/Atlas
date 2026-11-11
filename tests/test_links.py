"""tools/links.py: each Wikidata item's ids on every platform, read from the
query's rows and written as its stores write them."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import links  # noqa: E402


def row(item, prop, value):
    return {"item": {"value": f"http://www.wikidata.org/entity/{item}"},
            "prop": {"value": f"http://www.wikidata.org/prop/direct/{prop}"}, "v": {"value": value}}


class Links(unittest.TestCase):
    def test_normal(self):
        self.assertEqual(links.normal("switch", "0100a1b2c3d4e000"), "0100A1B2C3D4E000")
        self.assertIsNone(links.normal("switch", "0100A1B2C3D4E800"))   # an update, not a game
        self.assertEqual(links.normal("xbox", "9zzzzzzzzzz1"), "9ZZZZZZZZZZ1")
        self.assertEqual(links.normal("gog", "game/amber_lantern"), "amber_lantern")
        self.assertEqual(links.normal("ps_product", "ep0001-ppsa00001_00-amberlantern0000"),
                         "EP0001-PPSA00001_00-AMBERLANTERN0000")
        for platform, bad in (("steam", "12a"), ("ps", ""), ("ps_product", "UP0001-CUSA00001_00"),
                              ("xbox", "http://www.wikidata.org/.well-known/genid/1f"), ("epic", "a b")):
            self.assertIsNone(links.normal(platform, bad), (platform, bad))

    def test_links(self):
        rows = [row("Q900001", "P11072", "0100a1b2c3d4e000"), row("Q900001", "P1733", "900010"),
                row("Q900001", "P1733", "900009"), row("Q900001", "P1733", "900010"),
                row("Q900001", "P5971", "EP0001-PPSA00001_00-AMBERLANTERN0000"),
                row("Q900001", "P6278", "amber-lantern"),
                row("Q12", "P5885", "9zzzzzzzzzz2"), row("Q12", "P2725", "game/pebble_pilots"),
                row("Q13", "P1733", "not an id"), row("L1", "P1733", "900011")]
        self.assertEqual(links.links(rows), {
            "Q12": {"xbox": ["9ZZZZZZZZZZ2"], "gog": ["pebble_pilots"]},
            "Q900001": {"switch": ["0100A1B2C3D4E000"], "steam": ["900009", "900010"],
                        "ps_product": ["EP0001-PPSA00001_00-AMBERLANTERN0000"], "epic": ["amber-lantern"]}})

    def test_also(self):
        games = {"Q1": {"switch": ["0100A1B2C3D4E000"], "steam": ["900010"], "ps_product": ["EP0001-PPSA00001_00-AMBERLANTERN0000"],
                        "xbox": ["9ZZZZZZZZZZ1"]},
                 "Q2": {"switch": ["0100A1B2C3D4F000", "0100A1B2C3D50000"], "gog": ["pebble_pilots"]},
                 "Q3": {"switch": ["0100A1B2C3D51000"]},                    # on no other store
                 "Q4": {"steam": ["900011"], "xbox": ["9ZZZZZZZZZZ2"]},     # not on the Switch
                 "Q5": {"switch": ["0100A1B2C3D52000"], "ps_product": ["EP0001-PPSA00001_00-AMBERLANTERN0000"]}}  # a store ALSO leaves out
        got = links.also(games)
        self.assertEqual(got, {"0100A1B2C3D4E000": {"steam": ["900010"], "xbox": ["9ZZZZZZZZZZ1"]},
                               "0100A1B2C3D4F000": {"gog": ["pebble_pilots"]},
                               "0100A1B2C3D50000": {"gog": ["pebble_pilots"]}})
        self.assertEqual(list(got), sorted(got))
        self.assertEqual(links.also({}), {})

    def test_also_file_matches_its_schema(self):
        import schemas
        body = {"schema": 1, "platform": "switch", "generated": "2026-11-11", "source": "x",
                "games": links.also({"Q1": {"switch": ["0100A1B2C3D4E000"], "steam": ["900010"], "epic": ["amber-lantern"]}})}
        self.assertEqual(schemas.errors(body, schemas.KINDS["also"]), [])
        self.assertEqual(schemas.kind_of("platforms/switch/also.json"), "also")
        bad = dict(body, games={"0100A1B2C3D4E000": {"steam": ["not a number"]}})
        self.assertNotEqual(schemas.errors(bad, schemas.KINDS["also"]), [])


if __name__ == "__main__":
    unittest.main()
