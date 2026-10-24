import unittest
from pathlib import Path

import klipper_macro_check as kmc
import wiki_tools

ROOT = Path(__file__).resolve().parent.parent
BSP = ROOT / "wiki" / "beispiele" / "klipper"
read = lambda n: (BSP / n).read_text(encoding="utf-8")


class Beispiele(unittest.TestCase):
    def test_alle_beispiele_sauber(self):
        for f in sorted(BSP.glob("*.cfg")):
            self.assertEqual(kmc.lint(f.read_text(encoding="utf-8")), [], f.name)

    def test_parameter_sind_strings_und_default(self):
        cfg = read("anteil_melden.cfg")
        self.assertEqual(kmc.render(cfg, "ANTEIL_MELDEN", {"anteil": 0.2})[0], ["M117 Anteil: 20%"])
        self.assertEqual(kmc.render(cfg, "ANTEIL_MELDEN")[0], ["M117 Anteil: 50%"])

    def test_bett_default_und_grenze(self):
        cfg = read("bett_vorheizen.cfg")
        self.assertEqual(kmc.render(cfg, "BETT_VORHEIZEN")[0], ["M140 S40.0"])
        with self.assertRaises(kmc.MacroError):
            kmc.render(cfg, "BETT_VORHEIZEN", {"TEMPERATUR": 500})

    def test_wischen_schleife(self):
        lines, _ = kmc.render(read("duese_wischen.cfg"), "DUESE_WISCHEN")
        self.assertEqual(sum(l.startswith("G1") for l in lines), 6)
        self.assertEqual(lines[0], "SAVE_GCODE_STATE NAME=wischen")
        self.assertEqual(lines[-1], "RESTORE_GCODE_STATE NAME=wischen")

    def test_variable_und_printer(self):
        cfg = read("bett_merken.cfg")
        printer = {"heater_bed": {"target": 60.0}, "gcode_macro BETT_MERKEN": {"gemerkt": 55.0}}
        self.assertIn("SET_GCODE_VARIABLE MACRO=BETT_MERKEN VARIABLE=gemerkt VALUE=60.0",
                      kmc.render(cfg, "BETT_MERKEN", printer=printer)[0])
        self.assertEqual(kmc.render(cfg, "BETT_ZURUECK", printer=printer)[0], ["M140 S55.0"])


class Lint(unittest.TestCase):
    def test_befunde(self):
        self.assertTrue(kmc.lint("[gcode_macro A1B]\ngcode:\n    G28\n"))
        self.assertTrue(kmc.lint("[gcode_macro X]\nvariable_Gross: 1\ngcode:\n    G28\n"))
        self.assertTrue(kmc.lint("[gcode_macro X]\ngcode:\n    {% if %}\n"))
        self.assertTrue(kmc.lint("[gcode_macro X]\nvariable_a: nope(\ngcode:\n    G28\n"))
        self.assertTrue(kmc.lint("[gcode_macro X]\ndescription: nur Text\n"))

    def test_kein_do(self):
        # Klipper aktiviert keine Jinja2-Extensions: {% do %} ist ein Syntaxfehler.
        self.assertTrue(kmc.lint("[gcode_macro X]\ngcode:\n    {% do 1 %}\n"))

    def test_notaus_und_meldung(self):
        cfg = "[gcode_macro X]\ngcode:\n    {action_respond_info('hallo')}\n    G28\n"
        lines, msgs = kmc.render(cfg, "X")
        self.assertEqual(msgs, [("info", "hallo")])


class Wiki(unittest.TestCase):
    def test_wiki_konsistent(self):
        self.assertEqual(wiki_tools.validate(ROOT), [])

    def test_validator_erkennt_fehler(self):
        errs = wiki_tools.validate(ROOT, source_ids=set())
        self.assertTrue(any("unbekannte Quelle" in e for e in errs))


if __name__ == "__main__":
    unittest.main()
