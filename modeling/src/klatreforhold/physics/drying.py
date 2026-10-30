"""Tørkeepisoder med eksplisitte avslutninger, uten å skjule nytt regn eller sensurering."""
import numpy as np
import pandas as pd


def drying_events(weather, result, min_rain_mm=2., cap_h=72):
    w = weather.asfreq("h")
    r = result.reindex(w.index)
    p = w.precipitation.to_numpy(float)
    total12 = w.precipitation.rolling(12, min_periods=12).sum().to_numpy()
    rows = []
    for i in range(len(w)):
        if not (p[i] >= .2 and total12[i] >= min_rain_mm):
            continue
        following = p[i+1:i+4]
        if (following >= .2).any():
            continue
        outcome, elapsed = "ufullstendig", 0
        winter = False
        if len(following) == 3 and np.isfinite(following).all():
            for j in range(i, min(i + cap_h + 1, len(w))):
                elapsed = j - i
                row = r.iloc[j]
                if not np.isfinite(p[j]) or pd.isna(row.get("wet")):
                    break
                winter = winter or row.get("status") == "is" or row.get("snowfall_mm", 0) > 0
                if j > i and p[j] >= .2:
                    outcome = "nytt_regn"
                    break
                if not bool(row.wet):
                    outcome = "tort"
                    break
                if elapsed == cap_h:
                    outcome = "fortsatt_vatt"
        rows.append({"slutt": w.index[i], "timer": elapsed, "utfall": outcome, "vinterpaavirket": winter})
    return pd.DataFrame(rows, columns=["slutt", "timer", "utfall", "vinterpaavirket"])


def summarize_events(events):
    ordinary = events[~events.vinterpaavirket.astype(bool)]
    completed = ordinary.loc[ordinary.utfall == "tort", "timer"]
    quantiles = None if completed.empty else {
        "median": float(completed.median()), "q25": float(completed.quantile(.25)),
        "q75": float(completed.quantile(.75)), "n": int(len(completed))}
    counts = {k: int((ordinary.utfall == k).sum()) for k in ("tort", "nytt_regn", "fortsatt_vatt", "ufullstendig")}
    incidence = {}
    for hours in (6, 12, 24):
        # Regn er en konkurrerende avslutning, ikke uavhengig sensurering.
        known = ordinary[(ordinary.utfall != "ufullstendig") | (ordinary.timer >= hours)]
        successes = ((known.utfall == "tort") & (known.timer <= hours)).sum()
        incidence[str(hours)] = {"andel": float(successes / len(known)) if len(known) else None,
                                 "n": len(known), "ukjent": len(ordinary) - len(known)}
    return {"fullfort": quantiles, "utfall": counts, "innen_timer": incidence,
            "n": len(events), "vinterpaavirket": int(events.vinterpaavirket.sum())}
