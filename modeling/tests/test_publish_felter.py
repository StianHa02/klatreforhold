import pytest

from klatreforhold import publish


def _falsk_predict(slug, **_):
    return {"generert": "2026-11-06T10:00:00+00:00", "timer": [], "sammendrag": {"status_na": "tort"}}


def test_publish_all_bare_valgte_felt(monkeypatch):
    monkeypatch.setattr(publish, "predict", _falsk_predict)
    res = publish.publish_all(None, dry_run=True, felter=["uteveggen"])
    assert list(res) == ["uteveggen"]


def test_publish_all_ukjent_felt(monkeypatch):
    monkeypatch.setattr(publish, "predict", _falsk_predict)
    with pytest.raises(KeyError):
        publish.publish_all(None, dry_run=True, felter=["finnes-ikke"])
