"""Real test case: train a small CNN on CIFAR-10 and measure the energy it uses.

CodeCarbon samples GPU power from NVML (measured) and estimates CPU/RAM power
(on Windows CPU is a TDP-based estimate, there is no RAPL). We record kWh, then
price that same energy at each hour of India's grid in experiments/compare.py.

    python experiments/laptop_train.py --epochs 8
"""
import os

for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import datetime as dt
import json
import pickle
import tarfile
import time
import urllib.request
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from codecarbon import OfflineEmissionsTracker

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "cifar10"
URL = "https://cave.cs.toronto.edu/kriz/cifar-10-python.tar.gz"


def load_cifar():
    tgz = CACHE / "cifar-10-python.tar.gz"
    if not (CACHE / "cifar-10-batches-py").exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        if not tgz.exists():
            print("downloading CIFAR-10 (163 MB)...", flush=True)
            part = tgz.with_suffix(".part")  # only a finished download gets the real name
            urllib.request.urlretrieve(URL, part)
            part.replace(tgz)
        with tarfile.open(tgz) as t:
            t.extractall(CACHE, filter="data")
    def batch(name):
        with open(CACHE / "cifar-10-batches-py" / name, "rb") as f:
            d = pickle.load(f, encoding="bytes")
        return d[b"data"].reshape(-1, 3, 32, 32), np.array(d[b"labels"])
    parts = [batch(f"data_batch_{i}") for i in range(1, 6)]
    xtr = np.concatenate([p[0] for p in parts]); ytr = np.concatenate([p[1] for p in parts])
    xte, yte = batch("test_batch")
    return xtr, ytr, xte, yte


class Net(nn.Module):
    """A ~1.1M-param VGG-style CNN; big enough to keep a GTX 1650 busy."""
    def __init__(self):
        super().__init__()
        def block(i, o):
            return nn.Sequential(nn.Conv2d(i, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU(),
                                 nn.Conv2d(o, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU(),
                                 nn.MaxPool2d(2))
        self.features = nn.Sequential(block(3, 64), block(64, 128), block(128, 256))
        self.head = nn.Linear(256, 10)

    def forward(self, x):
        return self.head(F.adaptive_avg_pool2d(self.features(x), 1).flatten(1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--batch", type=int, default=128)
    args = ap.parse_args()

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    xtr, ytr, xte, yte = load_cifar()
    # Standard CIFAR-10 channel stats. Keep raw uint8 images on the GPU (~180 MB of VRAM) and normalise per batch,
    # so host RAM never holds a float copy of the dataset.
    mean = torch.tensor([125.3, 123.0, 113.9], device=dev).view(1, 3, 1, 1)
    std = torch.tensor([63.0, 62.1, 66.7], device=dev).view(1, 3, 1, 1)
    Xtr, Ytr = torch.from_numpy(xtr).to(dev), torch.from_numpy(ytr).long().to(dev)
    Xte, Yte = torch.from_numpy(xte).to(dev), torch.from_numpy(yte).long().to(dev)
    del xtr, xte
    norm = lambda x: (x.float() - mean) / std

    torch.manual_seed(0)
    model = Net().to(dev)
    opt = torch.optim.SGD(model.parameters(), lr=0.05, momentum=0.9, weight_decay=5e-4, nesterov=True)
    steps = args.epochs * (len(Xtr) // args.batch)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, 0.1, total_steps=steps)

    tracker = OfflineEmissionsTracker(country_iso_code="IND", project_name="cleanhour-cifar10",
                                      measure_power_secs=5, output_dir=str(ROOT / "data"),
                                      log_level="error")
    started = dt.datetime.now()
    tracker.start()
    t0 = time.time()
    for ep in range(args.epochs):
        model.train()
        perm = torch.randperm(len(Xtr), device=dev)
        for i in range(len(Xtr) // args.batch):
            idx = perm[i * args.batch:(i + 1) * args.batch]
            xb, yb = norm(Xtr[idx]), Ytr[idx]
            if torch.rand(1).item() < 0.5:
                xb = xb.flip(3)  # cheap augmentation
            loss = F.cross_entropy(model(xb), yb)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step(); sched.step()
        model.eval()
        with torch.no_grad():
            acc = sum((model(norm(Xte[j:j + 1000])).argmax(1) == Yte[j:j + 1000]).sum().item()
                      for j in range(0, len(Xte), 1000)) / len(Xte)
        print(f"epoch {ep + 1}/{args.epochs}  loss {loss.item():.3f}  test acc {acc:.3f}  "
              f"{time.time() - t0:.0f}s", flush=True)
    tracker.stop()
    d = tracker.final_emissions_data

    out = {
        "model": "VGG-style CNN (1.1M params), CIFAR-10",
        "device": torch.cuda.get_device_name(0) if dev == "cuda" else "cpu",
        "epochs": args.epochs,
        "test_accuracy": round(acc, 4),
        "started": started.isoformat(timespec="seconds"),
        "duration_s": round(d.duration, 1),
        "energy_kwh": round(d.energy_consumed, 6),
        "gpu_kwh": round(d.gpu_energy, 6),
        "cpu_kwh": round(d.cpu_energy, 6),
        "ram_kwh": round(d.ram_energy, 6),
        "avg_gpu_w": round(d.gpu_power, 1),
        "avg_cpu_w": round(d.cpu_power, 1),
        "codecarbon_version": d.codecarbon_version,
        "codecarbon_india_kg": round(d.emissions, 6),
    }
    (ROOT / "data" / "experiment_raw.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
