"""Tester lagringslaget uten nett: CSV på disk og Supabase med falsk HTTP-sesjon."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from klatreforhold.storage import CsvStorage, SupabaseStorage  # noqa: E402

ROW = {"time": "2026-10-08T07:30:00+00:00", "status": "fuktig", "predikert_status": "vatt", "riktig": 1,
       "kommentar": "test", "kilde": "test", "registrert": "2026-10-27T15:00:00+00:00"}


def test_csv_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        st = CsvStorage(Path(d))
        assert st.list_observations("x").empty
        st.add_observation("x", ROW)
        st.add_observation("x", {**ROW, "status": "tort", "riktig": 0})
        df = st.list_observations("x")
        assert len(df) == 2 and df.iloc[0]["status"] == "tort"


class FakeResp:
    def __init__(self, js=None):
        self._js = js or []

    def raise_for_status(self):
        pass

    def json(self):
        return self._js


class FakeSession:
    def __init__(self):
        self.calls = []
        self.headers = {}

    def post(self, url, **kw):
        self.calls.append(("POST", url, kw))
        return FakeResp()

    def get(self, url, **kw):
        self.calls.append(("GET", url, kw))
        return FakeResp([{"tid": ROW["time"], "status": "fuktig", "predikert_status": "vatt", "riktig": True,
                          "kommentar": None, "kilde": "web", "registrert": ROW["registrert"]}])


def test_supabase_payloads():
    st = SupabaseStorage("https://abc.supabase.co", "key")
    st.s = FakeSession()
    st.add_observation("ekstraveggen", ROW)
    _, url, kw = st.s.calls[-1]
    assert url.endswith("/rest/v1/observasjoner")
    assert kw["json"] == {"felt": "ekstraveggen", "tid": ROW["time"], "status": "fuktig", "predikert_status": "vatt",
                          "riktig": True, "kommentar": "test", "kilde": "test"}
    df = st.list_observations("ekstraveggen")
    assert df.iloc[0]["riktig"] == 1 and "time" in df
    n = st.save_forecast("ekstraveggen", [{"felt": "ekstraveggen", "generert": "x", "tid": "y"}])
    _, url, kw = st.s.calls[-1]
    assert n == 1 and kw["params"]["on_conflict"] == "felt,generert,tid"
    assert "ignore-duplicates" in kw["headers"]["Prefer"]


def test_training_excludes_dev():
    st = SupabaseStorage("https://abc.supabase.co", "key")
    st.s = FakeSession()
    st.all_observations("ekstraveggen")
    _, _, kw = st.s.calls[-1]
    assert kw["params"]["kilde"] == "not.in.(dev,test)"
    st.all_observations("ekstraveggen", include_dev=True)
    assert "kilde" not in st.s.calls[-1][2]["params"]


def test_labels_from_supabase_rows():
    import pandas as pd
    from klatreforhold.ml.features import labels_from_frame
    df = pd.DataFrame([{"tid": "2026-10-27T13:30:00+00:00", "status": "tort"},
                       {"tid": "2026-10-27T14:10:00+00:00", "status": "fuktig"}])
    y = labels_from_frame(df)
    assert y.tolist() == [False, True] and str(y.index[0]) == "2026-10-27 14:00:00+00:00"
    assert labels_from_frame(pd.DataFrame()).empty


def test_dotenv_does_not_override():
    import os
    from klatreforhold.config import _load_dotenv
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / ".env"
        p.write_text("# kommentar\nKF_TEST_A=fra_fil\nKF_TEST_B = 'sitert'\n", encoding="utf-8")
        os.environ["KF_TEST_A"] = "fra_miljo"
        _load_dotenv(p)
        assert os.environ["KF_TEST_A"] == "fra_miljo" and os.environ["KF_TEST_B"] == "sitert"


def test_checkpoint_selects_compatible_past_state():
    import pandas as pd
    with tempfile.TemporaryDirectory() as d:
        st = CsvStorage(Path(d))
        rows = [{"felt": "test", "tid": t, "config_hash": h, "model_version": "2.0.0", "state": {"ice_film": 2.}}
                for t, h in [("2026-10-01T00:00Z", "a"), ("2026-10-02T00:00Z", "a"), ("2026-10-03T00:00Z", "b")]]
        st.save_checkpoints(rows)
        hit = st.load_checkpoint("test", pd.Timestamp("2026-10-02T12:00Z"), "a")
        assert hit["tid"] == "2026-10-02T00:00Z" and hit["state"]["ice_film"] == 2.
        assert st.load_checkpoint("test", pd.Timestamp("2026-09-01T00:00Z"), "a") is None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK", name)
