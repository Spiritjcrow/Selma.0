"""Selma° Perceptual Operator | Brian2 data-driven simulation v0.2.

Reads a local/Colab Google Drive CSV or numeric text file; uses numeric samples
as time-varying rates for a Poisson encoder feeding a Brian2 LIF/STDP network.
This is an educational SNN demonstration, not real neural spike detection or
brain-state/intent recognition. Poisson spike events are sampled by the simulator.
"""
import argparse
import csv
import hashlib
import json
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd


def load_numeric_signal(path, default_dt=0.01, max_samples=10000):
    """Return (N,C) float samples, seconds per sample, metadata; fail closed."""
    path = Path(path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"Dataset not found: {path}")
    if path.suffix.lower() not in {'.csv', '.txt', '.tsv'}:
        raise ValueError('Supported extensions: .csv, .txt, .tsv')
    first = next((line.strip() for line in path.open(encoding='utf-8-sig')
                  if line.strip() and not line.lstrip().startswith('#')), None)
    if first is None:
        raise ValueError('Empty dataset')
    tokens = [tok for tok in re.split(r'[,;\s]+', first.strip()) if tok]
    def isfloat(s):
        try:
            float(s)
            return True
        except (ValueError, TypeError):
            return False
    header = not all(isfloat(x) for x in tokens)
    df = pd.read_csv(path, sep=r'[,;\s]+', engine='python', comment='#',
                     header=0 if header else None, encoding='utf-8-sig')
    if df.shape[0] < 2:
        raise ValueError('Need at least two rows of numeric data')
    if len(df) > max_samples:
        raise ValueError(f'Too many samples ({len(df)}); limit {max_samples} for demo')
    time_candidates = [col for col in df.columns if str(col).strip().lower()
                       in ('time', 'time_s', 'timestamp_s', 'seconds', 't_s')]
    dt = float(default_dt)
    if time_candidates:
        time_col = time_candidates[0]
        ts = pd.to_numeric(df[time_col], errors='coerce').to_numpy(dtype=float)
        if not np.all(np.isfinite(ts)) or not np.all(np.diff(ts) > 0):
            raise ValueError('time_s must be finite and strictly increasing')
        intervals = np.diff(ts)
        dt = float(np.median(intervals))
        if not np.allclose(intervals, dt, rtol=1e-3, atol=1e-7):
            raise ValueError('Irregular time stamps: resample to a uniform interval first')
        df = df.drop(columns=[time_col])
    if not 0 < dt <= 1:
        raise ValueError(f'Sample interval must be in (0, 1] seconds, got {dt}')
    numeric = df.apply(pd.to_numeric, errors='coerce')
    # Discard non-numeric annotation columns; never silently substitute synthetic data.
    numeric = numeric.loc[:, numeric.notna().any(axis=0)]
    if numeric.empty:
        raise ValueError('No numeric signal columns')
    numeric = numeric.replace([np.inf, -np.inf], np.nan)
    numeric = numeric.interpolate(axis=0, limit_direction='both')
    if numeric.isna().any().any():
        raise ValueError('Some channels contain no usable numeric values')
    values = numeric.to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError('Non-finite numeric values remain')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return values, dt, {'filename': path.name, 'sha256': digest,
                        'n_samples': int(values.shape[0]),
                        'original_channels': int(values.shape[1]),
                        'columns': [str(x) for x in numeric.columns]}


def encode_rates(values, n_encoders=32, low_hz=10.0, high_hz=50.0):
    """One independent Poisson encoder per mapped channel replica."""
    a = np.asarray(values, dtype=float)
    mins = a.min(axis=0)
    span = a.max(axis=0) - mins
    scaled = np.divide(a - mins, span, out=np.full_like(a, 0.5), where=span > 0)
    mapping = np.arange(n_encoders) % a.shape[1]
    rates = low_hz + scaled[:, mapping] * (high_hz - low_hz)
    assert rates.shape == (a.shape[0], n_encoders)
    return rates.astype(float), mapping.tolist()


