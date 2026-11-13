"""Fail-closed audit and plots for Selma Perceptual Operator simulated spike output."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path


def verify(dataset, report_path, spikes_path):
    dataset, report_path, spikes_path = map(Path, (dataset, report_path, spikes_path))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    expected_hash = hashlib.sha256(dataset.read_bytes()).hexdigest()
    if report.get("sha256") != expected_hash:
        raise ValueError("Dataset SHA256 differs from run report")
    if report.get("filename") != dataset.name:
        raise ValueError("Dataset filename differs from run report")
    if report.get("spikes_are_simulated_not_measured") is not True:
        raise ValueError("This verifier expects explicitly labeled simulated spikes")
    n_epochs = int(report["epochs"])
    n_samples = int(report["n_samples"])
    dt = float(report["dt_seconds"])
    n_reactors = int(report["num_reactors"])
    if not 1 <= n_epochs <= 50 or n_samples < 2 or not 0 < dt <= 1 or n_reactors <= 0:
        raise ValueError("Invalid time or reactor metadata")
    epoch_seconds = n_samples * dt
    rows = report["epoch_results"]
    if len(rows) != n_epochs or any(int(r["epoch"]) != idx + 1 for idx, r in enumerate(rows)):
        raise ValueError("Epoch numbering/report length mismatch")
    weights = [float(r["mean_synaptic_weight"]) for r in rows]
    if any(not math.isfinite(w) or not 0 <= w <= 1 for w in weights):
        raise ValueError("Invalid synaptic weight")
    counted = [0] * n_epochs
    raster = []
    with spikes_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if set(reader.fieldnames or []) != {"reactor_id", "time_seconds"}:
            raise ValueError("Unexpected spike CSV columns")
        for record in reader:
            reactor_id = int(record["reactor_id"])
            t = float(record["time_seconds"])
            if not (0 <= reactor_id < n_reactors and math.isfinite(t)
                    and 0 <= t < n_epochs * epoch_seconds + 1e-9):
                raise ValueError("Invalid spike neuron index or time")
            epoch_idx = min(int(t / epoch_seconds), n_epochs - 1)
            counted[epoch_idx] += 1
            if epoch_idx == 0 and len(raster) < 20000:
                raster.append((t, reactor_id))
    expected = [int(r["reactor_spikes"]) for r in rows]
    if counted != expected:
        raise ValueError(f"Reported spike counts {expected} do not equal CSV counts {counted}")
    return {
        "verified": True,
        "data_source": report["source"],
        "spikes_are_simulated_not_measured": True,
        "dataset_sha256": expected_hash,
        "epochs": n_epochs,
        "spike_counts": counted,
        "total_reactor_spikes": sum(counted),
        "mean_synaptic_weights": weights,
        "saturation_warning": any(w >= 0.9 for w in weights),
    }, raster


def save_plots(summary, raster, out_dir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 4))
    if raster:
        ax.scatter([p[0] for p in raster], [p[1] for p in raster], s=1)
    ax.set(xlabel="Simulation time (s)", ylabel="Reactor ID", title="Simulated reactor spikes: epoch 1")
    fig.tight_layout()
    fig.savefig(out_dir / "reactor_raster.png", dpi=150)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(range(1, summary["epochs"] + 1), summary["mean_synaptic_weights"], marker="o")
    ax.set(xlabel="Epoch", ylabel="Mean synaptic weight", ylim=(0, 1), title="STDP weight progression")
    fig.tight_layout()
    fig.savefig(out_dir / "learning_progression.png", dpi=150)
    plt.close(fig)
    (out_dir / "verification.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset")
    parser.add_argument("report")
    parser.add_argument("spikes")
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    summary, raster = verify(args.dataset, args.report, args.spikes)
    save_plots(summary, raster, args.out_dir)
    print(json.dumps(summary, indent=2))