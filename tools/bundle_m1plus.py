#!/usr/bin/env python3
"""Assemble a local M1 test kit, checking all vendor-derived inputs again."""
import argparse
import io
import json
from pathlib import Path
import shutil

from dissect.squashfs import SquashFS
from build_m1plus import ROOT, TARGET, checked, sha, validate_stock, payload_image, patch
from build_m1plus_firmware import ORIGINAL, KERNEL, ROOTFS, VERSION, RESTORE_VERSION
from port_inspect import read_container


def bundle(firmware, app, out):
    out = out.resolve()
    checked(out.is_relative_to(ROOT/'work') and out != ROOT/'work' and not out.exists(),
            'Use a fresh bundle directory under work/')
    validation = json.loads((firmware/'validation.json').read_text())
    checked(validation['filesystem']['passed'] and validation['filesystem']['no_growth'],
            'Firmware filesystem validation has not passed')
    fw_data, fw = read_container(firmware/'update.bin')
    stock_data, stock = read_container(firmware/'original-stock/update.bin')
    restore_data, restore = read_container(firmware/'stock-restore/update.bin')
    checked(stock['sha256'] == ORIGINAL and fw['sha256'] == validation['package']['sha256'] and
            fw['version'] == VERSION and restore['version'] == RESTORE_VERSION and
            restore['sha256'] == validation['restore']['package']['sha256'], 'Firmware/restore mismatch')
    checked(fw_data[KERNEL] == stock_data[KERNEL] and
            all(restore_data[n] == stock_data[n] for n in (KERNEL, ROOTFS)),
            'Kernel or stock restore payload was changed')
    # Reconstruct the application patch from the checked original and compiled
    # payload. A hand-edited manifest cannot disguise an unrelated executable.
    fs = SquashFS(io.BytesIO(stock_data[ROOTFS]))
    original = fs.get('release/bin/demo').open().read()
    target = json.loads(TARGET.read_text())
    validate_stock(original, target)
    payload, syms = payload_image(app/'payload.elf', target['payload_base'])
    expected_app, _ = patch(original, payload, syms, target)
    application = (app/'demo.m1pod').read_bytes()
    manifest = json.loads((app/'manifest.json').read_text())
    checked(application == expected_app and sha(application) == manifest['demo_sha256'] and
            manifest['target'] == target['name'], 'Application patch mismatch')
    out.mkdir(parents=True)
    files = {
        'firmware/update.bin': firmware/'update.bin',
        'restore/update.bin': firmware/'stock-restore/update.bin',
        'official-v2.1/update.bin': firmware/'original-stock/update.bin',
        'sd/M1Pod/bin/demo': app/'demo.m1pod',
        'sd/M1Pod/app.json': app/'manifest.json',
        'validation.json': firmware/'validation.json',
        'm1plus_card.py': ROOT/'tools/m1plus_card.py',
        'TESTING.md': ROOT/'docs/m1plus-testing.md',
    }
    for rel, source in files.items():
        destination = out/rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    (out/'sd/M1Pod/bin/demo').chmod(0o755)
    (out/'sd/M1Pod/disable').write_text('Stock boot selected. See TESTING.md before activating.\n')
    (out/'sd/M1Pod/diagnostics-enable').write_bytes(b'')
    (out/'sd/m1pod-trace.enable').write_bytes(b'')
    (out/'README-FIRST.txt').write_text(
        'M1 Plus V2.1: experimental bootstrap and input preview, NOT the full feature port.\n'
        'Read TESTING.md before copying or installing anything.\n'
        'firmware/update.bin installs stock-first launch support.\n'
        'restore/update.bin restores EXACT official kernel/rootfs, with a distinct update label.\n'
        'official-v2.1/update.bin is the untouched official backup; the V2.1 app rejects its same version.\n'
        'sd/ is staged disabled. No experiment is armed automatically.\n'
        'A complete failure to boot has no verified button/USB recovery procedure yet.\n')
    checksums = {p.relative_to(out).as_posix(): sha(p.read_bytes())
                 for p in sorted(out.rglob('*')) if p.is_file()}
    summary = dict(format='m1pod-bootstrap-bundle-v1', status='not-device-tested',
                   full_feature_port=False, original_sha256=ORIGINAL,
                   files=checksums)
    (out/'bundle.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(dict(bundle=str(out), firmware_sha256=fw['sha256'],
                         restore_sha256=restore['sha256'], app_sha256=sha(application)), indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--firmware', type=Path, required=True)
    p.add_argument('--app', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    bundle(a.firmware.resolve(), a.app.resolve(), a.out)
