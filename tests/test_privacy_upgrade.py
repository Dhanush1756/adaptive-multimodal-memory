import json
from pathlib import Path
import pytest
from PIL import Image
from src.accounts import Accounts, AuthenticationError
from src.conversations import Conversations
from src.config import load_config


@pytest.fixture
def service(tmp_path):
    a=Accounts(tmp_path/'accounts.db');a.register('alice','a unique long password')
    s=Conversations(a,a.login('alice','a unique long password'),tmp_path/'users')
    yield s,a,tmp_path
    s.close();a.close()


def test_sensitive_input_is_not_saved_or_sent(service):
    s,_,_=service;cid=s.create()
    for text in ['My API key is dummy-credential.', 'My passport number is dummy-123.', 'Remember my password is dummy.']:
        assert 'not saved' in s.chat(cid,text,remember=True).answer.text
    assert not s.transcript(cid) and not s.memories()
    s.remember(cid,'My API key is another disposable example.')
    s.ask(cid,'Is my passport number a disposable example?')
    assert not s.transcript(cid) and not s.memories()


def test_external_consent_is_account_local_and_revocable(service,monkeypatch):
    s,a,root=service
    s.local.provider='groq'
    monkeypatch.setattr(s.local,'status',lambda *a,**k: (_ for _ in ()).throw(AssertionError('Provider must not be touched')))
    assert s.local.extract('My car is red.','2026-10-01',[])[0]==[]
    assert not s.privacy_settings()['external_processing']
    s.set_privacy(external_processing=True)
    s.local.extraction_cache['fixture']='private'
    s.set_privacy(external_processing=False)
    assert not s.local.extraction_cache
    a.register('bobby','another unique long password')
    bob=Conversations(a,a.login('bobby','another unique long password'),root/'users')
    assert not bob.privacy_settings()['external_processing'];bob.close()


def test_automatic_memory_off_allows_explicit_request(service):
    s,_,_=service;cid=s.create();s.set_privacy(automatic_memory=False)
    s.chat(cid,'My car is red.');assert not s.memories()
    s.chat(cid,'My car is red.',remember=True);assert s.memories()


def test_export_and_full_erasure_persist_without_cross_account_access(service):
    s,a,root=service;cid=s.create()
    s.chat(cid,'My car is red.',Image.new('RGB',(80,80),'white'),timestamp='2026-10-01')
    s.summarize(cid)
    exported=s.export_workspace()
    assert 'red' in json.dumps(exported) and 'image_path' not in json.dumps(exported)
    a.register('bobby','another unique long password')
    bob=Conversations(a,a.login('bobby','another unique long password'),root/'users')
    bid=bob.create();bob.chat(bid,'My car is blue.')
    with pytest.raises(AuthenticationError):bob.transcript(cid)
    image=next(s.agent.image_dir.glob('IMG_*.png'))
    with pytest.raises(AuthenticationError):bob.read_evidence(image)
    with pytest.raises(ValueError):s.erase_workspace('wrong')
    s.erase_workspace('DELETE MY STORED DATA')
    assert not s.memories() and not s.list() and not image.exists()
    assert bob.chat(bid,'What color is my car?').answer.value=='blue'
    reopened=Conversations(a,s.token,root/'users')
    assert not reopened.memories() and not reopened.list()
    assert not reopened.chat(reopened.create(),'What color is my car?').answer.found
    reopened.close();bob.close()


def test_retention_is_opt_in_and_expires_whole_workspace(service,monkeypatch):
    s,_,_=service;cid=s.create();s.chat(cid,'My car is red.')
    s.db.execute("UPDATE messages SET created_at='2020-01-01T00:00:00+00:00'")
    assert s.apply_retention() is None
    s.set_privacy(retention_days=30)
    assert s.apply_retention()['memories_erased']==1
    assert not s.list()


def test_encrypted_snapshot_evidence_reopen_wrong_key_and_busy_lock(tmp_path,monkeypatch):
    from cryptography.fernet import Fernet
    from src.protected_storage import ProtectionError
    monkeypatch.setenv('AEGM_DATA_KEY',Fernet.generate_key().decode())
    a=Accounts(tmp_path/'accounts.db');a.register('alice','a unique long password');token=a.login('alice','a unique long password')
    cfg=load_config();cfg['privacy']={'encrypt_account_storage':True}
    s=Conversations(a,token,tmp_path/'users',cfg=cfg);cid=s.create()
    s.chat(cid,'My car is red.',Image.new('RGB',(80,80),'white'),timestamp='2026-10-01')
    vault=Path(s.agent.store.db_path+'.fernet');image=next(s.agent.image_dir.glob('*.fernet'))
    assert b'My car is red.' not in vault.read_bytes() and not Path(s.agent.store.db_path).exists()
    assert b'My car is red.' in s.agent.protection.decrypt(vault.read_bytes())
    assert not image.read_bytes().startswith(b'\x89PNG')
    assert s.read_evidence(image).startswith(b'\x89PNG')
    with pytest.raises(ProtectionError,match='already open'):Conversations(a,token,tmp_path/'users',cfg=cfg)
    s.close()
    reopened=Conversations(a,token,tmp_path/'users',cfg=cfg)
    assert reopened.chat(cid,'What color is my car?').answer.status=='uncertain'
    reopened.erase_workspace('DELETE MY STORED DATA');reopened.close()
    final=Conversations(a,token,tmp_path/'users',cfg=cfg)
    assert not final.list();final.close()
    original=vault.read_bytes();monkeypatch.setenv('AEGM_DATA_KEY',Fernet.generate_key().decode())
    with pytest.raises(ProtectionError,match='authenticated'):Conversations(a,token,tmp_path/'users',cfg=cfg)
    assert vault.read_bytes()==original
    a.close()


def test_protected_profile_refuses_missing_key_and_legacy_plaintext(service,monkeypatch):
    from src.protected_storage import ProtectionError
    s,a,root=service;cid=s.create();s.chat(cid,'My car is red.')
    legacy=Path(s.agent.store.db_path);original=legacy.read_bytes()
    cfg=load_config();cfg['privacy']={'encrypt_account_storage':True}
    with pytest.raises(ProtectionError,match='Legacy plaintext'):
        Conversations(a,s.token,root/'users',cfg=cfg)
    assert legacy.read_bytes()==original
    monkeypatch.delenv('AEGM_DATA_KEY',raising=False)
    with pytest.raises(ProtectionError,match='valid external'):
        Conversations(a,s.token,root/'different-users',cfg=cfg)
