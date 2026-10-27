"""Felles henting av etiketter: fil(er) eller 'supabase'."""
from pathlib import Path

import pandas as pd

from klatreforhold.ml.features import labels_from_frame, load_labels


def get_labels(sources, config_path, timezone="Europe/Oslo", med_dev=False) -> pd.Series:
    parts = []
    for src in sources:
        if src == "supabase":
            from klatreforhold.storage import SupabaseStorage, get_storage
            st = get_storage()
            if not isinstance(st, SupabaseStorage):
                raise SystemExit("'supabase' krever SUPABASE_URL og SUPABASE_SERVICE_ROLE_KEY (f.eks. i .env)")
            df = st.all_observations(Path(config_path).stem, include_dev=med_dev)
            print(f"Hentet {len(df)} observasjoner fra Supabase")
            parts.append(labels_from_frame(df, timezone))
        else:
            parts.append(load_labels(src, timezone))
    y = pd.concat(parts) if parts else pd.Series(dtype=bool)
    return y.groupby(level=0).max().astype(bool) if len(y) else y