def simulate(data_path, epochs=5, n_reactors=100, n_encoders=32, seed=20261110,
             out_dir=None, max_samples=10000):
    import brian2 as b2
    if epochs < 1 or epochs > 50:
        raise ValueError('epochs must be between 1 and 50')
    if not 1 <= n_reactors <= 1000 or not 1 <= n_encoders <= 256:
        raise ValueError('Network size outside demo bounds')
    values, dt, meta = load_numeric_signal(data_path, max_samples=max_samples)
    rates, mapping = encode_rates(values, n_encoders)
    b2.start_scope()
    b2.seed(seed)
    b2.prefs.codegen.target = 'numpy'  # portable on free Colab; no C compiler required
    b2.defaultclock.dt = 0.1 * b2.ms
    # Repeat the *observed* signal across learning epochs. Stochastic spike
    # realization changes, but real sample-based firing-rate modulation remains.
    repeated = np.tile(rates, (epochs, 1))
    rate_ta = b2.TimedArray(repeated * b2.Hz, dt=dt * b2.second)
    inputs = b2.PoissonGroup(n_encoders, rates='rate_ta(t, i)',
                             namespace={'rate_ta': rate_ta})
    reactors = b2.NeuronGroup(
        n_reactors, 'dv/dt = -v/(20*ms) : 1 (unless refractory)',
        threshold='v > 1', reset='v = 0', refractory=3*b2.ms, method='exact')
    synapses = b2.Synapses(inputs, reactors,
        model="""w : 1
                 dapre/dt = -apre/(20*ms) : 1 (event-driven)
                 dapost/dt = -apost/(20*ms) : 1 (event-driven)""",
        on_pre="""v_post += w
                  apre += 0.01
                  w = clip(w + apost, 0, 1)""",
        on_post="""apost += -0.0105
                   w = clip(w + apre, 0, 1)""")
    synapses.connect(p=0.25)
    synapses.w = '0.40 + 0.20*rand()'
    input_mon = b2.SpikeMonitor(inputs)
    output_mon = b2.SpikeMonitor(reactors)
    network = b2.Network(inputs, reactors, synapses, input_mon, output_mon)
    records = []
    for epoch in range(1, epochs + 1):
        before_in = int(input_mon.num_spikes)
        before_out = int(output_mon.num_spikes)
        # No restore() here: the synaptic weights persist across epochs.
        network.run((len(values) * dt) * b2.second)
        row = {'epoch': epoch, 'input_spikes': int(input_mon.num_spikes)-before_in,
               'reactor_spikes': int(output_mon.num_spikes)-before_out,
               'mean_synaptic_weight': float(np.mean(synapses.w[:]))}
        records.append(row)
        print('epoch={epoch} input_spikes={input_spikes} reactor_spikes={reactor_spikes} mean_w={mean_synaptic_weight:.5f}'.format(**row))
    output = Path(out_dir or Path(data_path).parent / 'results')
    output.mkdir(parents=True, exist_ok=True)
    # Include provenance and model parameters, but no behavioral risk claims.
    metadata = {**meta, 'source': 'file_numeric_signal',
                'encoder': 'minmax_to_inhomogeneous_poisson_10_50Hz',
                'spikes_are_simulated_not_measured': True,
                'num_encoders': n_encoders, 'mapped_channel_indices': mapping,
                'num_reactors': n_reactors, 'dt_seconds': dt,
                'epochs': epochs, 'seed': seed, 'epoch_results': records}
    report = output / 'perceptual_report.json'
    report.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    spikes = output / 'reactor_spikes.csv'
    with spikes.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['reactor_id', 'time_seconds'])
        writer.writerows(zip(np.asarray(output_mon.i[:], dtype=int),
                            np.asarray(output_mon.t[:] / b2.second, dtype=float)))
    print(f'Loaded {len(values)} samples from {meta["filename"]} SHA256={meta["sha256"][:16]}...')
    print(f'Output spikes captured: {int(output_mon.num_spikes)}')
    print(f'Report: {report}\nSpike events: {spikes}')
    return metadata


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('dataset', help='Path to CSV, TSV, or numeric TXT file')
    parser.add_argument('--epochs', type=int, default=5)
    parser.add_argument('--out-dir', default=None)
    args = parser.parse_args()
    simulate(args.dataset, epochs=args.epochs, out_dir=args.out_dir)