"""Authenticated local research interface; legacy demo stays available separately.

python -m streamlit run app/account_app.py --server.address 127.0.0.1
"""
from pathlib import Path
import sys
import sqlite3
import json
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st
from PIL import Image

from src.accounts import Accounts, AuthenticationError
from src.config import load_config, resolve_path
from src.conversations import Conversations

st.set_page_config(page_title="Adaptive Memory", page_icon="\u25c8", layout="wide")
st.markdown('<style>' + Path(__file__).with_name('chat.css').read_text(encoding='utf-8') + '</style>', unsafe_allow_html=True)
cfg = load_config()
base = Path(resolve_path(cfg["paths"]["db_path"])).parent / "authenticated"
accounts = Accounts(base / "accounts.db")


def close_workspace():
    existing = st.session_state.pop("workspace", None)
    if existing:
        existing.close()
    for key in ("login_token", "conversation", "pending", "answer", "ingest", "chosen_conversation", "chat_selections", "chat_notes", "remember_next", "remember_submitted"):
        st.session_state.pop(key, None)


token = st.session_state.get("login_token")
if token:
    try:
        accounts.identity(token)
    except AuthenticationError:
        close_workspace()
        token = None
        st.warning("Your session ended. Please log in again.")

if not token:
    st.title("Sign in to your persistent memory")
    st.caption("Local research prototype. Your account memory persists after logout and restart.")
    mode = st.radio("Account action", ["Login", "Register"])
    with st.form("authentication"):
        name = st.text_input("Username", key="auth_username")
        password = st.text_input("Password", type="password", key="auth_password")
        submitted = st.form_submit_button(mode)
    if submitted:
        try:
            if mode == "Register":
                accounts.register(name, password)
                st.success("Account created. Choose Login to continue.")
            else:
                st.session_state["login_token"] = accounts.login(name, password)
                accounts.close()
                st.rerun()
        except AuthenticationError as error:
            st.error(str(error))
    accounts.close()
    st.stop()

st.sidebar.markdown('<div class="memory-brand"><span>&#9672;</span> Adaptive Memory</div>', unsafe_allow_html=True)
navigation = st.sidebar.container()
tools = st.sidebar.container()
footer = st.sidebar.container()
# Process logout before rendering chat selectors or other account-owned widgets.
if footer.button("Logout", icon=":material/logout:", use_container_width=True):
    accounts.logout(token)
    close_workspace()
    accounts.close()
    st.rerun()
settings = tools.expander("Settings")
with settings:
    light = st.toggle("Light mode (no model downloads)", value=True)
    chat_day = st.date_input("Message event date", key="chat_day")
    st.caption("This date applies to your next observation. Historical questions use the recorded event dates.")
workspace = st.session_state.get("workspace")
if workspace is not None:
    try:
        workspace.agent.store.conn.execute('SELECT 1').fetchone()
    except sqlite3.ProgrammingError as error:
        if 'closed database' not in str(error).lower():
            raise
        # A closed connection is not reusable across reruns. Reopen the same
        # authenticated account store without clearing conversations or evidence.
        st.session_state.pop('workspace', None)
        workspace = None
        st.info('Reconnecting to your saved account memory.')
if workspace is None or workspace.agent.light != light:
    if workspace:
        # Remove the cached reference before closing: an interrupted rebuild
        # must not leave a closed workspace for the next rerun to reuse.
        st.session_state.pop('workspace', None)
        workspace.close()
    workspace = Conversations(accounts, token, base / "users", cfg=cfg, light=light)
    st.session_state["workspace"] = workspace
else:
    # Each rerun owns a short-lived registry connection; do not retain a closed
    # connection through Streamlit state.
    workspace.accounts = accounts

def clear_turn():
    for name in ("pending", "answer", "ingest", "chat_selections", "chat_notes"):
        st.session_state.pop(name, None)


def display_image(path, caption=None):
    # Only images in this authenticated account's evidence directory may render.
    if not path or workspace.agent.image_dir is None:
        return
    resolved = Path(path).resolve()
    if resolved.is_relative_to(workspace.agent.image_dir.resolve()) and resolved.is_file():
        st.image(str(resolved), caption=caption, width=320)


conversations = workspace.list()
if navigation.button("New chat", icon=":material/add:", use_container_width=True) or not conversations:
    st.session_state["conversation"] = workspace.create()
    st.session_state["chosen_conversation"] = st.session_state["conversation"]
    clear_turn()
    conversations = workspace.list()
