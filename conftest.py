# Presence of this file puts the repository root on sys.path so `import src...` works in tests.
import pytest


@pytest.fixture(autouse=True)
def isolated_optional_models(tmp_path, monkeypatch):
    """Local trained artifacts must not change the offline regression baseline."""
    monkeypatch.delenv("AEGM_CONFIG_PATH", raising=False)
    # Tests must not send fixture/user data to a real locally running model.
    monkeypatch.setenv('AEGM_LOCAL_MODELS_DISABLED', '1')
    monkeypatch.setenv('AEGM_LLM_PROVIDER', 'ollama')
    monkeypatch.delenv('AEGM_ALLOW_EXTERNAL_LLM', raising=False)
    monkeypatch.delenv('GROQ_API_KEY', raising=False)
    monkeypatch.setattr("src.cv.attributes.HEAD_PATH", str(tmp_path / "color_head.joblib"))
    monkeypatch.setattr("src.agent.intent_model.MODEL_PATH", str(tmp_path / "intent_clf.joblib"))
