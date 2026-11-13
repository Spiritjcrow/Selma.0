import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from verify_run import verify, save_plots


class VerifyRunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.dataset = self.dir / 'SYNTHETIC.csv'
        self.dataset.write_text('signal\n0\n1\n2\n3\n')
        self.report = self.dir / 'perceptual_report.json'
        self.spikes = self.dir / 'reactor_spikes.csv'
        data = {'filename': self.dataset.name,
                'sha256': hashlib.sha256(self.dataset.read_bytes()).hexdigest(),
                'source': 'file_numeric_signal',
                'spikes_are_simulated_not_measured': True,
                'epochs': 2, 'n_samples': 4, 'dt_seconds': 0.01,
                'num_reactors': 100,
                'epoch_results': [
                    {'epoch': 1, 'reactor_spikes': 1, 'mean_synaptic_weight': 0.5},
                    {'epoch': 2, 'reactor_spikes': 1, 'mean_synaptic_weight': 0.92},
                ]}
        self.report.write_text(json.dumps(data))
        with self.spikes.open('w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['reactor_id', 'time_seconds'])
            writer.writerow([5, 0.001])
            writer.writerow([1, 0.043])

    def test_good_report_and_plots(self):
        summary, raster = verify(self.dataset, self.report, self.spikes)
        self.assertEqual(summary['total_reactor_spikes'], 2)
        self.assertTrue(summary['saturation_warning'])
        save_plots(summary, raster, self.dir / 'out')
        self.assertTrue((self.dir / 'out' / 'reactor_raster.png').is_file())

    def test_modified_dataset_fails_closed(self):
        self.dataset.write_text('signal\n0\n1\n2\n9\n')
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            verify(self.dataset, self.report, self.spikes)

    def test_wrong_spike_count_fails_closed(self):
        with self.spikes.open('a') as f:
            f.write('4,0.045\n')
        with self.assertRaisesRegex(ValueError, 'spike counts'):
            verify(self.dataset, self.report, self.spikes)


if __name__ == '__main__':
    unittest.main()