ids = [c["conversation_id"] for c in reversed(conversations)]
titles = {}
for conversation in conversations:
    chat_id = conversation['conversation_id']
    first_message = next((m['content'] for m in workspace.transcript(chat_id) if m['role'] == 'user'), '')
    titles[chat_id] = (first_message.strip()[:48] or conversation['title']) + ' | ' + conversation['created_at'][:10]
if st.session_state.get('chosen_conversation') not in ids:
    st.session_state['chosen_conversation'] = st.session_state.get('conversation', ids[0])
    if st.session_state['chosen_conversation'] not in ids:
        st.session_state['chosen_conversation'] = ids[0]
cid = navigation.radio("Your chats", ids, index=None, key="chosen_conversation", format_func=titles.get)
if cid != st.session_state.get('conversation'):
    clear_turn()
st.session_state['conversation'] = cid
navigation.caption('Conversations and memories are private to your account.')

st.markdown('<div class="memory-heading">Adaptive Memory</div>', unsafe_allow_html=True)
local_status = workspace.local.status()
if local_status.get('provider') == 'groq' and local_status.get('llm_model'):
    st.caption('Groq enabled | Conversation text and relevant memories are sent to Groq. Images are processed locally.')
else:
    st.caption('Deterministic responses | Evidence-grounded memory')

def prepare_submission():
    st.session_state['remember_submitted'] = st.session_state.get('remember_next', False)
    st.session_state['remember_next'] = False

remember_requested = st.toggle('Remember this', key='remember_next',
    help='Pin your next message as important even if automatic selection would skip it. Evidence, identity and disagreement checks still apply.')
submission = st.chat_input("Message Adaptive Memory", key="chat_composer", accept_file=True,
                           file_type=["png", "jpg", "jpeg"], max_chars=5000,
                           on_submit=prepare_submission)
if submission is not None:
    message = submission if isinstance(submission, str) else submission.text
    files = [] if isinstance(submission, str) else submission.files
    image, notes = None, []
    if files:
        try:
            image = Image.open(files[0]).convert('RGB')
        except Exception:
            notes.append('Image could not be decoded. Valid text will still be evaluated.')
    if message.strip() or image is not None:
        with st.spinner('Working with your memory...'):
            turn = workspace.chat(cid, message, image,
                datetime.combine(chat_day, datetime.min.time()).replace(tzinfo=timezone.utc),
                remember=st.session_state.pop('remember_submitted', remember_requested))
        st.session_state['answer'] = turn.answer
        st.session_state['chat_selections'] = turn.selections
        notes.extend(note for observation in turn.observations for note in observation.notes)
        notes.extend(selection['reason'] for selection in turn.selections if selection['outcome'] == 'clarify')
        st.session_state['chat_notes'] = notes
    else:
        st.session_state['chat_notes'] = notes or ['Provide a message or a readable image.']

messages = workspace.transcript(cid)
facts = workspace.memories()
events = workspace.events(cid)
visuals = {e['image_id']:e for record in facts for e in record.get('visual_evidence',[])}
images_by_message = {}
for event in events:
    for evidence_id in json.loads(event['evidence_ids']):
        if evidence_id in visuals:
            images_by_message.setdefault(event['message_id'], {})[evidence_id] = visuals[evidence_id]

if not messages:
    st.markdown('<div class="memory-welcome"><div class="mark">&#9672;</div><h1>What would you like to remember?</h1>'
                '<p>Share a thought, add a photo, or ask about something from an earlier conversation.</p></div>',
                unsafe_allow_html=True)
    st.caption('Try "My first car is red." Then ask "What color is my first car?"')

