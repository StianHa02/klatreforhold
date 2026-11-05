"""Tester Parquet-arkivet uten nett: falsk PostgREST og Storage i minnet."""
import datetime as dt
import hashlib
import sys
import tempfile
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from klatreforhold import arkiv  # noqa: E402
from klatreforhold.storage import SupabaseStorage  # noqa: E402

D1, D2 = dt.date(2026, 11, 1), dt.date(2026, 11, 2)


def varselrad(generert, tid, ledetid, felt="ekstraveggen"):
    return {"felt": felt, "generert": generert, "tid": tid, "ledetid_timer": ledetid, "status": "tort",
            "vann_mm": 0.25, "p_vatt": None, "bergtemp": 7.5, "duggpunkt": 3.1, "nedbor_mm": 0.0,
            "regn_mot_veggen_mm": 0.0, "sol_pa_veggen": True, "modellversjon": "2.0.0", "konfigurasjon": "abc",
            "is_mm": 0.0, "sno_mm": None, "vaerkilde": "metnordic"}


def dagrader(dato, n_felt=1):
    """24 kjøringer x 49 ledetider per felt: 1176 rader per felt, mer enn én side (1000)."""
    rader = []
    for f in range(n_felt):
        for h in range(24):
            gen = pd.Timestamp(dato, tz="UTC") + pd.Timedelta(hours=h, minutes=7)
            for l in range(49):
                rader.append(varselrad(gen.isoformat(), (gen.floor("h") + pd.Timedelta(hours=l)).isoformat(), l,
                                       felt=f"felt{f}"))
    return rader


class Resp:
    def __init__(self, js=None, content=b"", status=200):
        self._js, self.content, self.status = js, content, status

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f"HTTP {self.status}")

    def json(self):
        return self._js


class FakeSupabase:
    """Nok av PostgREST (filter på generert, Range-sider) og Storage til arkiv-modulen."""

    def __init__(self, tabeller, korrupt=False):
        self.tabeller = tabeller
        self.kvitteringer = []
        self.objekter = {}
        self.korrupt = korrupt
        self.headers = {}

    def _filtrer(self, rows, params):
        for k, v in (params.items() if isinstance(params, dict) else params):
            if k == "generert" and v.startswith("gte."):
                rows = [r for r in rows if pd.Timestamp(r["generert"]) >= pd.Timestamp(v[4:])]
            elif k == "generert" and v.startswith("lt."):
                rows = [r for r in rows if pd.Timestamp(r["generert"]) < pd.Timestamp(v[3:])]
            elif k == "tabell":
                rows = [r for r in rows if r["tabell"] == v[3:]]
        return rows

    def get(self, url, params=None, headers=None, **kw):
        if "/storage/v1/object/arkiv/" in url:
            path = url.split("/object/arkiv/", 1)[1]
            data = self.objekter[path]
            return Resp(content=data[:-1] + b"x" if self.korrupt else data)
        table = url.rsplit("/", 1)[1]
        rows = self.kvitteringer if table == "arkiv_eksport" else self.tabeller.get(table, [])
        rows = sorted(self._filtrer(rows, params or {}), key=lambda r: r.get("generert", ""))
        if isinstance(params, dict) and params.get("limit"):
            rows = rows[:int(params["limit"])]
        if headers and "Range" in headers:
            a, b = map(int, headers["Range"].split("-"))
            rows = rows[a:b + 1]
        return Resp(rows)

    def post(self, url, json=None, data=None, headers=None, **kw):
        if "/storage/v1/object/arkiv/" in url:
            assert headers["x-upsert"] == "true"
            self.objekter[url.split("/object/arkiv/", 1)[1]] = data
            return Resp()
        assert url.endswith("/rest/v1/arkiv_eksport")
        for k in json:
            self.kvitteringer = [r for r in self.kvitteringer if (r["tabell"], r["dato"]) != (k["tabell"], k["dato"])]
            self.kvitteringer.append(k)
        return Resp()


def lag(tabeller, **kw):
    st = SupabaseStorage("https://abc.supabase.co", "key")
    st.s = FakeSupabase(tabeller, **kw)
    return st


def test_sti():
    assert arkiv.sti("varsel", D1) == "varsel/2026-11/varsel_2026-11-01.parquet"


