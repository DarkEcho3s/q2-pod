#!/usr/bin/env python3
"""Exercise stock-first launch decisions and real MIPS execve instructions.

Shell fixtures simulate storage failures; Unicorn simulates syscall results.
Neither checks real flash hardware, FAT durability, mdev timing or bootability.
"""
import argparse
import hashlib
import io
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS32, UC_MODE_LITTLE_ENDIAN, UC_HOOK_INTR, UC_HOOK_CODE
from unicorn.mips_const import (UC_MIPS_REG_SP, UC_MIPS_REG_A0, UC_MIPS_REG_A1,
    UC_MIPS_REG_A2, UC_MIPS_REG_A3, UC_MIPS_REG_V0, UC_MIPS_REG_S3, UC_MIPS_REG_S4,
    UC_MIPS_REG_GP, UC_MIPS_REG_PC, UC_MIPS_REG_RA)

ROOT = Path(__file__).resolve().parents[1]
BASH = SHIM = STOCK = None


def posix(path):
    value = str(path.resolve()).replace('\\', '/')
    return '/'+value[0].lower()+value[2:] if len(value) > 1 and value[1] == ':' else value


class LaunchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='boot-test-', dir=ROOT/'work')
        self.root = Path(self.tmp.name)
        self.card = self.root/'card'
        (self.card/'bin').mkdir(parents=True)
        self.proc = self.root/'proc'
        (self.proc/'bus/input').mkdir(parents=True)
        (self.root/'stock').write_text('#!/bin/sh\nprintf "stock\\n"\n', newline='\n')
        (self.root/'shim').write_text('#!/bin/sh\n[ ! -e "$M1POD_TEST_CARD/run-once" ] || exit 90\n'
                                     '[ -f "$M1POD_TEST_CARD/last-attempt" ] || exit 91\n'
                                     'printf "payload\\n"\n', newline='\n')
        for f in ['stock', 'shim']:
            (self.root/f).chmod(0o755)
        (self.card/'bin/demo').write_bytes(b'#!/bin/sh\nexit 0\n')
        (self.card/'bin/demo').chmod(0o755)
        self.digest = hashlib.sha256((self.card/'bin/demo').read_bytes()).hexdigest()
        self.mounts = self.proc/'mounts'
        self.mounts.write_text('/dev/mmcblk0p1 /mnt/mmc vfat rw 0 0\n')
        self.env = os.environ.copy()
        self.env['PATH'] = str(BASH.parent)+os.pathsep+self.env['PATH']
        self.env.update(M1POD_HOST_TEST='1', M1POD_TEST_CARD=posix(self.card),
                        M1POD_TEST_STOCK=posix(self.root/'stock'),
                        M1POD_TEST_EXEC=posix(self.root/'shim'),
                        M1POD_TEST_MOUNTS=posix(self.mounts), M1POD_TEST_PROC=posix(self.proc))

    def tearDown(self):
        self.tmp.cleanup()

    def arm(self, content=None):
        (self.card/'run-once').write_bytes(content if content is not None else (self.digest+'\n').encode())

    def run_launch(self):
        run = subprocess.run([str(BASH), posix(ROOT/'patch/m1plus/launch.sh')], env=self.env,
                             capture_output=True, text=True, timeout=10)
        self.assertEqual(run.returncode, 0, run.stderr)
        return run.stdout.strip()

    def override(self, command):
        directory = self.root/'commands'
        directory.mkdir(exist_ok=True)
        path = directory/command
        path.write_text('#!/bin/sh\nexit 1\n', newline='\n')
        path.chmod(0o755)
        # Bash inherits PATH from Windows as a converted POSIX path. Pass a
        # leading Windows component on Windows, conventional PATH on Unix.
        self.env['PATH'] = str(directory)+os.pathsep+self.env['PATH']

    def test_no_marker_is_stock(self):
        self.assertEqual(self.run_launch(), 'stock')

    def test_valid_payload_only_runs_once(self):
        self.arm()
        self.assertEqual(self.run_launch(), 'payload')
        self.assertFalse((self.card/'run-once').exists())
        self.assertEqual((self.card/'last-attempt').read_text(), self.digest+'\n')
        self.assertEqual(self.run_launch(), 'stock')

    def test_disabled_payload_stays_armed_but_runs_stock(self):
        self.arm()
        (self.card/'disable').touch()
        self.assertEqual(self.run_launch(), 'stock')
        self.assertTrue((self.card/'run-once').exists())

    def test_unmounted_or_different_mount_uses_stock(self):
        self.arm()
        for value in ['', '/dev/foo /mnt/mmc-backup vfat rw 0 0\n']:
            self.mounts.write_text(value)
            self.assertEqual(self.run_launch(), 'stock')

    def test_corrupt_payload_is_rejected(self):
        self.arm()
        (self.card/'bin/demo').write_bytes(b'corrupt')
        self.assertEqual(self.run_launch(), 'stock')

    def test_malformed_markers_are_rejected(self):
        for content in [b'', self.digest.encode(), (self.digest+'\r\n').encode(),
                        ('F'*64+'\n').encode(), ('0'*64+'\n').encode(),
                        (self.digest+'\nx').encode(), (self.digest+'x').encode()]:
            with self.subTest(content=content):
                self.arm(content)
                self.assertEqual(self.run_launch(), 'stock')

    def test_missing_app_or_shim_uses_stock(self):
        self.arm()
        (self.card/'bin/demo').unlink()
        self.assertEqual(self.run_launch(), 'stock')
        (self.card/'bin/demo').write_bytes(b'#!/bin/sh\nexit 0\n')
        (self.card/'bin/demo').chmod(0o755)
        (self.root/'shim').unlink()
        self.assertEqual(self.run_launch(), 'stock')
        self.assertTrue((self.card/'run-once').exists())

    def test_unwritable_consumption_uses_stock(self):
        self.arm()
        self.override('mv')
        self.assertEqual(self.run_launch(), 'stock')
        self.assertTrue((self.card/'run-once').exists())

    def test_sync_failure_never_runs_payload(self):
        self.arm()
        self.override('sync')
        self.assertEqual(self.run_launch(), 'stock')
        self.assertFalse((self.card/'run-once').exists())

    def test_last_attempt_directory_cannot_receive_marker(self):
        self.arm()
        (self.card/'last-attempt').mkdir()
        self.assertEqual(self.run_launch(), 'stock')
        self.assertTrue((self.card/'run-once').exists())

    def test_diagnostics_are_opt_in_fixed_and_bounded(self):
        for name in ['version', 'cmdline', 'mtd', 'meminfo', 'cpuinfo', 'bus/input/devices']:
            (self.proc/name).write_bytes(b'X'*10000)
        self.assertEqual(self.run_launch(), 'stock')
        self.assertFalse((self.card/'boot.txt').exists())
        (self.card/'diagnostics-enable').touch()
        self.assertEqual(self.run_launch(), 'stock')
        content = (self.card/'boot.txt').read_bytes()
        self.assertTrue(content.startswith(b'format=m1pod-boot-v1\n'))
        self.assertLess(len(content), 7*8192+300)
        self.assertIn(b'[mtd]\n'+b'X'*8192+b'\n', content)

    def test_symlink_marker_is_rejected(self):
        self.arm()
        (self.card/'run-once').rename(self.card/'real-marker')
        try:
            (self.card/'run-once').symlink_to(self.card/'real-marker')
        except OSError as e:
            self.skipTest('Host cannot create symlinks: '+str(e))
        self.assertEqual(self.run_launch(), 'stock')