last_assistant = next((row['message_id'] for row in reversed(messages) if row['role'] == 'assistant'), None)
for row in messages:
    with st.chat_message(row['role']):
        st.write(row['content'] or 'Image observation')
        if row['role'] == 'user':
            for visual in images_by_message.get(row['message_id'], {}).values():
                association = visual.get('association_status', 'unknown')
                support = 'supporting' if visual.get('supports_state') else 'non-supporting'
                display_image(visual.get('image_path'), f'Image evidence | {association} | {support}')
        if row['message_id'] == last_assistant:
            for note in st.session_state.get('chat_notes', []):
                st.warning(note)
            answer = st.session_state.get('answer')
            if answer:
                if workspace.local.last_response.get('method') == 'deterministic-fallback':
                    st.caption('Fallback response | Groq was unavailable or its output did not pass validation.')
                if answer.note:
                    st.caption(answer.note)
                if answer.evidence:
                    with st.expander('Sources & evidence'):
                        st.caption(f'{answer.status} | {answer.intent}')
                        st.json(answer.evidence)
                        for evidence in answer.evidence:
                            if evidence.get('modality') == 'image':
                                display_image(evidence.get('image_path'), evidence.get('association_status'))
                with st.expander('Memory activity'):
                    st.json(st.session_state.get('chat_selections', []))
                    st.json(workspace.local.status())
if not messages:
    for note in st.session_state.get('chat_notes', []):
        st.warning(note)

# Verification stays visible and cannot be hidden by a model response.
outstanding = workspace.pending(cid)
verification = st.empty()
resolution_message = None
if outstanding:
    with verification.container(border=True):
        st.subheader('Verify a disagreement')
        selected_observation = st.selectbox('Unresolved observations', range(len(outstanding)),
            format_func=lambda i: outstanding[i].timestamp + ' | ' + outstanding[i].session_id)
        observation = outstanding[selected_observation]
        request = workspace.agent.verification_request(observation)
        if request:
            st.warning(f"Text/memory: {request['memory_value']}; image: {request['image_value']}. Choose which value to accept.")
            selected = st.radio('Accept value', [request['memory_value'], request['image_value']])
            rationale = st.text_input('Rationale (optional)')
            if st.button('Resolve disagreement', type='primary'):
                workspace.resolve(cid, observation, selected, rationale)
                clear_turn()
                verification.empty()
                resolution_message = workspace.transcript(cid)[-1]['content']
                facts = workspace.memories()
                events = workspace.events(cid)
if resolution_message:
    with st.chat_message('assistant'):
        st.write(resolution_message)

with tools.expander('Memory & evidence'):
    memory_tab, decisions_tab, audit_tab = st.tabs(['Memories', 'Decisions', 'Resolutions'])
    with memory_tab:
        identity = st.selectbox('Memory identity', ['All identities'] + sorted({r['entity_id'] for r in facts}))
        st.json([r for r in facts if identity == 'All identities' or r['entity_id'] == identity])
    with decisions_tab:
        st.json(workspace.selection_history())
        st.caption('Explicit importance requests (pin / unpin history)')
        st.json(workspace.priority_history())
    with audit_tab:
        st.json(workspace.audit())
with tools.expander('Manage memories'):
    st.caption('Corrections create new states. Forgetting hides the complete fact history from retrieval and is reversible; transcripts and evidence remain.')
    if facts:
        target = st.selectbox('Memory to manage', [r['memory_id'] for r in facts])
        reason = st.text_input('Management rationale')
        if st.button('Pin as important'):
            workspace.set_memory_priority(target, True)
            st.success('Pinned. Truth, temporal history and visibility remain governed by the memory engine.')
        if st.button('Unpin'):
            workspace.set_memory_priority(target, False)
            st.success('Importance removed. The memory is preserved.')
        if st.button('Forget from retrieval'):
            workspace.set_memory_visibility(target, False, reason)
            clear_turn()
            accounts.close()
            st.rerun()
        if st.button('Restore to retrieval'):
            workspace.set_memory_visibility(target, True, reason)
            clear_turn()
            accounts.close()
            st.rerun()
    st.caption('To correct a fact, send "Correction: ..." in the chat.')
with tools.expander('Conversation details'):
    st.json(events)
    if st.button('Create extractive session summary'):
        st.write(workspace.summarize(cid))
    for summary in workspace.summaries(cid):
        st.json(summary)
with settings:
    if not local_status.get('llm_model'):
        st.info(local_status['status'])
    st.json(local_status)
    st.json(workspace.agent.status())
    if st.button('Refresh model status'):
        st.json(workspace.local.status(refresh=True))
    if st.button('Rebuild local semantic index'):
        try:
            st.json(workspace.local.reindex(force=True))
        except Exception:
            st.warning('Local embeddings unavailable. Your previous index is preserved; lexical retrieval remains available.')
    st.caption('API credentials are configured on the server, never in this page.')
with tools.expander('Login history'):
    st.json(accounts.history(token))
accounts.close()
