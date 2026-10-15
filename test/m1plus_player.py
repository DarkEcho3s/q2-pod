#!/usr/bin/env python3
"""Execute the compiled M1 audio payload in a MIPS emulator with bounded I/O.

This checks target addresses, DSP and filter behavior; it does not emulate the
DAC, Linux audio drivers, Bluetooth or the physical player.
"""
import argparse
import io
import json
import math
from pathlib import Path
import struct
import sys
import unittest

from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS32, UC_MODE_LITTLE_ENDIAN, UC_HOOK_CODE
import unicorn.mips_const as r

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import build_m1plus_player as build
from build_m1plus import payload_image

BUILD = STOCK = None
DATA, STOP, STACK = 0x1000000, 0x11e0000, 0x11f0000


class Machine:
    def __init__(self):
        self.u = Uc(UC_ARCH_MIPS, UC_MODE_MIPS32 | UC_MODE_LITTLE_ENDIAN)
        self.u.ctl_set_cpu_model(r.UC_CPU_MIPS32_P5600)
        self.u.reg_write(r.UC_MIPS_REG_CP0_STATUS,
                         self.u.reg_read(r.UC_MIPS_REG_CP0_STATUS) | 0x24000000)  # CU1 and FR
        self.u.mem_map(0x400000, 0xb00000)
        self.u.mem_map(DATA, 0x200000)
        for path in (BUILD/'hciplayer', BUILD/'payload.elf'):
            e = ELFFile(io.BytesIO(path.read_bytes()))
            for s in e.iter_segments():
                if s['p_type'] == 'PT_LOAD':
                    self.u.mem_write(s['p_vaddr'], s.data())
        e = ELFFile(io.BytesIO((BUILD/'payload.elf').read_bytes()))
        self.syms = {s.name: s['st_value'] for s in e.get_section_by_name('.symtab').iter_symbols()}
        self.manifest = json.loads((BUILD/'manifest.json').read_text())
        self.heap, self.calls, self.stock_calls = DATA+0x40000, [], []
        self.callbacks = {}
        for n, imp in self.manifest['imports'].items():
            if 'peq_lib_'+n in self.syms:
                slot = DATA+0x180000+len(self.callbacks)*4
                self.callbacks[slot] = n
                self.word(imp['address'], slot)
        self.u.hook_add(UC_HOOK_CODE, self.intercept)

    def word(self, address, value=None):
        if value is None:
            return struct.unpack('<I', self.u.mem_read(address, 4))[0]
        self.u.mem_write(address, struct.pack('<I', value & 0xffffffff))

    def string(self, a):
        out = bytearray()
        while a and (b := self.u.mem_read(a, 1)[0]):
            out.append(b)
            a += 1
            if len(out) > 4096:
                raise AssertionError('Unterminated string')
        return bytes(out)

    def double(self, register, value=None):
        if value is None:
            return struct.unpack('<d', struct.pack('<Q', self.u.reg_read(register)))[0]
        self.u.reg_write(register, struct.unpack('<Q', struct.pack('<d', value))[0])

    def intercept(self, u, address, size, _):
        name = self.callbacks.get(address)
        if not name:
            return
        a, b, c = [u.reg_read(x) for x in (r.UC_MIPS_REG_A0, r.UC_MIPS_REG_A1, r.UC_MIPS_REG_A2)]
        self.calls.append(name)
        value = 0
        if name == 'calloc':
            value = self.heap
            self.heap += (a*b+15) & ~15
            if self.heap >= DATA+0x160000:
                raise AssertionError('Test heap exhausted')
            u.mem_write(value, bytes(a*b))
        elif name == 'memset':
            u.mem_write(a, bytes([b & 255])*c)
            value = a
        elif name == 'memcpy':
            u.mem_write(a, bytes(u.mem_read(b, c)))
            value = a
        elif name in ('strcmp', 'memcmp'):
            aa, bb = ((self.string(a), self.string(b)) if name == 'strcmp'
                      else (bytes(u.mem_read(a, c)), bytes(u.mem_read(b, c))))
            value = (aa > bb)-(aa < bb)
        elif name == 'strlen':
            value = len(self.string(a))
        elif name in ('sin', 'cos', 'log', 'pow'):
            x = self.double(r.UC_MIPS_REG_F12)
            value_fp = math.pow(x, self.double(r.UC_MIPS_REG_F14)) if name == 'pow' else getattr(math, name)(x)
            self.double(r.UC_MIPS_REG_F0, value_fp)
        elif name in ('fopen', 'free'):
            pass  # no preset file => flat defaults
        elif name == 'open':
            value = -1  # visualizer/crossfade controls absent
        elif name == 'lseek64':
            value = -1
            u.reg_write(r.UC_MIPS_REG_V1, 0xffffffff)
        elif name in ('stock_seek', 'stock_id3'):
            self.stock_calls.append((name, a, b, c, u.reg_read(r.UC_MIPS_REG_A3)))
        else:
            raise AssertionError('Unmocked player import: '+name)
        u.reg_write(r.UC_MIPS_REG_V0, value & 0xffffffff)
        u.reg_write(r.UC_MIPS_REG_PC, u.reg_read(r.UC_MIPS_REG_RA))

    def call(self, name, *args):
        address = self.syms[name] if isinstance(name, str) else name
        self.u.reg_write(r.UC_MIPS_REG_SP, STACK)
        self.u.reg_write(r.UC_MIPS_REG_RA, STOP)
        for reg, value in zip((r.UC_MIPS_REG_A0, r.UC_MIPS_REG_A1, r.UC_MIPS_REG_A2, r.UC_MIPS_REG_A3), args):
            self.u.reg_write(reg, value)
        self.u.emu_start(address, STOP, count=2000000)
        if self.u.reg_read(r.UC_MIPS_REG_PC) != STOP or self.u.reg_read(r.UC_MIPS_REG_SP) != STACK:
            raise AssertionError('MIPS call did not return with its stack restored')
        return self.u.reg_read(r.UC_MIPS_REG_V0)


