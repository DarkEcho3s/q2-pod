#!/usr/bin/env python3
"""Run the *compiled MIPS code*, plus binary-patch rejection tests.

The adapter harness stubs toolkit services; it is not device/GUI emulation.
Pass --build work/<build> --stock-demo <original M1 demo>.
"""
import argparse
import copy
import io
import json
from pathlib import Path
import struct
import sys
import unittest

from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS32, UC_MODE_LITTLE_ENDIAN, UC_HOOK_CODE
from unicorn.mips_const import (UC_MIPS_REG_SP, UC_MIPS_REG_RA, UC_MIPS_REG_PC,
                                UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2,
                                UC_MIPS_REG_A3, UC_MIPS_REG_V0, UC_MIPS_REG_GP)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import build_m1plus as build

DOWN, LONG, UP = 0x10f, 0x110, 0x113
POWER, VOL_UP, VOL_DOWN = 210, 220, 221
PASS, DROP, PREV, NEXT, CONFIRM = range(5)
BUILD = STOCK = None
DATA, STACK, STOP = 0x1000000, 0x101f000, 0x101e000
STATE, CONTEXT, EVENT = DATA, DATA+0x100, DATA+0x200
WM, MENU, OTHER = DATA+0x1000, DATA+0x2000, DATA+0x3000


