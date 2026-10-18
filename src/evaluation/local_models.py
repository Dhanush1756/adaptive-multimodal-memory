"""Actual local-model readiness/evaluation. Missing models produce BLOCKED, not fake scores.

python -B -m src.evaluation.local_models --out reports/local_models_v1/run.json
No downloads, browser, user databases or frozen benchmark rewrites.
"""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import tempfile
import time

from ..accounts import Accounts
from ..config import load_config
from ..conversations import Conversations
from ..memory.selection import extract_candidates, EXTRACTOR_VERSION


def fraction(n,d):
    return {'numerator':n,'denominator':d,'value':n/d if d else None}


def metrics(rows):
    tp = fp = fn = 0
    for row in rows:
        expected,actual = {tuple(c) for c in row['expected']},{tuple(c) for c in row['actual']}
        tp += len(expected & actual)
        fp += len(actual-expected)
        fn += len(expected-actual)
    return {'precision':fraction(tp,tp+fp),'recall':fraction(tp,tp+fn),
            'exact_cases':fraction(sum(r['expected']==r['actual'] for r in rows),len(rows))}


def memory_sample():
    try:
        import psutil
        return {'python_rss_bytes':psutil.Process().memory_info().rss,
                'available_system_ram_bytes':psutil.virtual_memory().available,
                'ollama_process_rss_sum_bytes':sum(p.memory_info().rss for p in psutil.process_iter()
                    if 'ollama' in p.name().lower())}
    except Exception:
        return None


