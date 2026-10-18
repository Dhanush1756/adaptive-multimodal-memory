"""Separate controlled automatic-memory diagnostics; never runs frozen Track A/B.

python -B -m src.evaluation.automatic_memory --out reports/automatic_memory_v1/run.json
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import tempfile

from PIL import Image

from ..accounts import Accounts, AuthenticationError
from ..config import load_config
from ..conversations import Conversations
from ..memory.selection import extract_candidates


def ratio(n, d):
    return {'numerator': n, 'denominator': d, 'value': n / d if d else None}


def run(dataset):
    source = Path(dataset)
    spec = json.loads(source.read_text(encoding='utf-8'))
    cases, tp, fp, fn, baseline_fp = [], 0, 0, 0, 0
    with tempfile.TemporaryDirectory(prefix='aegm-automatic-') as temp:
        root = Path(temp)
        accounts = Accounts(root / 'registry.db')
        accounts.register('researcher', 'disposable diagnostic password')
        token = accounts.login('researcher', 'disposable diagnostic password')
        cfg = load_config(str(Path(__file__).resolve().parents[2] / 'config.yaml'))
        cfg['cv']['color_head_path'] = str(root / 'absent-head.joblib')
        def workspace(subdir, login=token):
            s = Conversations(accounts, login, root / subdir, cfg=cfg, light=True)
            s.agent.intent_model = None
            return s
        for i, item in enumerate(spec['cases']):
            s = workspace(f'case-{i}')
            turn = s.chat(s.create(), item['text'], timestamp='2026-10-01')
            predicted = {(r['entity'],r['attribute'],r['value']) for r in s.memories()}
            expected = {tuple(c) for c in item['expected']}
            tp += len(predicted & expected)
            fp += len(predicted - expected)
            fn += len(expected - predicted)
            extracted = {(c.entity,c.attribute,c.value) for c in extract_candidates(item['text'], '2026-10-01')}
            baseline_fp += len(extracted - expected)
            cases.append({'text':item['text'], 'expected':sorted(expected), 'predicted':sorted(predicted),
                          'correct':predicted == expected, 'selections':turn.selections})
            s.close()
        s = workspace('integrated')
        cid = s.create()
        for color, day in [('red','01'),('blue','20'),('black','25'),('blue','10')]:
            s.chat(cid, f'My car is {color}.', timestamp=f'2026-10-{day}')
        queries = [('What color is my car now?', 'black'),
                   ('What color was my car previously?', 'blue'),
                   ('What color was my car originally?', 'red'),
                   ('What color was my car on 2026-10-15?', 'blue'),
                   ('Show my car color history.', ['red','blue','black'])]
        temporal = [{'question':q, 'expected':v, 'actual':s.chat(cid,q).answer.value} for q,v in queries]
        s.chat(cid, 'My project named atlas model is CLIP.', timestamp='2026-10-01')
        before = len(s.memories())
        dup = s.chat(cid, 'My project named atlas model is CLIP.', timestamp='2026-10-02')
        duplicate_states = len(s.memories()) - before
        later = s.create('cross-conversation recall')
        recalled = s.chat(later, 'What model is project named atlas?').answer
        grounding = all(e.get('evidence_id') and e.get('timestamp') and e.get('ingested_at')
                        and e.get('extractor') and e.get('conversation_references') for e in recalled.evidence)
        accounts.register('other_user', 'another disposable password')
        other = workspace('integrated', accounts.login('other_user','another disposable password'))
        isolated = not other.chat(other.create(), 'What model is project named atlas?').answer.found
        try:
            other.transcript(cid)
            denied = False
        except AuthenticationError:
            denied = True
        other.close()
        # Reopen the real account-local SQLite; no process-local session state.
        s.close()
        s = workspace('integrated')
        recovery = s.chat(s.create(), 'What model is project named atlas?').answer.value == 'clip'
        s.close()
        visual = []
        for choice in ['red','white']:
            s = workspace('visual-'+choice)
            cid = s.create()
            s.chat(cid, 'My car is red.', timestamp='2026-10-01')
            s.chat(cid, 'My car is red.', image=Image.new('RGB',(64,64),'white'), timestamp='2026-10-10')
            uncertain = s.chat(cid, 'What color is my car?').answer.status == 'uncertain'
            s.resolve(cid, s.pending(cid)[0], choice, 'automated synthetic-image diagnostic')
            answer = s.chat(cid, 'What color is my car?').answer
            visual.append({'choice':choice,'uncertain_before':uncertain,'value_after':answer.value,
                           'original':s.chat(cid,'What color was my car originally?').answer.value,
                           'audit_count':len(s.audit()), 'fixture':'generated solid white PIL image; HSV, no pretrained inference'})
            s.close()
        accounts.close()
    return {'dataset':str(source), 'dataset_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'annotation_process':spec['annotation_process'], 'split':spec['split'], 'python':platform.python_version(),
            'selection_case_count':len(cases), 'selection_exact_cases':ratio(sum(c['correct'] for c in cases),len(cases)),
            'selection_precision':ratio(tp,tp+fp), 'selection_recall':ratio(tp,tp+fn),
            'promote_all_extracted_baseline_false_positives':baseline_fp,
            'history_only_baseline_recall':ratio(0,tp+fn), 'cases':cases,
            'temporal_queries':temporal, 'temporal_correct':ratio(sum(r['actual']==r['expected'] for r in temporal),len(temporal)),
            'duplicate_new_state_rate':ratio(duplicate_states,1), 'duplicate_outcome':dup.selections[0]['outcome'],
            'cross_conversation_recall':recalled.value == 'clip', 'source_metadata_complete':grounding,
            'cross_account_retrieval_blocked':isolated, 'foreign_transcript_denied':denied,
            'sqlite_reopen_recall':recovery, 'visual_conflict_diagnostics':visual,
            'limitations':'Constructed assistant-labelled diagnostics; no independent gold, natural-dialogue or pretrained/general-vision performance claim. Frozen tracks not rerun.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset', default='data/annotations/automatic_selection_v1.json')
    p.add_argument('--out', required=True)
    a = p.parse_args()
    output = Path(a.out)
    if output.exists():
        raise FileExistsError('Preserve the prior result; choose a new output.')
    result = run(a.dataset)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x',encoding='utf-8') as f:
        json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k not in {'cases','temporal_queries'}},indent=2))


if __name__ == '__main__':
    main()
