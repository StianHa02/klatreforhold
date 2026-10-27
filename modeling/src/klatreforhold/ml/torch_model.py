"""PyTorch-modell: en liten GRU som ser de siste `window` timene med vær + fysikktilstand
og gir sannsynlighet for at veggen er våt. Bruker CUDA (f.eks. RTX 5070) automatisk hvis tilgjengelig.

Trenes på etiketter fra brukere (data/labels/*_observasjoner.csv). Med få etiketter er det
fysikkfeaturene som gjør jobben; GRU-en lærer korreksjoner.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def _device(prefer: str | None = None) -> str:
    import torch
    if prefer:
        return prefer
    return "cuda" if torch.cuda.is_available() else "cpu"


class GRUWetModel:
    def __init__(self, cols: list[str], window: int = 48, hidden: int = 32):
        self.cols = list(cols)
        self.window = window
        self.hidden = hidden
        self.mu = None
        self.sd = None
        self.net = None

    def _build(self):
        import torch
        from torch import nn

        class Net(nn.Module):
            def __init__(self, n_in, hidden):
                super().__init__()
                self.gru = nn.GRU(n_in, hidden, batch_first=True)
                self.head = nn.Linear(hidden, 1)

            def forward(self, x):
                out, _ = self.gru(x)
                return self.head(out[:, -1]).squeeze(-1)

        torch.manual_seed(0)
        self.net = Net(len(self.cols), self.hidden)

    def _matrix(self, X: pd.DataFrame):
        import torch
        Xf = X[self.cols].astype(float).ffill().fillna(0.0)
        Z = ((Xf - self.mu) / self.sd).to_numpy(dtype=np.float32)
        return Xf.index, torch.from_numpy(Z)

    def _windows(self, Z, positions):
        import torch
        return torch.stack([Z[i - self.window + 1:i + 1] for i in positions])

    def fit(self, X: pd.DataFrame, y: pd.Series, train_times, epochs: int = 40, lr: float = 3e-3,
            batch_size: int = 128, device: str | None = None, verbose: bool = True):
        import torch
        from torch import nn

        dev = _device(device)
        Xf = X[self.cols].astype(float)
        self.mu = Xf.loc[train_times].mean().fillna(0.0)
        self.sd = Xf.loc[train_times].std().replace(0, 1).fillna(1.0)
        idx, Z = self._matrix(X)
        pos = {t: i for i, t in enumerate(idx)}
        positions = [pos[t] for t in train_times if t in pos and pos[t] >= self.window - 1]
        if len(positions) < 10:
            raise ValueError(f"For få etiketter med {self.window} t historikk ({len(positions)})")
        xs = self._windows(Z, positions)
        ys = torch.tensor(y.loc[[idx[i] for i in positions]].astype(float).to_numpy(), dtype=torch.float32)
        self._build()
        self.net.to(dev)
        frac = float(ys.mean())
        pos_weight = torch.tensor((1 - frac) / max(frac, 1e-3), device=dev)
        lossf = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
        opt = torch.optim.Adam(self.net.parameters(), lr=lr, weight_decay=1e-4)
        dl = torch.utils.data.DataLoader(torch.utils.data.TensorDataset(xs, ys), batch_size=batch_size, shuffle=True)
        for ep in range(epochs):
            self.net.train()
            tot = 0.0
            for xb, yb in dl:
                xb, yb = xb.to(dev), yb.to(dev)
                opt.zero_grad()
                loss = lossf(self.net(xb), yb)
                loss.backward()
                opt.step()
                tot += float(loss.detach()) * len(xb)
            if verbose and (ep % 10 == 0 or ep == epochs - 1):
                print(f"  epoke {ep:3d}  tap {tot / len(xs):.4f}  ({dev})")
        self.net.to("cpu")
        return self

    def predict_proba(self, X: pd.DataFrame, batch_size: int = 512) -> pd.Series:
        """Sannsynlighet for vått per time (NaN for de første window-1 timene)."""
        import torch
        idx, Z = self._matrix(X)
        positions = list(range(self.window - 1, len(idx)))
        out = np.full(len(idx), np.nan)
        self.net.eval()
        with torch.no_grad():
            for s in range(0, len(positions), batch_size):
                chunk = positions[s:s + batch_size]
                p = torch.sigmoid(self.net(self._windows(Z, chunk))).numpy()
                out[chunk] = p
        return pd.Series(out, index=idx, name="p_vatt")

    def save(self, path: str | Path):
        import torch
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        torch.save({"cols": self.cols, "window": self.window, "hidden": self.hidden,
                    "mu": self.mu.to_dict(), "sd": self.sd.to_dict(), "state_dict": self.net.state_dict()}, path)

    @classmethod
    def load(cls, path: str | Path) -> "GRUWetModel":
        import torch
        d = torch.load(path, map_location="cpu", weights_only=False)
        m = cls(d["cols"], d["window"], d["hidden"])
        m.mu = pd.Series(d["mu"])
        m.sd = pd.Series(d["sd"])
        m._build()
        m.net.load_state_dict(d["state_dict"])
        m.net.eval()
        return m