class PlayerTests(unittest.TestCase):
    def setUp(self):
        self.m = Machine()
        self.af, self.frame, self.audio = DATA, DATA+0x100, DATA+0x1000
        self.assertEqual(self.m.call('peq_open', self.af), 1)

    def frame_data(self, rate=44100, channels=2, fmt=0x1d, samples=(0.0, 0.25, -0.5, 0.75)):
        pcm = struct.pack('<'+'f'*len(samples), *samples)
        self.m.u.mem_write(self.audio, pcm)
        self.m.u.mem_write(self.frame, struct.pack('<6I', self.audio, len(pcm), rate, channels, fmt, 4))
        return pcm

    def control(self):
        return self.m.call(self.m.word(self.af+4), self.af, 0x10000100, self.frame)

    def play(self):
        self.assertEqual(self.m.call(self.m.word(self.af+12), self.af, self.frame), self.frame)

    def test_filter_installs_and_frees(self):
        self.assertTrue(self.m.word(self.af+16))
        self.assertTrue(self.m.word(self.af+20))
        self.m.call(self.m.word(self.af+8), self.af)
        self.assertEqual(self.m.word(self.af+16), 0)
        self.assertEqual(self.m.word(self.af+20), 0)
        self.assertEqual(self.m.calls.count('free'), 2)

    def test_flat_pcm_at_all_supported_rates(self):
        for rate in (8000, 44100, 48000, 96000, 192000, 384000):
            with self.subTest(rate=rate):
                pcm = self.frame_data(rate=rate)
                self.assertEqual(self.control(), 1)
                self.play()
                self.assertEqual(bytes(self.m.u.mem_read(self.audio, len(pcm))), pcm)

    def test_bad_channels_rejected(self):
        for n in (0, 9):
            self.frame_data(channels=n)
            self.assertEqual(self.control(), 0xfffffffe)

    def test_dsd_and_dop_remain_bit_exact(self):
        target = json.loads(build.TARGET.read_text())
        for name, driver in ((b'ffdsd_lsbf\0', b'ffmpeg\0'), (b'dsd\0', b'dsdiff\0')):
            with self.subTest(name=name):
                mp, sh, codec, strings = DATA+0x2000, DATA+0x3000, DATA+0x4000, DATA+0x5000
                self.m.word(target['addresses']['PLAYER_MPCTX'], mp)
                self.m.word(mp+0x2c, sh)
                self.m.word(sh+4, codec)
                self.m.word(codec+0x3d0, strings)
                self.m.word(codec+0x3e0, strings+64)
                self.m.u.mem_write(strings, name)
                self.m.u.mem_write(strings+64, driver)
                pcm = self.frame_data(rate=176400)
                pcm = bytes.fromhex('12340500789afa00bcde05003412fa00')
                self.m.u.mem_write(self.audio, pcm)
                self.assertEqual(self.control(), 1)
                before = self.m.calls.count('open')
                self.play()
                self.assertEqual(bytes(self.m.u.mem_read(self.audio, len(pcm))), pcm)
                self.assertEqual(self.m.calls.count('open'), before)

    def test_preamp_and_channel_balance_process_real_samples(self):
        preset, dsp = DATA+0x8000, DATA+0x9000
        self.m.call('peq_default', preset)
        self.m.word(preset+4, 0)
        self.m.u.mem_write(preset+8, struct.pack('<d', -6.0))
        self.m.u.mem_write(preset+976, struct.pack('<d', 6.0))  # positive attenuates left
        self.m.call('peq_reset', dsp, 48000, 2, preset)
        self.m.u.mem_write(self.audio, struct.pack('<4f', 0.5, 0.5, -0.5, -0.5))
        self.m.call('peq_process', dsp, self.audio, 2)
        got = struct.unpack('<4f', self.m.u.mem_read(self.audio, 16))
        for actual, expected in zip(got, (0.5*10**(-12/20), 0.5*10**(-6/20),
                                         -0.5*10**(-12/20), -0.5*10**(-6/20))):
            self.assertAlmostEqual(actual, expected, places=6)

    def test_peaking_filter_has_expected_gain_at_center(self):
        preset, dsp, pcm = DATA+0x8000, DATA+0x9000, DATA+0x10000
        self.m.call('peq_default', preset)
        self.m.word(preset+4, 0)
        self.m.word(preset, 1)
        self.m.u.mem_write(preset+16, struct.pack('<ii3d', 1, 0, 1000.0, 6.0, 1.0))
        self.m.call('peq_reset', dsp, 48000, 2, preset)
        n = 2048
        samples = [0.1*math.sin(2*math.pi*1000*i/48000) for i in range(n)]
        self.m.u.mem_write(pcm, struct.pack('<'+'f'*(n*2), *(v for x in samples for v in (x, x))))
        self.m.call('peq_process', dsp, pcm, n)
        output = struct.unpack('<'+'f'*(n*2), self.m.u.mem_read(pcm, n*8))[::2]
        ratio = sum(x*x for x in output[512:])/sum(x*x for x in samples[512:])
        self.assertAlmostEqual(10*math.log10(ratio), 6.0, delta=0.01)

    def test_mp3_hr_seek_uses_m1_flag_and_original_function(self):
        addresses = json.loads(build.TARGET.read_text())['addresses']
        self.m.callbacks[addresses['PLAYER_SEEK']] = 'stock_seek'
        demuxer, private, stream = DATA+0x8000, DATA+0xa000, DATA+0xb000
        self.m.word(demuxer+0xc70, private)
        self.m.word(demuxer+0x20, stream)
        self.m.word(private, 1)
        self.m.u.mem_write(demuxer+0x10, struct.pack('<qq', 100, 10000))
        self.m.word(addresses['PLAYER_HR_MP3_SEEK'], 1)
        self.m.call('mp3_seek', demuxer, 0x41200000, 0, 1)  # 10 seconds
        self.assertEqual(self.m.stock_calls, [('stock_seek', demuxer, 0x41200000, 0, 1)])
        self.assertNotIn('lseek64', self.m.calls)

    def test_id3_hook_retains_vendor_parser_for_unseekable_stream(self):
        addresses = json.loads(build.TARGET.read_text())['addresses']
        self.m.callbacks[addresses['PLAYER_ID3']] = 'stock_id3'
        stream = DATA+0xb000
        self.m.word(stream+0x14, 7)
        self.m.call('id3_gain', stream, 1234)
        self.assertEqual(self.m.stock_calls[0][:3], ('stock_id3', stream, 1234))
        self.assertEqual(self.m.calls.count('lseek64'), 1)


