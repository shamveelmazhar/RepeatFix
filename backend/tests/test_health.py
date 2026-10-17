import app.main as m


class Down:
    def with_options(self, **kwargs):
        raise RuntimeError("down")


def test_health_reports_model_down(monkeypatch):
    monkeypatch.setattr(m.extract_module, "get_client", lambda: Down())
    monkeypatch.setattr(m, "_health_cache", {"at": 0.0, "model_ok": False})
    assert m.health() == {"ok": True, "vllm": False, "evolus": False}