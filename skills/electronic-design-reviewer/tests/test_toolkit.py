#!/usr/bin/env python3
"""Regression tests for the electronic-design-reviewer toolkit (standard library only).

Run from the toolkit folder:   python3 tests/test_toolkit.py
Add a test here whenever the learning loop strengthens a check ("check-too-weak" escapes),
so the fix can never silently regress.
"""
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = os.path.join(ROOT, 'scripts')
FX = os.path.join(ROOT, 'tests', 'fixtures')
EV = os.path.join(ROOT, 'evals')


def run(script, *args):
    out = subprocess.run([sys.executable, os.path.join(S, script), *args], capture_output=True, text=True)
    if out.returncode != 0:
        raise AssertionError(f"{script} {' '.join(args)} failed:\n{out.stderr}")
    return out.stdout


def lint(path, *extra):
    d = json.loads(run('netlist_lint.py', path, '--json', '-', *extra))
    return d, {(l['rule'], l['check']) for l in d['leads']}


def pcb(path, *extra):
    d = json.loads(run('pcb_check.py', path, '--json', '-', *extra))
    return d, {(l['rule'], l['check']) for l in d['leads']}


def calc(*args):
    return json.loads(run('ee_calc.py', '--json', *args))['results']


SEEDED_NETLIST = {
    ('SCH-03', 'polarized_cap_reversed'), ('SCH-08', 'no_flyback'), ('SCH-01', 'single_pin_net'),
    ('SCH-04', 'name_variants'), ('SCH-05', 'ground_split'), ('SCH-07', 'no_decoupling'),
    ('SCH-15', 'floating_input'), ('SCH-16', 'missing_multiplier'), ('SCH-17', 'dnp_mismatch'),
    ('CMP-04', 'cap_margin'), ('CMP-03', 'dc_bias'), ('SCH-13', 'no_ground_tp'), ('SCH-16', 'cap_no_unit'),
    ('SCH-04', 'generic_rail_names'), ('LAY-20', 'missing_order_codes'),
}
SEEDED_BOARD = {
    ('LAY-06', 'traces_on_l2'), ('LAY-14', 'shared_ground_via'), ('LAY-14', 'ground_pad_no_via'),
    ('LAY-14', 'pour_no_near_via'), ('PLC-02', 'decap_far'), ('LAY-17', 'few_fiducials'),
    ('LAY-17', 'no_local_fiducials'), ('MECH-02', 'no_mounting_holes'), ('LAY-19', 'layer_markers'),
    ('LAY-08', 'via_ring'), ('LAY-08', 'thin_track'), ('PLC-04', 'inductor_proximity'),
    ('LAY-07', 'floating_copper'), ('LAY-24', 'pads_without_paste'),
}


class NetlistLint(unittest.TestCase):
    def test_seeded_kicad_sexpr(self):
        d, got = lint(os.path.join(EV, 'full-review-seeded-netlist', 'files', 'sensor_node.net'))
        self.assertTrue(SEEDED_NETLIST <= got, SEEDED_NETLIST - got)
        self.assertEqual(len(d['leads']), 21)
        self.assertNotIn('check_errors', d['info'])

    def test_formats_agree(self):
        _, a = lint(os.path.join(EV, 'full-review-seeded-netlist', 'files', 'sensor_node.net'))
        _, b = lint(os.path.join(FX, 'sensor_node.xml'))
        _, c = lint(os.path.join(FX, 'sensor_node_pins.csv'), '--bom', os.path.join(FX, 'sensor_node_bom.csv'))
        self.assertEqual(a, b)
        self.assertEqual(a, c)

    def test_no_false_positive_on_decoupled_caps(self):
        d, _ = lint(os.path.join(EV, 'full-review-seeded-netlist', 'files', 'sensor_node.net'))
        polar = [l for l in d['leads'] if l['check'].startswith('polarized') and set(l['refs']) & {'C3', 'C6', 'C7', 'C9'}]
        self.assertEqual(polar, [])

    def test_contact_switched_pump(self):
        _, got = lint(os.path.join(EV, 'relay-reset-escape-learning', 'files', 'relay_board.net'))
        self.assertIn(('EXP-DRV-05', 'contact_load_no_suppression'), got)
        self.assertNotIn(('SCH-16', 'missing_multiplier'), got)      # 100 ohm gate resistor is fine

    def test_transistor_switched_motor(self):
        _, got = lint(os.path.join(FX, 'motor_pins.csv'), '--bom', os.path.join(FX, 'motor_bom.csv'))
        self.assertIn(('SCH-08', 'load_no_flyback'), got)

    def test_pcb_as_netlist(self):
        d, _ = lint(os.path.join(FX, 'seeded_board.kicad_pcb'))
        self.assertEqual(d['format'], 'pcb')
        self.assertGreater(d['stats']['nets'], 2)