class Machine:
    def __init__(self, vendor=False):
        self.u = Uc(UC_ARCH_MIPS, UC_MODE_MIPS32 | UC_MODE_LITTLE_ENDIAN)
        self.u.mem_map(DATA, 0x20000)
        self.u.mem_map(0xb00000, 0x100000)
        elf = ELFFile(io.BytesIO((BUILD/'payload.elf').read_bytes()))
        self.syms = {s.name: s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
        for s in elf.iter_sections():
            if s['sh_flags'] & 2 and s['sh_type'] != 'SHT_NOBITS':
                self.u.mem_write(s['sh_addr'], s.data())
        if vendor:
            self.u.mem_map(0x400000, 0x700000)
            e = ELFFile(io.BytesIO((BUILD/'demo.m1pod').read_bytes()))
            for s in e.iter_segments():
                if s['p_type'] == 'PT_LOAD' and s['p_vaddr'] < 0xb00000:
                    self.u.mem_write(s['p_vaddr'], s.data())

    def word(self, address, value=None):
        if value is None:
            return struct.unpack('<I', self.u.mem_read(address, 4))[0]
        self.u.mem_write(address, struct.pack('<I', value))

    def call(self, function, *args):
        address = self.syms[function] if isinstance(function, str) else function
        for r, v in [(UC_MIPS_REG_SP, STACK), (UC_MIPS_REG_RA, STOP),
                     *zip([UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2, UC_MIPS_REG_A3], args)]:
            self.u.reg_write(r, v)
        self.u.emu_start(address, STOP, count=50000)
        if self.u.reg_read(UC_MIPS_REG_PC) != STOP:
            raise AssertionError('MIPS function did not return within instruction budget')
        if self.u.reg_read(UC_MIPS_REG_SP) != STACK:
            raise AssertionError('MIPS stack pointer was not restored')
        return self.u.reg_read(UC_MIPS_REG_V0)

    def route(self, event, key, **overrides):
        ctx = dict(page=1, generation=1, enabled=1, awake=1, unlocked=1, stable=1, reversed=0)
        ctx.update(overrides)
        self.u.mem_write(CONTEXT, struct.pack('<7I', *ctx.values()))
        return self.call('m1_route', STATE, CONTEXT, event, key)


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.m = Machine()

    def test_menu_click_confirms_only_on_release(self):
        self.assertEqual(self.m.route(DOWN, POWER), PASS)
        self.assertEqual(self.m.route(UP, POWER), CONFIRM)
        self.assertEqual(self.m.route(UP, POWER), PASS)

    def test_wheel_directions_and_rotation(self):
        for rev in [0, 1]:
            for key, normal in [(VOL_UP, PREV), (VOL_DOWN, NEXT)]:
                with self.subTest(reversed=rev, key=key):
                    self.assertEqual(self.m.route(DOWN, key, reversed=rev), PASS)
                    self.assertEqual(self.m.route(UP, key, reversed=rev),
                                     normal if not rev else (NEXT if normal == PREV else PREV))

    def test_now_playing_and_other_unregistered_pages_keep_volume(self):
        for key in [POWER, VOL_UP, VOL_DOWN]:
            self.assertEqual(self.m.route(DOWN, key, page=0), PASS)
            self.assertEqual(self.m.route(UP, key, page=0), PASS)

    def test_disabled_locked_sleep_transition_passthrough(self):
        for field in ['enabled', 'awake', 'unlocked', 'stable']:
            for key in [POWER, VOL_UP, VOL_DOWN]:
                with self.subTest(field=field, key=key):
                    self.assertEqual(self.m.route(DOWN, key, **{field: 0}), PASS)
                    self.assertEqual(self.m.route(UP, key, **{field: 0}), PASS)

    def test_wake_click_cannot_confirm(self):
        self.m.route(DOWN, POWER, awake=0)
        self.assertEqual(self.m.route(UP, POWER, awake=1), PASS)

    def test_power_long_hold_and_release_reach_stock(self):
        self.m.route(DOWN, POWER)
        self.assertEqual(self.m.route(LONG, POWER), PASS)
        self.assertEqual(self.m.route(UP, POWER, page=0, stable=0), PASS)

    def test_repeated_down_does_not_steal_original_owner(self):
        self.m.route(DOWN, POWER, page=0)
        self.m.route(DOWN, POWER)
        self.assertEqual(self.m.route(UP, POWER), PASS)

    def test_menu_press_cancelled_after_context_change(self):
        for change in [dict(page=2), dict(generation=2), dict(enabled=0), dict(awake=0),
                       dict(unlocked=0), dict(stable=0)]:
            for key in [POWER, VOL_UP, VOL_DOWN]:
                self.m.route(DOWN, key)
                self.assertEqual(self.m.route(UP, key, **change), DROP)

    def test_observed_interruption_remains_cancelled(self):
        self.m.route(DOWN, POWER)
        self.m.route(DOWN, POWER, page=0)
        self.assertEqual(self.m.route(UP, POWER), DROP)

    def test_playback_buttons_and_unknown_events_passthrough(self):
        for key in [0, 212, 213, 214, 215, 999]:
            for event in [DOWN, LONG, UP, 0xff]:
                self.assertEqual(self.m.route(event, key), PASS)

    def test_unpaired_release_and_long_press_do_not_activate(self):
        for key in [POWER, VOL_UP, VOL_DOWN]:
            self.assertEqual(self.m.route(LONG, key), PASS)
            self.assertEqual(self.m.route(UP, key), PASS)

    def test_independent_keys(self):
        self.m.route(DOWN, POWER)
        self.m.route(DOWN, VOL_DOWN)
        self.assertEqual(self.m.route(UP, VOL_DOWN), NEXT)
        self.assertEqual(self.m.route(UP, POWER, generation=2), DROP)

    def test_touch_cancels_owned_press_but_preserves_power_hold(self):
        self.m.route(DOWN, POWER)
        self.m.call('m1_cancel_owned', STATE)
        self.assertEqual(self.m.route(UP, POWER), DROP)
        self.m.route(DOWN, POWER)
        self.m.call('m1_cancel_owned', STATE)
        self.m.route(LONG, POWER)
        self.assertEqual(self.m.route(UP, POWER), PASS)


class PatchTests(unittest.TestCase):
    def setUp(self):
        self.target = json.loads(build.TARGET.read_text())
        self.raw = STOCK.read_bytes()

    def test_rebuild_matches_manifest_and_patch_allowlist(self):
        payload, syms = build.payload_image(BUILD/'payload.elf', self.target['payload_base'])
        raw, changes = build.patch(self.raw, payload, syms, self.target)
        manifest = json.loads((BUILD/'manifest.json').read_text())
        self.assertEqual(raw, (BUILD/'demo.m1pod').read_bytes())
        self.assertEqual(build.sha(raw), manifest['demo_sha256'])
        self.assertEqual(build.sha(payload), manifest['payload_sha256'])
        self.assertEqual(len(changes), 4)

    def test_rejects_other_or_modified_firmware(self):
        for raw in [b'', b'Q2 firmware', self.raw[:-1], b'X'+self.raw[1:]]:
            with self.assertRaisesRegex(ValueError, 'pinned M1'):
                build.validate_stock(raw, self.target)

    def test_rejects_bad_symbol_prologue_and_abi(self):
        variants = []
        t = copy.deepcopy(self.target); t['symbols']['application_init']['address'] += 4; variants.append(t)
        t = copy.deepcopy(self.target); t['hooks']['application_init']['prologue'] = '00'*12; variants.append(t)
        t = copy.deepcopy(self.target); t['elf_flags'] = 0; variants.append(t)
        for target in variants:
            with self.assertRaises(ValueError): build.validate_stock(self.raw, target)

    def test_rejects_overlap_and_bad_jump_destination(self):
        payload, syms = build.payload_image(BUILD/'payload.elf', self.target['payload_base'])
        t = copy.deepcopy(self.target); t['payload_base'] = 0x400000
        with self.assertRaisesRegex(ValueError, 'overlaps'):
            build.patch(self.raw, payload, syms, t)
        syms['m1_dispatch'] = 0x1000
        with self.assertRaisesRegex(ValueError, 'destination'):
            build.patch(self.raw, payload, syms, self.target)

    def test_hook_and_trampoline_machine_code(self):
        for name, hook in self.target['hooks'].items():
            m = Machine(vendor=True)
            address = self.target['symbols'][name]['address']
            destination = m.syms[hook['replacement']]
            m.u.reg_write(UC_MIPS_REG_SP, STACK)
            m.u.emu_start(address, destination, count=16)
            self.assertEqual(m.u.reg_read(UC_MIPS_REG_PC), destination)
            self.assertEqual(m.u.reg_read(UC_MIPS_REG_SP), STACK)
            m.u.reg_write(UC_MIPS_REG_GP, 0xdeadbeef)
            m.u.emu_start(m.syms['stock_'+name], address+12, count=16)
            self.assertEqual(m.u.reg_read(UC_MIPS_REG_PC), address+12)
            self.assertEqual(m.u.reg_read(UC_MIPS_REG_GP), self.target['stock_gp'])


class AdapterTests(unittest.TestCase):
    """Execute real patched entry points; fake the stock toolkit's services.

    The dispatcher stub calls the real patched keyup entry, with a stock-volume
    sentinel after its trampoline. This catches lost/double release suppression.
    It cannot prove what physical wheel events the player produces.
    """
    def setUp(self):
        self.m = m = Machine(vendor=True)
        self.t = json.loads(build.TARGET.read_text())
        self.top, self.native_releases, self.opened = MENU, 0, []
        self.force_volume_change = False
        self.io_failure, self.renamed = None, False
        self.address = {n: v['address'] for n, v in self.t['symbols'].items()}
        m.word(m.syms['menu'], MENU)
        m.word(m.syms['wheel_enabled'], 1)
        m.word(self.address['volume'], 10)
        m.u.mem_write(self.address['backlight_status'], b'\1')
        # A synthetic dispatcher body: call widget_on_keyup then return.
        stub = [0x27bdffe0, 0xafbf001c, 0x0c000000 | (self.address['widget_on_keyup'] >> 2),
                0, 0x8fbf001c, 0x03e00008, 0x27bd0020]
        self.stub = DATA+0x4000
        m.u.mem_write(self.stub, struct.pack('<7I', *stub))
        m.u.hook_add(UC_HOOK_CODE, self.intercept)

    def returned(self, value=0):
        self.m.u.reg_write(UC_MIPS_REG_V0, value)
        self.m.u.reg_write(UC_MIPS_REG_PC, self.m.u.reg_read(UC_MIPS_REG_RA))

    def intercept(self, u, pc, size, unused):
        a = self.address
        io_returns = {'fopen': DATA+0x5000, 'fwrite': 2, 'fflush': 0, 'fileno': 3,
                      'fsync': 0, 'fclose': 0, 'rename': 0}
        for name, value in io_returns.items():
            if pc == self.m.syms['m1_lib_'+name]:
                if name == 'rename': self.renamed = True
                if name == self.io_failure: value = 0 if name in ['fopen', 'fwrite'] else 0xffffffff
                self.returned(value)
                return
        if pc == a['window_manager']: self.returned(WM)
        elif pc == a['window_manager_get_top_window']: self.returned(self.top)
        elif pc == a['window_manager_is_animating']: self.returned(0)
        elif pc in [a[n] for n in ['widget_set_prop_str', 'widget_set_state',
                                   'widget_set_text_utf8', 'reset_poweroptions_timer']]: self.returned(0)
        elif pc == a['navigator_to']:
            ptr = u.reg_read(UC_MIPS_REG_A0)
            self.opened.append(bytes(u.mem_read(ptr, 64)).split(b'\0')[0])
            self.returned(0)
        elif pc == a['window_manager_dispatch_input_event']+12:
            event = u.reg_read(UC_MIPS_REG_A1)
            if self.force_volume_change: self.m.word(a['volume'], 11)
            if self.m.word(event) == UP: u.reg_write(UC_MIPS_REG_PC, self.stub)
            else: self.returned(0)
        elif pc == a['widget_on_keyup']+12:
            self.native_releases += 1
            event = u.reg_read(UC_MIPS_REG_A1)
            if self.m.word(event+24) in [VOL_UP, VOL_DOWN]:
                self.m.word(a['volume'], self.m.word(a['volume'])+1)
            self.returned(0)
        elif pc == a['on_wm_keylong_fun']+12: self.returned(0)

    def event(self, kind, key):
        self.m.u.mem_write(EVENT, bytes(40))
        self.m.word(EVENT, kind); self.m.word(EVENT+4, 40); self.m.word(EVENT+24, key)
        name = 'on_wm_keylong_fun' if kind == LONG else 'window_manager_dispatch_input_event'
        return self.m.call(self.address[name], WM, EVENT)

    def test_menu_scroll_has_no_stock_release_or_volume_change(self):
        self.event(DOWN, VOL_DOWN); self.event(UP, VOL_DOWN)
        self.assertEqual(self.native_releases, 0)
        self.assertEqual(self.m.word(self.address['volume']), 10)
        self.assertEqual(self.m.word(self.m.syms['selected']), 1)

    def test_confirm_executes_once(self):
        self.event(DOWN, POWER); self.event(UP, POWER)
        self.assertEqual(self.opened, [b'localclass_page'])
        self.assertEqual(self.native_releases, 0)

    def test_now_playing_passes_wheel_to_stock(self):
        self.top = OTHER
        self.event(DOWN, VOL_DOWN); self.event(UP, VOL_DOWN)
        self.assertEqual(self.native_releases, 1)
        self.assertEqual(self.m.word(self.address['volume']), 11)
        self.assertEqual(self.m.word(self.m.syms['selected']), 0)

    def test_long_hold_keeps_stock_release(self):
        self.event(DOWN, POWER); self.event(LONG, POWER); self.event(UP, POWER)
        self.assertEqual(self.native_releases, 1)
        self.assertEqual(self.opened, [])

    def test_page_change_consumes_release_without_selection(self):
        self.event(DOWN, POWER); self.top = OTHER; self.event(UP, POWER)
        self.assertEqual(self.native_releases, 0)
        self.assertEqual(self.opened, [])

    def test_touch_cancels_pending_confirmation(self):
        self.event(DOWN, POWER); self.event(0xff, 0); self.event(UP, POWER)
        self.assertEqual(self.native_releases, 0)
        self.assertEqual(self.opened, [])

    def test_unexpected_volume_path_disables_navigation(self):
        self.event(DOWN, VOL_DOWN)
        self.force_volume_change = True
        self.event(UP, VOL_DOWN)
        self.assertEqual(self.m.word(self.m.syms['wheel_enabled']), 0)
        self.assertEqual(self.m.word(self.m.syms['selected']), 0)

    def test_toggle_changes_only_after_successful_persistence(self):
        self.m.call('activate', 4)
        self.assertTrue(self.renamed)
        self.assertEqual(self.m.word(self.m.syms['wheel_enabled']), 0)

    def test_failed_flush_does_not_commit_toggle(self):
        self.io_failure = 'fsync'
        self.m.call('activate', 4)
        self.assertFalse(self.renamed)
        self.assertEqual(self.m.word(self.m.syms['wheel_enabled']), 1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--stock-demo', type=Path, required=True)
    args, remaining = parser.parse_known_args()
    BUILD, STOCK = args.build.resolve(), args.stock_demo.resolve()
    unittest.main(argv=[sys.argv[0], *remaining])
