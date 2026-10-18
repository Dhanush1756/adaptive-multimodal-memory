"""AppTest integration, explicitly not a real-browser demonstration."""
from copy import deepcopy
from pathlib import Path

import pytest

from src.config import load_config


def input_value(app, label, value):
    next(x for x in app.text_input if x.label == label).set_value(value)


def button(app, label):
    # AppTest retains a stale login-form node for one tree after st.rerun.
    # Explicit values avoid reading a removed widget's session-state entry.
    # This does not inject a token or bypass the actual login form.
    if label != "Login" and app.chat_input:
        for item in app.text_input:
            if item.label in {"Username", "Password"}:
                item.set_value("")
    next(x for x in app.button if x.label == label).click().run(timeout=15)
    assert not app.exception


def send(app, text):
    # Multimodal composer text is exercised through Streamlit's real widget serde.
    for item in app.text_input:
        if item.label in {'Username', 'Password'}:
            item.set_value('')
    app.chat_input[0].set_value(text).run(timeout=15)
    assert not app.exception


@pytest.mark.parametrize('human_choice', ['red', 'white'])
def test_account_ui_register_login_remember_logout_and_return(tmp_path, monkeypatch, human_choice):
    from streamlit.testing.v1 import AppTest
    cfg = load_config()
    cfg["paths"]["db_path"] = str(tmp_path / "app" / "memory.db")
    monkeypatch.setattr("src.config.load_config", lambda: deepcopy(cfg))
    path = str(Path(__file__).resolve().parents[1] / "app" / "account_app.py")
    app = AppTest.from_file(path).run(timeout=15)
    assert not app.exception
    assert not app.chat_input  # unauthenticated UI cannot show memories or uploads
    app.radio[0].set_value("Register").run()
    input_value(app, "Username", "alice")
    input_value(app, "Password", "a unique long password")
    button(app, "Register")
    app.radio[0].set_value("Login").run()
    input_value(app, "Username", "alice")
    input_value(app, "Password", "a unique long password")
    button(app, "Login")
    assert app.chat_input
    assert len(app.chat_input) == 1 and not app.text_area
    next(t for t in app.toggle if t.label == 'Remember this').set_value(True).run()
    send(app, 'Bring the handmade folder to the Friday review')
    assert any('Pinned as important' in x.value for x in app.markdown)
    assert not app.session_state['remember_next']
    send(app, 'Show my saved notes')
    assert app.session_state['answer'].found
    assert 'handmade folder' in app.session_state['answer'].text
    send(app, "My project model is CLIP.")
    button(app, "New chat")
    assert not app.chat_message
    send(app, "What is my project model?")
    assert app.session_state['answer'].found and app.session_state['answer'].value == 'clip'
    # A stale closed workspace can survive an interrupted rerun in session state.
    # Reopen its same account database; never reset it or lose its evidence.
    old_workspace = app.session_state['workspace']
    # Inspect the temporary memory store (which supports cross-thread access),
    # not the app thread's short-lived account registry from the test thread.
    original_memories = [row.to_dict() for row in old_workspace.agent.store.all()]
    original_conversation = app.session_state['conversation']
    old_workspace.close()
    app.run(timeout=15)
    assert not app.exception
    assert app.session_state['workspace'] is not old_workspace
    assert app.session_state['conversation'] == original_conversation
    assert [row.to_dict() for row in app.session_state['workspace'].agent.store.all()] == original_memories
    send(app, 'What is my project model?')
    assert app.session_state['answer'].found and app.session_state['answer'].value == 'clip'
    send(app, "My project named atlas deadline is 2026-12-01.")
    send(app, "What is the deadline for project named atlas?")
    assert any("deadline: 2026-12-01" in x.value for x in app.markdown)
    # AppTest does not provide an upload setter for multimodal chat_input.
    # Keep the real widget mounted and inject only its returned upload payload;
    # decoding, chat, persistence and verification still use the actual code.
    import io
    from types import SimpleNamespace
    import streamlit as st
    from PIL import Image
    original_composer = st.chat_input
    queued = []
    def uploaded_turn(*args, **kwargs):
        actual = original_composer(*args, **kwargs)
        return queued.pop(0) if queued else actual
    monkeypatch.setattr(st, 'chat_input', uploaded_turn)
    queued.append(SimpleNamespace(text='My phone is green.', files=[io.BytesIO(b'invalid image')]))
    app.run(timeout=15)
    assert not app.exception
    assert any('could not be decoded' in w.value for w in app.warning)
    assert any(r.entity == 'phone' and r.value == 'green' for r in app.session_state['workspace'].agent.store.all())

    send(app, 'My first car is red.')
    photo = io.BytesIO()
    Image.new('RGB', (64,64), 'white').save(photo, format='PNG')
    photo.seek(0)
    queued.append(SimpleNamespace(text='My first car is red.', files=[photo]))
    app.run(timeout=15)
    assert not app.exception
    assert any(r.label == 'Accept value' for r in app.radio)
    assert app.get('imgs')  # saved visual evidence is visible with the chat
    next(r for r in app.radio if r.label == 'Accept value').set_value(human_choice)
    input_value(app, 'Rationale (optional)', f'Accept {human_choice} for this UI regression.')
    button(app, 'Resolve disagreement')
    assert not any(r.label == 'Accept value' for r in app.radio)
    assert any(row['selected_value'] == human_choice for row in app.session_state['workspace'].agent.conflict_audit())
    button(app, "Logout")
    assert not app.chat_input
    assert not app.chat_message
    input_value(app, "Username", "alice")
    input_value(app, "Password", "a unique long password")
    button(app, "Login")
    send(app, "What is my project model?")
    assert app.session_state['answer'].found and app.session_state['answer'].value == 'clip'
    button(app, "Logout")
