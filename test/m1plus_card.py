#!/usr/bin/env python3
"""Card preparation invariants: explicit opt-in, integrity and interrupted writes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('card', ROOT/'tools/m1plus_card.py')
card = importlib.util.module_from_spec(spec)
spec.loader.exec_module(card)


class CardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='card-test-', dir=ROOT/'work')
        self.root = Path(self.tmp.name)
        self.bundle = self.root/'bundle'
        (self.bundle/'sd/M1Pod/bin').mkdir(parents=True)
        self.sd = self.root/'card'
        self.sd.mkdir()
        (self.sd/'music.flac').write_bytes(b'preserve existing user data')
        app = self.bundle/'sd/M1Pod/bin/demo'
        app.write_bytes(b'example payload')
        self.digest = card.digest(app)
        info = dict(target='shanling-m1-plus-v2.1', demo_sha256=self.digest)
        (self.bundle/'sd/M1Pod/app.json').write_text(json.dumps(info))
        manifest = dict(format='m1pod-bootstrap-bundle-v1', files={
            p.relative_to(self.bundle).as_posix(): card.digest(p)
            for p in self.bundle.rglob('*') if p.is_file()})
        (self.bundle/'bundle.json').write_text(json.dumps(manifest))

    def tearDown(self):
        self.tmp.cleanup()

    def stage(self):
        card.operate('stage', self.sd, self.bundle)

    def test_stage_leaves_stock_selected_and_music_untouched(self):
        self.stage()
        self.assertTrue((self.sd/'M1Pod/disable').is_file())
        self.assertFalse((self.sd/'M1Pod/run-once').exists())
        self.assertIn('stock boot', card.operate('status', self.sd))
        self.assertEqual((self.sd/'music.flac').read_bytes(), b'preserve existing user data')
        self.assertFalse((self.sd/'update.bin').exists())

    def test_arm_is_hash_bound_and_explicit(self):
        self.stage()
        card.operate('arm', self.sd)
        self.assertEqual((self.sd/'M1Pod/run-once').read_bytes(), (self.digest+'\n').encode())
        self.assertFalse((self.sd/'M1Pod/disable').exists())
        self.assertIn('armed for one boot', card.operate('status', self.sd))

    def test_corrupt_card_cannot_be_armed(self):
        self.stage()
        (self.sd/'M1Pod/bin/demo').write_bytes(b'wrong')
        with self.assertRaises(ValueError):
            card.operate('arm', self.sd)
        self.assertTrue((self.sd/'M1Pod/disable').exists())
        self.assertFalse((self.sd/'M1Pod/run-once').exists())

    def test_corrupt_bundle_rejected_before_card_changes(self):
        (self.bundle/'sd/M1Pod/bin/demo').write_bytes(b'wrong')
        with self.assertRaises(ValueError):
            self.stage()
        self.assertEqual(sorted(p.name for p in self.sd.iterdir()), ['music.flac'])

    def test_disable_does_not_depend_on_valid_payload(self):
        self.stage()
        card.operate('arm', self.sd)
        (self.sd/'M1Pod/bin/demo').unlink()
        card.operate('disable', self.sd)
        self.assertTrue((self.sd/'M1Pod/disable').exists())
        self.assertFalse((self.sd/'M1Pod/run-once').exists())

    def test_failed_arm_write_keeps_disable(self):
        self.stage()
        original = card.atomic
        def fail_marker(root, relative, content):
            if relative == 'M1Pod/run-once':
                raise OSError('simulated card write failure')
            original(root, relative, content)
        with patch.object(card, 'atomic', side_effect=fail_marker), self.assertRaises(OSError):
            card.operate('arm', self.sd)
        self.assertTrue((self.sd/'M1Pod/disable').is_file())

    def test_restage_disables_previously_armed_payload(self):
        self.stage()
        card.operate('arm', self.sd)
        self.stage()
        self.assertTrue((self.sd/'M1Pod/disable').is_file())
        self.assertFalse((self.sd/'M1Pod/run-once').exists())

    def test_refuses_card_root_missing_or_overlapping_bundle(self):
        with self.assertRaises(ValueError):
            card.operate('stage', self.root/'missing', self.bundle)
        with self.assertRaises(ValueError):
            card.operate('stage', self.root, self.bundle)

    def test_does_not_replace_directory_with_marker(self):
        self.stage()
        (self.sd/'M1Pod/run-once').mkdir()
        with self.assertRaises(ValueError):
            card.operate('arm', self.sd)
        self.assertTrue((self.sd/'M1Pod/disable').is_file())


if __name__ == '__main__':
    unittest.main()