class ExecTests(unittest.TestCase):
    def run_shim(self, failures):
        elf = ELFFile(io.BytesIO(SHIM.read_bytes()))
        u = Uc(UC_ARCH_MIPS, UC_MODE_MIPS32 | UC_MODE_LITTLE_ENDIAN)
        u.mem_map(0x400000, 0x100000)
        u.mem_map(0x1000000, 0x20000)
        for seg in elf.iter_segments():
            if seg['p_type'] == 'PT_LOAD':
                u.mem_write(seg['p_vaddr'], seg.data())
        sp = 0x1010000
        env_text = sp+128
        u.mem_write(env_text, b'TSLIB_TSDEVICE=/dev/input/event2\0')
        # argc=2, argv[0], argv[1], NULL, envp[0], NULL.
        u.mem_write(sp, struct.pack('<6I', 2, sp+200, sp+220, 0, env_text, 0))
        u.reg_write(UC_MIPS_REG_SP, sp)
        calls = []

        def string(addr):
            return bytes(u.mem_read(addr, 128)).split(b'\0')[0].decode()

        def interrupt(machine, number, data):
            syscall = u.reg_read(UC_MIPS_REG_V0)
            if syscall == 4011:
                path = string(u.reg_read(UC_MIPS_REG_A0))
                argv = struct.unpack('<2I', u.mem_read(u.reg_read(UC_MIPS_REG_A1), 8))
                envp = u.reg_read(UC_MIPS_REG_A2)
                self.assertEqual(envp, sp+16)
                self.assertEqual(string(struct.unpack('<I', u.mem_read(envp, 4))[0]),
                                 'TSLIB_TSDEVICE=/dev/input/event2')
                self.assertEqual(argv[1], 0)
                self.assertEqual(string(argv[0]), '/release/bin/demo')
                calls.append(path)
                if len(calls) > failures:
                    u.emu_stop()
                else:
                    u.reg_write(UC_MIPS_REG_V0, 2)  # ENOENT
                    u.reg_write(UC_MIPS_REG_A3, 1)  # o32 syscall error flag
                    u.reg_write(UC_MIPS_REG_A2, 0)  # stress recomputation
            elif syscall == 4001:
                calls.append(('exit', u.reg_read(UC_MIPS_REG_A0)))
                u.emu_stop()
            else:
                self.fail('Unexpected syscall '+str(syscall))

        u.hook_add(UC_HOOK_INTR, interrupt)
        u.emu_start(elf['e_entry'], 0x4ffffc, count=100)
        return calls

    def test_sd_exec_preserves_watchdog_name_and_environment(self):
        self.assertEqual(self.run_shim(0), ['/mnt/mmc/M1Pod/bin/demo'])

    def test_missing_noexec_or_invalid_sd_executable_falls_back(self):
        self.assertEqual(self.run_shim(1), ['/mnt/mmc/M1Pod/bin/demo', '/release/bin/demo'])

    def test_both_execs_failing_exit_without_loop(self):
        self.assertEqual(self.run_shim(2), ['/mnt/mmc/M1Pod/bin/demo', '/release/bin/demo', ('exit', 127)])


