# Presence of this file puts the repository root on sys.path so `import src...` works in tests.
import pytest


@pytest.fixture(autouse=True)
def isolated_optional_models(tmp_path, monkeypatch):
    """Local trained artifacts must not change the offline regression baseline."""
    monkeypatch.setattr("src.cv.attributes.HEAD_PATH", str(tmp_path / "color_head.joblib"))
    monkeypatch.setattr("src.agent.intent_model.MODEL_PATH", str(tmp_path / "intent_clf.joblib"))
