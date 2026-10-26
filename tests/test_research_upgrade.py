import json
import pytest
from PIL import Image
from src.config import load_config
from src.cv.detection import Detection
from src.multimodal.visual_pipeline import VisualPipeline
from src.accounts import Accounts, AuthenticationError
from src.conversations import Conversations
from src.memory.selection import extract_candidates


def test_multiple_detections_are_not_existing_object_identity(monkeypatch):
    cfg=load_config();cfg['cv']['general_categories']=True
    p=VisualPipeline(cfg,light=True)
    monkeypatch.setattr(p.detector,'detect',lambda image:[
        Detection('cup','cup',[0,0,40,40],.9),Detection('person','person',[40,0,80,80],.9)])
    a=p.analyze(Image.new('RGB',(80,80),'red'),'cup')
    assert len(a.objects)==2 and a.association_status=='contextual'
    assert all(o['supports_state'] is False and o['identity_status']=='unassociated' for o in a.objects)
    assert a.objects[1]['color'] is None
    assert a.description['verified'] is False


def test_unknown_attribute_is_not_a_guessed_colour(monkeypatch):
    cfg=load_config();cfg['cv']['general_categories']=True
    p=VisualPipeline(cfg,light=True)
    monkeypatch.setattr(p.detector,'detect',lambda image:[Detection('cup','cup',[0,0,20,20],.9)])
    monkeypatch.setattr(p.attributes,'extract',lambda *a,**k:{'color':'red','confidence':.1,'method':'hsv'})
    a=p.analyze(Image.new('RGB',(20,20),'red'),'cup')
    assert a.color is None and a.objects[0]['color'] is None


def test_image_only_observations_are_persistent_and_account_scoped(tmp_path,monkeypatch):
    a=Accounts(tmp_path/'accounts.db');a.register('alice','a unique long password')
    s=Conversations(a,a.login('alice','a unique long password'),tmp_path/'users')
    monkeypatch.setattr(s.agent.comp.visual.detector,'detect',lambda image:[Detection('cup','cup',[0,0,20,20],.9)])
    cid=s.create();s.chat(cid,'',Image.new('RGB',(20,20),'red'),timestamp='2026-10-01')
    assert not s.memories()
    record=s.visual_observations(cid)[0]
    assert record['payload']['source_message_id'] and record['payload']['event_time'] != record['payload']['ingested_at']
    assert record['payload']['objects'][0]['supports_state'] is False
    reopened=Conversations(a,s.token,tmp_path/'users')
    assert reopened.visual_observations(cid)[0]['observation_id']==record['observation_id']
    a.register('bobby','another unique long password')
    bob=Conversations(a,a.login('bobby','another unique long password'),tmp_path/'users')
    with pytest.raises(AuthenticationError):bob.visual_observations(cid)
    reopened.close();bob.close();s.close();a.close()


def test_explicit_relationship_commitment_and_source_span(tmp_path):
    claims=extract_candidates('Alice works at Acme. I will submit my thesis tomorrow.','2026-10-01')
    assert [(c.entity,c.attribute,c.value) for c in claims]==[
        ('person','workplace','acme'),('user','commitment','submit my thesis tomorrow')]
    assert claims[1].resolved_time.startswith('2026-10-01')  # statement date, not future promised event
    a=Accounts(tmp_path/'accounts.db');a.register('alice','a unique long password')
    s=Conversations(a,a.login('alice','a unique long password'),tmp_path/'users')
    text='Alice works at Acme.';s.chat(s.create(),text,timestamp='2026-10-01')
    audit=json.loads(s.selection_history()[0]['candidate_json'])
    provenance=audit['provenance'];start,end=provenance['source_span']
    assert provenance['source_message_id'] and provenance['schema_version']=='candidate-memory-v2'
    assert text[start:end]==audit['source_text'] and not provenance['independently_verified']
    s.close();a.close()


def test_encrypted_publish_failure_rolls_back_ram_and_disk(tmp_path,monkeypatch):
    from cryptography.fernet import Fernet
    monkeypatch.setenv('AEGM_DATA_KEY',Fernet.generate_key().decode())
    a=Accounts(tmp_path/'accounts.db');a.register('alice','a unique long password')
    cfg=load_config();cfg['privacy']={'encrypt_account_storage':True}
    s=Conversations(a,a.login('alice','a unique long password'),tmp_path/'users',cfg=cfg)
    cid=s.create();s.chat(cid,'My car is red.',timestamp='2026-10-01')
    old=s.agent.protection.path.read_bytes()
    monkeypatch.setattr(s.agent.protection,'save',lambda *args: (_ for _ in ()).throw(OSError('fixture disk failure')))
    with pytest.raises(OSError):s.chat(cid,'My car is blue.',timestamp='2026-10-02')
    assert [r['value'] for r in s.memories()]==['red']
    assert s.agent.protection.path.read_bytes()==old
    assert not any('blue' in m['content'] for m in s.transcript(cid))
    s.close();a.close()