def run(dataset):
    path = Path(dataset)
    spec = json.loads(path.read_text(encoding='utf-8'))
    baseline,proposed = [],[]
    extraction_ms, retrieval_rows = [],[]
    resource_start = memory_sample()
    with tempfile.TemporaryDirectory(prefix='aegm-local-evaluation-') as temp:
        root = Path(temp)
        registry = Accounts(root/'registry.db')
        registry.register('researcher','disposable local evaluation password')
        token = registry.login('researcher','disposable local evaluation password')
        config = load_config(str(Path(__file__).resolve().parents[2]/'config.local.yaml'))
        config['cv']['color_head_path'] = str(root/'absent-head.joblib')
        service = Conversations(registry,token,root/'users',cfg=config,light=True)
        service.agent.intent_model = None
        status = service.local.status(refresh=True)
        llm_probe = {'status':'BLOCKED','reason':'Local runtime/model not available. No real LLM inference executed.'}
        embedding_probe = {'status':'BLOCKED','reason':'Local embedding model not available. No semantic model inference executed.'}
        if service.local.llm:
            start = time.perf_counter()
            try:
                result,timing = service.local.client.chat(service.local.llm_name,[{'role':'user','content':'Return JSON {"ready":true}.'}],max_tokens=32)
                llm_probe = {'status':'PASS' if result.get('ready') is True else 'FAIL',
                             'latency_ms':(time.perf_counter()-start)*1000,'runtime_timing':timing}
            except Exception:
                llm_probe = {'status':'FAIL','reason':'Local chat inference failed.'}
        if service.local.embedding:
            start = time.perf_counter()
            try:
                vectors = service.local.client.embed(service.local.embedding_name,['A small local embedding probe.'])
                embedding_probe = {'status':'PASS','dimensions':len(vectors[0]),'latency_ms':(time.perf_counter()-start)*1000}
            except Exception:
                embedding_probe = {'status':'FAIL','reason':'Local embedding inference failed.'}
        # This is extraction, not selection; evaluate exact canonical tuples and
        # report missing paraphrases rather than quietly treating them as negatives.
        for item in spec['extraction']:
            rules = extract_candidates(item['text'],'2026-10-01T00:00:00+00:00')
            expected = sorted(item['claims'])
            actual = sorted({(c.entity,c.attribute,c.value) for c in rules})
            baseline.append({'text':item['text'],'expected':expected,'actual':[list(c) for c in actual]})
            if llm_probe['status'] == 'PASS':
                start = time.perf_counter()
                claims,_ = service.local.extract(item['text'],'2026-10-01T00:00:00+00:00',rules)
                extraction_ms.append((time.perf_counter()-start)*1000)
                proposed.append({'text':item['text'],'expected':expected,
                    'actual':[list(c) for c in sorted({(c.entity,c.attribute,c.value) for c in claims})],
                    'extraction_status':dict(service.local.last_extraction)})
        # Populate through the actual general-attribute path, with model calls
        # disabled so both retrieval systems receive identical controlled facts.
        original = service.create('source facts')
        was_enabled = service.local.enabled
        service.local.enabled = False
        for item in spec['observations']:
            service.chat(original,item['text'],timestamp=item['time'])
        assert len(service.memories()) == 8, 'Controlled source facts were not populated correctly.'
        service.local.enabled = was_enabled
        query_cid = service.create('return visit')
        for item in spec['retrieval']:
            question = item['question']
            start = time.perf_counter()
            lexical = service._references(service._automatic_answer(question,'2026-10-25T00:00:00+00:00'))
            lexical_ms = (time.perf_counter()-start)*1000
            start = time.perf_counter()
            answer = service.local.retrieve(question,'2026-10-25T00:00:00+00:00',lexical)
            retrieval_rows.append({'question':question,'expected':item['value'],
                'lexical_value':lexical.value if lexical.found else None,'local_with_fallback_value':answer.value if answer.found else None,
                'lexical_latency_ms':lexical_ms,'local_path_latency_ms':(time.perf_counter()-start)*1000,
                'local_path':dict(service.local.last_retrieval), 'supporting_state_ids':answer.supporting_state_ids,
                'evidence':answer.evidence})
        service.close()
        registry.close()
    def retrieval_metrics(field):
        positives = [r for r in retrieval_rows if r['expected'] is not None]
        correct = sum(r[field] == r['expected'] for r in positives)
        answered = sum(r[field] is not None for r in retrieval_rows)
        negatives = [r for r in retrieval_rows if r['expected'] is None]
        return {'precision':fraction(correct,answered),'recall':fraction(correct,len(positives)),
                'correct_abstention':fraction(sum(r[field] is None for r in negatives),len(negatives)),
                'exact_cases':fraction(sum(r[field]==r['expected'] for r in retrieval_rows),len(retrieval_rows))}
    return {'dataset':str(path),'dataset_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'review':spec['review'],
        'python':platform.python_version(),'packages':{p:importlib.metadata.version(p) for p in ['numpy','streamlit','scikit-learn','Pillow','pytest']},
        'local_setup_status':status,'llm_inference_probe':llm_probe,'embedding_inference_probe':embedding_probe,
        'extraction_case_count':len(baseline),'deterministic_extraction':{'version':EXTRACTOR_VERSION,'metrics':metrics(baseline),'cases':baseline},
        'local_llm_extraction':{'status':'EXECUTED' if proposed else 'BLOCKED',
            'metrics':metrics(proposed) if proposed else None,'latencies_ms':extraction_ms,'cases':proposed},
        'retrieval_case_count':len(retrieval_rows),'lexical_retrieval':retrieval_metrics('lexical_value'),
        'controlled_source_state_count':8,
        'local_with_fallback_retrieval':retrieval_metrics('local_with_fallback_value'),
        'real_semantic_comparison_status':'EXECUTED' if embedding_probe['status']=='PASS' else 'BLOCKED - these are fallback results, not embedding performance',
        'retrieval_cases':retrieval_rows,'resource_start':resource_start,'resource_end':memory_sample(),
        'resource_scope':'Point samples only, not peak RSS. psutil optional; Ollama process sum may count shared memory and includes runner only if present.',
        'limitations':'Small assistant-reviewed authored diagnostics, no independent human gold, no generalization or benchmark-improvement claim. Null model scores mean not executed. Browser verification deliberately not performed.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',default='data/annotations/local_nlp_review_v1.json')
    parser.add_argument('--out',required=True)
    args = parser.parse_args()
    out = Path(args.out)
    if out.exists():
        raise FileExistsError('Preserve existing evaluation; choose another output filename.')
    report = run(args.dataset)
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x',encoding='utf-8') as stream:
        json.dump(report,stream,indent=2)
    print(json.dumps({k:report[k] for k in ['llm_inference_probe','embedding_inference_probe','extraction_case_count',
        'lexical_retrieval','local_with_fallback_retrieval','real_semantic_comparison_status','resource_start','resource_end']},indent=2))


if __name__ == '__main__':
    main()
