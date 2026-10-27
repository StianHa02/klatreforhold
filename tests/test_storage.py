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
    assert "merge-duplicates" in kw["headers"]["Prefer"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("OK", name)