class UpdateGateTests(unittest.TestCase):
    """Execute stock model/version gate only, without extraction or flash writes.

    This does not emulate the recovery environment or actual update installation.
    """
    def gate(self, version, model='Shanling M1 Plus'):
        import json
        sys.path.insert(0, str(ROOT/'tools'))
        from build_m1plus import validate_stock
        raw = STOCK.read_bytes()
        elf = validate_stock(raw, json.loads((ROOT/'targets/m1plus/v2.1.json').read_text()))
        u = Uc(UC_ARCH_MIPS, UC_MODE_MIPS32 | UC_MODE_LITTLE_ENDIAN)
        u.mem_map(0x400000, 0x700000)
        u.mem_map(0x1000000, 0x20000)
        for s in elf.iter_segments():
            if s['p_type'] == 'PT_LOAD':
                u.mem_write(s['p_vaddr'], s.data())
        # Populate stack-local strings as if fgets/trim had returned them.
        for r, value in [(UC_MIPS_REG_SP, 0x1010000), (UC_MIPS_REG_GP, 0xa03ed0),
                         (UC_MIPS_REG_S3, 0x1000000), (UC_MIPS_REG_S4, 0x1000100)]:
            u.reg_write(r, value)
        u.mem_write(0x1010018, struct.pack('<I', 0xa03ed0))
        u.mem_write(0x1000000, model.encode()+b'\0')
        u.mem_write(0x1000100, version.encode()+b'\0')
        u.mem_write(0xa0343c, struct.pack('<I', 0x1011000))  # strcmp GOT
        u.mem_write(0xa033bc, struct.pack('<I', 0x1011010))  # strchr GOT
        result = []

        def string(address):
            return bytes(u.mem_read(address, 128)).split(b'\0')[0]

        def code(machine, address, size, data):
            if address in (0x4e1148, 0x4e0f80, 0x4e1140):
                result.append({0x4e1148: 'accepted', 0x4e0f80: 'invalid', 0x4e1140: 'same-version'}[address])
                u.emu_stop()
            elif address in (0x1011000, 0x1011010):
                a, b = u.reg_read(UC_MIPS_REG_A0), u.reg_read(UC_MIPS_REG_A1)
                if address == 0x1011000:
                    value = int(string(a) != string(b))
                else:
                    index = string(a).find(bytes([b]))
                    value = a+index if index >= 0 else 0
                u.reg_write(UC_MIPS_REG_V0, value)
                u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))
            elif address == 0x4d8a70:  # delete_updateremain: no filesystem calls
                u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))

        u.hook_add(UC_HOOK_CODE, code)
        u.emu_start(0x4e10dc, 0x4ffffc, count=200)
        self.assertEqual(len(result), 1, 'Version gate did not reach a decision')
        return result[0]

    def test_official_same_version_restore_is_rejected(self):
        self.assertEqual(self.gate('V2.1'), 'same-version')

    def test_development_and_restore_labels_pass_stock_gate(self):
        for label in ['V2.1-M1P-dev1', 'V2.1-M1P-restore']:
            self.assertEqual(self.gate(label), 'accepted')

    def test_wrong_model_and_invalid_label_rejected(self):
        self.assertEqual(self.gate('V2.1-M1P-dev1', 'Shanling Q2'), 'invalid')
        self.assertEqual(self.gate('2.1-M1P-dev1'), 'invalid')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--bash', type=Path, default=Path(shutil.which('bash') or 'bash'))
    p.add_argument('--shim', type=Path, required=True)
    p.add_argument('--stock-demo', type=Path, required=True)
    a, remaining = p.parse_known_args()
    BASH, SHIM, STOCK = a.bash.resolve(), a.shim.resolve(), a.stock_demo.resolve()
    unittest.main(argv=[sys.argv[0], *remaining])
