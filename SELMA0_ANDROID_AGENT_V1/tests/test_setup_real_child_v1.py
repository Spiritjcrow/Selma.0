"""Synthetic child-process smoke. No Selma runtime, network, or Android device."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import selma0_first_run_android_v1 as setup

class TestRealChildExit(unittest.TestCase):
    def test_real_subprocess_early_exit(self):
        opts={"profile":"eco","scene":"coast","motion":"reduced"}
        raw=json.dumps(opts).encode()
        for code in (0,7):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as t:
                home=Path(t); child=home/'synthetic_exit.py'
                child.write_text(f'raise SystemExit({code})\n',encoding='utf-8')
                prefs=home/'selma0_setup_v1.json'
                handler=object.__new__(setup.WizardHandler)
                handler.path='/start'
                handler.headers={'Host':'127.0.0.1:8766','X-Selma-Setup-Token':setup.TOKEN,'Content-Type':'application/json','Content-Length':str(len(raw))}
                handler.rfile=io.BytesIO(raw)
                replies=[]
                handler.reply=lambda status,payload:replies.append((status,payload))
                real_save=setup.save_preferences
                with mock.patch.object(setup,'HOME',home),mock.patch.object(setup,'PREFS',prefs),mock.patch.object(setup,'RUNTIME',child),mock.patch.object(setup,'save_preferences',side_effect=lambda v:real_save(v,prefs)):
                    handler.do_POST()
                self.assertEqual(replies[0][0],503)
                self.assertIn('incomplete',replies[0][1]['error'])
                self.assertFalse(prefs.exists())
