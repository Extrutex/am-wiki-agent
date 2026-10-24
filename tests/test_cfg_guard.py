import unittest

from am_agent import cfg_guard as g

CFG = """\
[mcu]
serial: /dev/serial/by-id/usb-Klipper_stm32-if00

[stepper_x]
step_pin: PB13
dir_pin: !PB12
enable_pin: !PB14
microsteps: 16
rotation_distance: 40
endstop_pin: ^PC0

[heater_bed]
heater_pin: PA3
sensor_pin: PC4
control: pid

[output_pin led]
pin: PA8

[gcode_macro TEST]
variable_a_pin: 1
gcode:
    M117 hallo
    {% set x = 1 %}

#*# <---- SAVE_CONFIG ---->
#*# DO NOT EDIT THIS BLOCK OR BELOW. The contents are auto-generated.
#*#
#*# [stepper_x]
#*# position_endstop = 0.5
"""


def aend(neu, alt=CFG):
    return g.pin_aenderungen(alt, neu)


class Erkennung(unittest.TestCase):
    def test_unveraendert_und_erlaubte_aenderungen(self):
        self.assertEqual(aend(CFG), [])
        self.assertEqual(aend(CFG.replace("microsteps: 16", "microsteps: 32")), [])
        self.assertEqual(aend(CFG.replace("control: pid", "control: watermark")), [])
        self.assertEqual(aend(CFG.replace("hallo", "welt")), [])
        self.assertEqual(aend(CFG.replace("PB13", "PB13  # step")), [])  # nur Kommentar
        self.assertEqual(aend(CFG.replace("step_pin:", "step_pin :")), [])

    def test_pin_wert_geaendert(self):
        r = aend(CFG.replace("step_pin: PB13", "step_pin: PB10"))
        self.assertEqual([(a.art, a.schluessel, a.alt, a.neu) for a in r], [("geaendert", "step_pin", "PB13", "PB10")])

    def test_invertierung_und_pullup_zaehlen(self):
        self.assertEqual(len(aend(CFG.replace("dir_pin: !PB12", "dir_pin: PB12"))), 1)
        self.assertEqual(len(aend(CFG.replace("endstop_pin: ^PC0", "endstop_pin: PC0"))), 1)

    def test_alle_pin_arten(self):
        for alt, neu in [("heater_pin: PA3", "heater_pin: PA4"), ("sensor_pin: PC4", "sensor_pin: PC5"),
                         ("pin: PA8", "pin: PA9"), ("enable_pin: !PB14", "enable_pin: PB14"),
                         ("serial: /dev/serial/by-id/usb-Klipper_stm32-if00", "serial: /dev/ttyACM0")]:
            self.assertEqual(len(aend(CFG.replace(alt, neu))), 1, alt)

    def test_entfernt_und_hinzugefuegt(self):
        r = aend(CFG.replace("enable_pin: !PB14\n", ""))
        self.assertEqual(r[0].art, "entfernt")
        r = aend(CFG + "\n[fan]\npin: PA0\n")
        self.assertEqual(r[0].art, "hinzugefuegt")

    def test_sektion_umbenennen_ist_aenderung(self):
        self.assertTrue(aend(CFG.replace("[stepper_x]\nstep_pin", "[stepper_y]\nstep_pin")))

    def test_schluessel_gross_geschrieben_und_gleichheitszeichen(self):
        self.assertEqual(len(aend(CFG.replace("step_pin: PB13", "STEP_PIN = PB10"))), 1)

    def test_kommentar_trick_umgeht_nicht(self):
        # Original-Pin wird auskommentiert und ein neuer gesetzt
        neu = CFG.replace("step_pin: PB13", "#step_pin: PB13\nstep_pin: PB1")
        self.assertEqual(len(aend(neu)), 1)
        # Pin nur auskommentiert = entfernt
        self.assertEqual(aend(CFG.replace("step_pin: PB13", "#step_pin: PB13"))[0].art, "entfernt")

    def test_include_und_board_pins(self):
        self.assertEqual(len(aend(CFG + "\n[include extra.cfg]\n")), 1)
        base = CFG + "\n[board_pins]\naliases: a=PA1\n"
        self.assertEqual(len(aend(base.replace("a=PA1", "a=PA2"), alt=base)), 1)

    def test_save_config_block_ist_geschuetzt(self):
        neu = CFG + "#*#\n#*# [stepper_y]\n#*# step_pin = PB1\n"
        self.assertEqual(len(aend(neu)), 1)

    def test_fortsetzungszeile(self):
        alt = "[multi_pin x]\npins:\n    PA1,\n    PA2\n"
        self.assertEqual(g.pin_aenderungen(alt, alt.replace("PA2", "PA3"))[0].art, "geaendert")

    def test_makro_inhalt_wird_nicht_als_schluessel_gelesen(self):
        neu = CFG.replace("M117 hallo", "M117 hallo\n    foo_pin: PA1")
        self.assertEqual(aend(neu), [])  # eingerueckt = Teil von gcode

    def test_zeilenende_windows(self):
        self.assertEqual(aend(CFG.replace("\n", "\r\n")), [])


class Bestaetigung(unittest.TestCase):
    def test_satz(self):
        for ok in ("Ich weiss was ich tue", "  ich WEISS was ich tue. ", "Ich weiß, was ich tue".replace(",", "")):
            self.assertTrue(g.bestaetigt(ok), ok)
        for nein in ("", None, "ja", "ich weiss was ich tue nicht", "ok"):
            self.assertFalse(g.bestaetigt(nein), nein)


class Diff(unittest.TestCase):
    def test_diff(self):
        d = g.diff(CFG, CFG.replace("microsteps: 16", "microsteps: 32"))
        self.assertIn("-microsteps: 16", d)
        self.assertIn("+microsteps: 32", d)
        self.assertEqual(g.diff(CFG, CFG), "")


if __name__ == "__main__":
    unittest.main()
