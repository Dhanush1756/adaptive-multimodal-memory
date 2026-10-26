"""New diagnostics only; never writes frozen benchmark or historical outputs."""
import argparse
import hashlib
import json
import time
from pathlib import Path
from ..memory.selection import extract_candidates
from ..nlp.relation_extraction import extract_claims
from ..privacy import sensitivity


def evaluate(path):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    result={'dataset':str(path),'sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            'review':data['review'],'live_api_calls':False,'systems':{},
            'semantic_retrieval':'NOT EXECUTED: embedding runtime/model unavailable; existing lexical fallback retained.'}
    for name,extractor in [('legacy_colour_extractor',extract_claims),('candidate_rules_v2',extract_candidates)]:
        tp=fp=fn=exact=0;rows=[];latencies=[]
        for case in data['cases']:
            start=time.perf_counter()
            claims=extractor(case['text'],data['reference']) if sensitivity(case['text'])=='ordinary' else []
            got={(c.entity,c.attribute,c.value) for c in claims}
            expected={tuple(x) for x in case['expected']}
            latencies.append((time.perf_counter()-start)*1000)
            tp+=len(got&expected);fp+=len(got-expected);fn+=len(expected-got);exact+=got==expected
            rows.append({'text':case['text'],'expected':sorted(expected),'actual':sorted(got)})
        result['systems'][name]={'true_positive':tp,'false_positive':fp,'false_negative':fn,
            'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None,
            'exact_cases':exact,'total_cases':len(rows),'latency_ms':latencies,'cases':rows}
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data',default='data/annotations/research_upgrade_nlp_v1.json')
    parser.add_argument('--out',required=True)
    args=parser.parse_args();out=Path(args.out)
    if out.exists():raise FileExistsError('Use a new output path; historical reports are never overwritten.')
    result=evaluate(args.data);out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    print(json.dumps({name:{k:v for k,v in row.items() if k not in {'cases','latency_ms'}} for name,row in result['systems'].items()},indent=2))