class PcbCheck(unittest.TestCase):
    def test_seeded_board(self):
        d, got = pcb(os.path.join(FX, 'seeded_board.kicad_pcb'))
        self.assertEqual(got, SEEDED_BOARD)
        gp = d['info']['ground_pads']
        self.assertEqual((gp['own_via'], gp['shared'], gp['pour_far'], gp['no_via']), (4, 1, 1, 1))

    def test_net_names_instead_of_codes(self):
        _, a = pcb(os.path.join(FX, 'seeded_board.kicad_pcb'))
        _, b = pcb(os.path.join(FX, 'seeded_board_netnames.kicad_pcb'))
        self.assertEqual(a, b)

    def test_ir_drop(self):
        d, _ = pcb(os.path.join(FX, 'seeded_board.kicad_pcb'), '--ir', 'VBUS', 'J1.1', 'U3.1', '--current', '2')
        self.assertAlmostEqual(d['info']['ir_path']['r_ohm'], 0.11575, places=4)


class Calculators(unittest.TestCase):
    def test_rc(self):
        r = calc('rc', '--r', '100k', '--c', '10u', '--ceff', '3.3u')
        self.assertAlmostEqual(r['tau_s'], 1.0)
        self.assertAlmostEqual(r['tau_eff_s'], 0.33)

    def test_trace_width_ipc2221(self):
        self.assertAlmostEqual(calc('trace-width', '--i', '1', '--dt', '10')['width_mm'], 0.302, places=2)

    def test_microstrip(self):
        self.assertAlmostEqual(calc('microstrip', '--h', '0.21', '--er', '4.4', '--w', '0.35')['z0'], 49.9, places=0)

    def test_via_guide_fit(self):
        self.assertAlmostEqual(calc('via', '--h', '0.38')['l_guide_ph'], 45, delta=1)
        self.assertAlmostEqual(calc('via', '--h', '1.6')['l_guide_ph'], 501, delta=2)

    def test_i2c(self):
        r = calc('i2c-pullup', '--vdd', '3.3', '--cb', '100p', '--mode', 'fast')
        self.assertAlmostEqual(r['rmin'], 966.7, places=0)
        self.assertAlmostEqual(r['rmax'], 3541, delta=2)

    def test_flyback_and_hotplug(self):
        f = calc('flyback', '--i', '30m', '--l', '100m', '--cpar', '50p', '--r', '400', '--vsup', '12')
        self.assertAlmostEqual(f['v_peak_noclamp'], 1344, delta=5)
        self.assertAlmostEqual(f['t_decay_diode_s'], 0.693e-3, delta=0.01e-3)
        h = calc('hotplug', '--v', '12', '--l', '1u', '--r', '0.05', '--c', '10u', '--esr', '5m')
        self.assertAlmostEqual(h['v_peak'], 21.1, delta=0.1)

    def test_pulse_sag(self):
        r = calc('pulse-sag', '--vcell', '3', '--rint', '20', '--i', '15m', '--t', '3m', '--c', '100u', '--esr', '0.1')
        self.assertAlmostEqual(r['v_min_cap'], 2.767, places=3)

    def test_mlcc_screen(self):
        self.assertEqual(calc('mlcc', '--c', '10u', '--vrated', '6.3', '--vbias', '5', '--dielectric', 'X5R',
                              '--size', '0603')['risk'], 'HIGH')
        self.assertEqual(calc('mlcc', '--c', '22p', '--vrated', '50', '--vbias', '5', '--dielectric', 'C0G')['risk'], 'NONE')


class Compliance(unittest.TestCase):
    PACK = os.path.join(ROOT, 'references', 'guide-rosenberg-v5.md')

    def test_rule_count(self):
        t = json.loads(run('compliance_score.py', '--rules', self.PACK, '--stage', 'release', '--template'))
        self.assertEqual(len(t['rules']), 95)

    def test_precedence_and_custom_ids(self):
        t = json.loads(run('compliance_score.py', '--rules', os.path.join(FX, 'acme_pack.md'), '--rules', self.PACK,
                           '--stage', 'placement', '--template'))
        ids = [r['id'] for r in t['rules']]
        self.assertIn('ACME-PLC-01', ids)
        self.assertEqual(ids.count('SCH-05'), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