class PatchTests(unittest.TestCase):
    def test_rebuild_bytes_and_exact_seven_sites(self):
        target = json.loads(build.TARGET.read_text())
        payload, syms = payload_image(BUILD/'payload.elf', target['payload_base'])
        patched, changes = build.patch(STOCK.read_bytes(), payload, syms, target)
        self.assertEqual(patched, (BUILD/'hciplayer').read_bytes())
        self.assertEqual(len(changes), 7)

    def test_wrong_player_rejected(self):
        raw = bytearray(STOCK.read_bytes())
        raw[-1] ^= 1
        with self.assertRaisesRegex(ValueError, 'pinned'):
            build.validate_stock(bytes(raw), json.loads(build.TARGET.read_text()))

    def test_wrong_site_rejected_even_with_correct_file(self):
        target = json.loads(build.TARGET.read_text())
        target['patches'][0]['expected'] ^= 1
        with self.assertRaisesRegex(ValueError, 'patch mismatch'):
            build.validate_stock(STOCK.read_bytes(), target)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--build', type=Path, required=True)
    p.add_argument('--stock-player', type=Path, required=True)
    args, rest = p.parse_known_args()
    BUILD, STOCK = args.build.resolve(), args.stock_player.resolve()
    if json.loads((BUILD/'manifest.json').read_text()).get('source_sha256') != build.source_digest():
        raise SystemExit('Audio build is stale; rebuild it before running the checks')
    unittest.main(argv=[sys.argv[0], *rest])
