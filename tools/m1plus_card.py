#!/usr/bin/env python3
"""Stage, arm once, or disable the experimental M1 SD app. Never flash firmware.

Uses only the Python standard library. An explicitly supplied card root is
required; no drive scanning, formatting or firmware update copying is performed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def regular(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError('Expected a regular file: '+str(path))


def safe_path(root, relative):
    path = root
    for component in Path(relative).parts:
        if component in ('.', '..'):
            raise ValueError('Unsafe path')
        path = path/component
        if path.is_symlink() or path.is_junction():
            raise ValueError('Refusing link/junction: '+str(path))
    if not path.resolve().is_relative_to(root):
        raise ValueError('Path escapes the card root')
    return path


def atomic(root, relative, data):
    path = safe_path(root, relative)
    temp = safe_path(root, relative+'.tmp')
    if path.exists():
        regular(path)
    if temp.exists():
        regular(temp)
    path.parent.mkdir(parents=True, exist_ok=True)
    with temp.open('wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def remove_file(root, relative):
    path = safe_path(root, relative)
    if path.exists():
        regular(path)
        path.unlink()


def verified_bundle(bundle):
    regular(bundle/'bundle.json')
    manifest = json.loads((bundle/'bundle.json').read_text())
    if manifest.get('format') != 'm1pod-bootstrap-bundle-v1':
        raise ValueError('Wrong bundle format')
    for rel in ('sd/M1Pod/bin/demo', 'sd/M1Pod/app.json'):
        path = safe_path(bundle, rel)
        regular(path)
        if digest(path) != manifest['files'][rel]:
            raise ValueError('Bundle checksum mismatch: '+rel)
    app = json.loads((bundle/'sd/M1Pod/app.json').read_text())
    if app.get('target') != 'shanling-m1-plus-v2.1' or app.get('demo_sha256') != digest(bundle/'sd/M1Pod/bin/demo'):
        raise ValueError('Incorrect application target or digest')
    return manifest, app


def card_state(card):
    app_path = safe_path(card, 'M1Pod/bin/demo')
    info_path = safe_path(card, 'M1Pod/app.json')
    regular(app_path)
    regular(info_path)
    info = json.loads(info_path.read_text())
    actual = digest(app_path)
    if info.get('target') != 'shanling-m1-plus-v2.1' or info.get('demo_sha256') != actual:
        raise ValueError('Card payload is incomplete, corrupted, or for a different target')
    return actual


def operate(action, card, bundle=None):
    if card.is_symlink() or card.is_junction() or not card.is_dir():
        raise ValueError('Card root must be an existing real directory')
    card = card.resolve()
    if action == 'stage':
        if bundle is None:
            raise ValueError('stage requires --bundle')
        bundle = bundle.resolve()
        verified_bundle(bundle)
        if card.is_relative_to(bundle) or bundle.is_relative_to(card):
            raise ValueError('Bundle and card directory must not overlap')
        # Disable first, so an interrupted staging operation cannot arm a mix of
        # old/new files. Never remove library/music/settings files on the card.
        atomic(card, 'M1Pod/disable', b'Disabled. Use the arm command for one boot.\n')
        remove_file(card, 'M1Pod/run-once')
        for rel in ('M1Pod/bin/demo', 'M1Pod/app.json'):
            atomic(card, rel, (bundle/'sd'/rel).read_bytes())
        safe_path(card, 'M1Pod/bin/demo').chmod(0o755)
        atomic(card, 'M1Pod/diagnostics-enable', b'')
        atomic(card, 'm1pod-trace.enable', b'')
        card_state(card)
        return 'Staged with stock boot selected. No firmware copied or installed.'
    if action == 'disable':
        atomic(card, 'M1Pod/disable', b'Disabled.\n')
        remove_file(card, 'M1Pod/run-once')
        return 'Experimental app disabled; the bootstrap will select stock.'
    value = card_state(card)
    if action == 'arm':
        # Start disabled, replace token durably, then enable as the final step.
        atomic(card, 'M1Pod/disable', b'Arming in progress.\n')
        atomic(card, 'M1Pod/run-once', (value+'\n').encode())
        remove_file(card, 'M1Pod/disable')
        return 'Armed for ONE experimental boot. Safely eject the card before use.'
    marker = safe_path(card, 'M1Pod/run-once')
    disabled = safe_path(card, 'M1Pod/disable').exists()
    armed = marker.is_file() and marker.read_bytes() == (value+'\n').encode() and not disabled
    return 'Payload verified; '+('armed for one boot.' if armed else 'stock boot selected.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['stage', 'arm', 'disable', 'status'])
    parser.add_argument('card', type=Path, help='Explicit microSD root directory')
    parser.add_argument('--bundle', type=Path, help='Bundle directory, required for stage')
    args = parser.parse_args()
    print(operate(args.action, args.card, args.bundle))
