import json
import math
from pathlib import Path
import shutil
import tempfile
import unittest
import wave
import hashlib

import numpy as np

from voxlab.pipeline import analyze_file, find_acoustic_events, sha256_file
from voxlab.corrections import record_correction, export_corrections


class VoxReviewTests(unittest.TestCase):
    def test_silence_never_claims_speech(self):
        self.assertEqual(find_acoustic_events(np.zeros(16000, dtype=np.float32)), [])

    def test_pulse_event_unclassified(self):
        audio = np.zeros(16000 * 3, dtype=np.float32)
        t = np.arange(12000) / 16000
        audio[20000:32000] = .18 * np.sin(2*np.pi*440*t)
        ev = find_acoustic_events(audio, sensitivity=1)
        self.assertTrue(ev)
        self.assertEqual(ev[0]['type'], 'acoustic_candidate_unclassified')
        self.assertFalse(any(event['speech_confirmed'] for event in ev))
        self.assertTrue(any(e['start_seconds'] <= 1.3 and e['end_seconds'] >= 1.8 for e in ev))

    def test_invalid_sensitivity(self):
        for s in [-1, 1.1]:
            with self.assertRaises(ValueError):
                find_acoustic_events(np.ones(1000), sensitivity=s)

    def test_correction_export_not_training(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp)/'reviews.sqlite3'
            sha = 'a' * 64
            n = record_correction(db, sha, 1.0, 2.5, 'possible words', 'listener_reported')
            self.assertEqual(n, 1)
            out = Path(tmp)/'reviews.jsonl'
            self.assertEqual(export_corrections(db, out), 1)
            row = json.loads(out.read_text())
            self.assertFalse(row['training_approved'])
            self.assertEqual(row['status'], 'listener_reported')
            with self.assertRaises(ValueError):
                record_correction(db, sha, 1, 2, 'invented', 'independently_verified')

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'ffmpeg required')
    def test_end_to_end_keeps_original_intact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / 'source.wav'
            audio = (0.2 * np.sin(2*np.pi*300*np.arange(16000)/16000)*32767).astype('<i2')
            with wave.open(str(src), 'wb') as wav:
                wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000)
                wav.writeframes(audio.tobytes())
            original_sha = sha256_file(src)
            report = analyze_file(src, root/'reports')
            self.assertEqual(sha256_file(src), original_sha)
            self.assertEqual(report['original']['sha256'], original_sha)
            self.assertEqual(report['asr']['status'], 'not_run_no_local_model')
            self.assertTrue(Path(report['report_path']).is_file())
            self.assertTrue((Path(report['report_path']).parent/'speech_band_listening_copy.wav').is_file())
            self.assertTrue(report['analysis']['analysis_is_not_speech_identification'])

if __name__ == '__main__':
    unittest.main()