def test_typer_bevares_i_parquet():
    df = arkiv.typet(pd.DataFrame(dagrader(D1)[:3]), "varsel")
    tilbake = pd.read_parquet(__import__("io").BytesIO(arkiv.til_parquet(df)))
    assert str(tilbake["generert"].dtype) == "datetime64[us, UTC]"
    assert tilbake["ledetid_timer"].dtype == "Int16" and tilbake["vann_mm"].dtype == "float32"
    assert tilbake["sol_pa_veggen"].dtype == "boolean" and tilbake["status"].dtype == "string"
    assert tilbake["p_vatt"].isna().all() and tilbake["vann_mm"].iloc[0] == pytest.approx(0.25)


def test_eksport_laster_opp_kontrollerer_og_kvitterer():
    rader = dagrader(D1, n_felt=2) + dagrader(D2)
    st = lag({"varsel": rader, "stasjon_varsel": []})
    with tempfile.TemporaryDirectory() as d:
        ut = arkiv.eksporter(st, til=D2, tabeller=["varsel", "stasjon_varsel"], lokal=Path(d), logg=lambda s: None)
        assert [(k["dato"], k["rader"]) for k in ut] == [("2026-11-01", 2352), ("2026-11-02", 1176)]
        k = st.s.kvitteringer[0]
        lokal = Path(d) / k["fil"]
        assert hashlib.sha256(lokal.read_bytes()).hexdigest() == k["sha256"] == \
            hashlib.sha256(st.s.objekter[k["fil"]]).hexdigest()
        df = pd.read_parquet(lokal)
        assert len(df) == 2352 and df["ledetid_timer"].nunique() == 49  # alle ledetider, alle sider

        # Andre kjøring: alt er kvittert, ingenting gjøres på nytt
        assert arkiv.eksporter(st, til=D2, lokal=Path(d), logg=lambda s: None) == []


def test_dry_run_skriver_bare_lokalt():
    st = lag({"varsel": dagrader(D1), "stasjon_varsel": []})
    with tempfile.TemporaryDirectory() as d:
        ut = arkiv.eksporter(st, til=D1, lokal=Path(d), dry_run=True, logg=lambda s: None)
        assert ut[0]["rader"] == 1176 and (Path(d) / ut[0]["fil"]).exists()
        assert st.s.objekter == {} and st.s.kvitteringer == []


def test_avvik_i_storage_gir_ingen_kvittering():
    st = lag({"varsel": dagrader(D1), "stasjon_varsel": []}, korrupt=True)
    with tempfile.TemporaryDirectory() as d, pytest.raises(RuntimeError, match="stemmer ikke"):
        arkiv.eksporter(st, til=D1, lokal=Path(d), logg=lambda s: None)
    assert st.s.kvitteringer == []


def test_tomme_dogn_hoppes_over_og_i_dag_avvises():
    st = lag({"varsel": dagrader(D1) + dagrader(dt.date(2026, 11, 3)), "stasjon_varsel": []})
    with tempfile.TemporaryDirectory() as d:
        ut = arkiv.eksporter(st, til=dt.date(2026, 11, 3), tabeller=["varsel"], lokal=Path(d), logg=lambda s: None)
        assert [k["rader"] for k in ut] == [1176, 0, 1176]
        assert [k["dato"] for k in st.s.kvitteringer] == ["2026-11-01", "2026-11-03"]
        with pytest.raises(ValueError, match="ferdig døgn"):
            arkiv.eksporter(st, til=dt.datetime.now(dt.timezone.utc).date(), lokal=Path(d))


def test_hent_og_les_arkiv():
    st = lag({"varsel": dagrader(D1) + dagrader(D2), "stasjon_varsel": []})
    with tempfile.TemporaryDirectory() as kilde, tempfile.TemporaryDirectory() as maal:
        arkiv.eksporter(st, til=D2, tabeller=["varsel"], lokal=Path(kilde), logg=lambda s: None)
        assert arkiv.hent(st, lokal=Path(maal), logg=lambda s: None) == 2
        assert arkiv.hent(st, lokal=Path(maal), logg=lambda s: None) == 0  # allerede lokalt og lik sha256
        df = arkiv.les_arkiv("varsel", lokal=Path(maal))
        assert len(df) == 2 * 1176 and df["generert"].dt.date.nunique() == 2
