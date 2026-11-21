#!/usr/bin/env python3
"""Selma Tanka coordination optimizer: deterministic, local-only, review-first.

No network, subprocess, code execution, public posting, or source-file modification.
Path names from the archive are untrusted metadata, not executable instructions.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re

PROJECT_GOALS = {
    'SelmaOS / Android agent': .99,
    'SelmaOS / collaboration policy': .97,
    'Tanka coordination reference': .97,
    'ARIA': .88,
    'Soulbooks Crowology Engine': .85,
    'Vedic Cosmos Explorer / Crowology': .82,
    'Games / 3D prototype review': .80,
    'Crowology / Astro monetization': .76,
    'Tanka source evidence': .68,
    'Drive metadata inventory': .50,
    'Workspace triage queue': .40,
}
DEFAULT_WEIGHTS = {'goal':.28,'readiness':.22,'reuse':.16,'novelty':.12,'evidence':.12,'efficiency':.10}
CANDIDATE_MIN_SEEDS = 3
CANDIDATE_MIN_COVERAGE = .15
CANDIDATE_MIN_PURity = .80
SENSITIVE_TOKENS = ('/turn_history/','/.git/','/sessions/','/gmail/','/secrets/','/credentials/','/private/','.env', '/.ssh/', 'id_rsa', 'api_key','access_token','auth_token')
GATED_TOKENS = ('billing','wallet','trade','order','payment','auth','permission','credential','secrets','procurement','ssh','network','sudo','deploy','release')
CSV_COLS = ('path','bytes','sha256','category','search_indexed','proposed_destination','integration_status','notes')


def read_rows(path: Path):
    with path.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if not set(CSV_COLS).issubset(set(reader.fieldnames or ())):
            raise ValueError('Required routing columns missing')
        rows=list(reader)
    if not rows: raise ValueError('Empty source register')
    paths=set()
    for r in rows:
        p=r['path']
        if (not p or p.startswith('/') or '\\' in p or '..' in p.split('/') or p in paths):
            raise ValueError('Invalid/duplicate source path')
        paths.add(p)
        n=int(r['bytes']);assert n>=0
        if not re.fullmatch(r'[0-9a-f]{64}',r['sha256']): raise ValueError('Invalid SHA-256')
        if r['search_indexed'] not in ('0','1'):raise ValueError('Invalid index flag')
    return rows


def validate_config(config):
    w=config['weights']
    if set(w)!=set(DEFAULT_WEIGHTS): raise ValueError('Weight feature mismatch')
    if any(not isinstance(v,(int,float)) or not math.isfinite(v) or v < 0 for v in w.values()):
        raise ValueError('Weights must be finite and nonnegative')
    if not math.isclose(sum(w.values()),1,abs_tol=1e-8): raise ValueError('Weights must total 1.0')
    return w


def workspace_id(path):
    bits=path.split('/')
    return bits[1] if len(bits)>=3 and bits[0]=='workspace' else ''


def infer_lanes(rows):
    # Strong hints from known assignments *within the same archived workspace*.
    byws=defaultdict(lambda:Counter())
    totals=Counter()
    for r in rows:
        ws=workspace_id(r['path'])
        if not ws:continue
        totals[ws]+=1
        label=r['proposed_destination']
        if label not in ('Workspace triage queue','Private Tanka archive'):
            byws[ws][label]+=1
    inference={}
    for ws,votes in byws.items():
        total_seed=sum(votes.values())
        if not total_seed:continue
        top,n=votes.most_common(1)[0]
        purity=n/total_seed
        coverage=total_seed/totals[ws]
        if total_seed>=CANDIDATE_MIN_SEEDS and coverage>=CANDIDATE_MIN_COVERAGE and purity>=CANDIDATE_MIN_PURity:
            confidence=round(purity*coverage,3) # evidence coverage limits confidence
            inference[ws]=(top,confidence,round(coverage,3),round(purity,3))
    return inference


def filepath_risk(row):
    p=row['path'].lower()
    if row['integration_status']=='RESTRICTED' or row['category'] in ('sessions','gmail'):
        return 'RESTRICTED'
    if any(token in p for token in SENSITIVE_TOKENS):return 'PRIVATE_REVIEW'
    if any(token in p for token in GATED_TOKENS):return 'HUMAN_GATE'
    return 'REVIEW_ONLY'


def next_action(risk,indexed,candidate):
    if risk=='RESTRICTED': return 'Retain privately; never auto-share or execute'
    if risk=='PRIVATE_REVIEW': return 'Review metadata and redact sensitive material before any reuse'
    if risk=='HUMAN_GATE': return 'Static review, dependency/license/permission review; no live action'
    if candidate=='Unclassified workspace':return 'Inspect safely, identify project and owner, then test in isolation'
    if not indexed:return 'Inspect binary/config provenance and run non-executing validation'
    return 'Review source and dependencies; test in sandbox before any import'


def score_rows(rows,weights):
    inference=infer_lanes(rows)
    namecounts=Counter(Path(r['path']).name.lower() for r in rows)
    maxbytes=max(int(r['bytes']) for r in rows)
    output=[]
    for r in rows:
        p=r['path'];risk=filepath_risk(r)
        dst=r['proposed_destination']; ws=workspace_id(p)
        if dst=='Workspace triage queue':
            if ws in inference:
                lane,confidence,coverage,purity=inference[ws]
                tag='INFERRED_FROM_WORKSPACE'
            else:lane='Unclassified workspace';confidence=0.;tag='UNCLASSIFIED'
        else:
            lane=dst
            confidence=1.0 if dst=='Private Tanka archive' else .70
            tag='SOURCE_PROPOSED'
        indexed=int(r['search_indexed'])
        filename=Path(p).name.lower()
        # Feature engineering is intentionally inspectable, not trained on private records.
        goal=PROJECT_GOALS.get(lane,.44)
        readiness=.82 if indexed else .36
        tokens=p.lower()
        if any(t in tokens for t in ('test_','/tests/','/test/','schema','manifest','readme','requirements','contract')):reuse=.86
        elif any(t in tokens for t in ('core','engine','adapter','bridge','module','api','skill')):reuse=.80
        elif filename.endswith(('.png','.jpg','.jpeg','.webp','.gif','.zip','.mp4')):reuse=.40
        else:reuse=.55
        novelty=round(.45+.55/(1+math.log1p(namecounts[filename]-1)),4)
        evidence=.77 if indexed else .46
        efficiency=1.0-math.log1p(int(r['bytes']))/math.log1p(maxbytes)
        parts={'goal':goal,'readiness':readiness,'reuse':reuse,'novelty':novelty,'evidence':evidence,'efficiency':efficiency}
        score=round(100*sum(weights[k]*parts[k] for k in weights),2)
        if risk=='RESTRICTED':score=0.0
        if risk=='PRIVATE_REVIEW':score=min(score,35.)
        out={**r,'record_id':hashlib.sha256(p.encode()).hexdigest()[:16],
             'candidate_lane':lane,'lane_confidence':confidence,'lane_source':tag,
             'privacy_gate':risk,'score':score,'next_action':next_action(risk,indexed,lane),
             'workspace_key':hashlib.sha256(ws.encode()).hexdigest()[:8] if ws else '',
             **{f'feature_{k}':round(v,4) for k,v in parts.items()}}
        output.append(out)
    return output,inference


def select_balanced(rows,n):
    # Maximal marginal relevance: prioritize usefulness and add calibrated lane/cluster diversity.
    remain=[r for r in rows if r['privacy_gate'] != 'RESTRICTED']
    picks=[];lane_count=Counter();ws_count=Counter()
    while remain and len(picks)<n:
        pick=max(remain,key=lambda r:(
            round(r['score'] + 7*r['feature_novelty'] - 6*math.log1p(lane_count[r['candidate_lane']])
                  - 3*math.log1p(ws_count[r['workspace_key']]) if r['workspace_key'] else r['score']+7*r['feature_novelty']-6*math.log1p(lane_count[r['candidate_lane']]),6),
            r['record_id']))
        remain.remove(pick);lane_count[pick['candidate_lane']]+=1
        if pick['workspace_key']:ws_count[pick['workspace_key']]+=1
        picks.append({**pick,'queue_position':len(picks)+1})
    return picks


def write_csv(path,rows,columns):
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');w.writeheader()
        w.writerows(rows)


def public_handoff(rows,queue,inference):
    public_lanes=Counter(r['candidate_lane'] for r in rows if r['privacy_gate']!='RESTRICTED')
    risk=Counter(r['privacy_gate'] for r in rows)
    return {'schema':'selma.tanka.coordination.v1','date_utc':'2026-11-21',
            'run_mode':'read_only_review_prioritization','source_count':len(rows),
            'gate_totals':dict(sorted(risk.items())),'candidate_lane_totals':dict(sorted(public_lanes.items())),
            'inferred_workspace_groups':len(inference),
            'proposed_queue_count':len(queue),
            'source_content_shared':False,'source_paths_shared':False,'source_code_executed':False,
            'destination_changes_automated':False,
            'priority_policy':{'formula':'100 * sum(weight_i * feature_i), restricted=0, private_review<=35',
                               'diversity':'MMR: score + 7 novelty - 6 ln(1+lane_hits) - 3 ln(1+workspace_hits)',
                               'manual_approval':'required before imports, executions, live trading, public uploads, or changing locked visuals'},
            'next_approved_step':'Human-reviewed source triage; isolated static dependency and license checks',
            'overrides':['Keep Soulbooks Crowology canonical visual baseline LOCKED',
                         'Never infer running code or model retraining from archive indexing']}


def run(register,config,outdir,size):
    rows=read_rows(register)
    weights=validate_config(config)
    scored,inference=score_rows(rows,weights)
    ranked=sorted(scored,key=lambda r:(-r['score'],r['record_id']))
    queue=select_balanced(scored,size)
    outdir.mkdir(parents=True,exist_ok=True)
    cols=list(scored[0])
    write_csv(outdir/'TANKA_OPTIMIZED_PRIVATE_848.csv',ranked,cols)
    write_csv(outdir/'TANKA_ACTION_QUEUE_PRIVATE.csv',queue,['queue_position']+cols)
    with (outdir/'SELMA_COORDINATION_HANDOFF_SAFE.json').open('w',encoding='utf8') as f:
        json.dump(public_handoff(scored,queue,inference),f,indent=2,sort_keys=True);f.write('\n')
    stats={'count':len(rows),'restricted':sum(r['privacy_gate']=='RESTRICTED' for r in scored),
           'private_review':sum(r['privacy_gate']=='PRIVATE_REVIEW' for r in scored),
           'human_gate':sum(r['privacy_gate']=='HUMAN_GATE' for r in scored),
           'triage_to_inferred':sum(r['lane_source']=='INFERRED_FROM_WORKSPACE' for r in scored),
           'uncategorized':sum(r['candidate_lane']=='Unclassified workspace' for r in scored),
           'inference_groups':len(inference),'queue_count':len(queue),
           'queue_lanes':dict(Counter(r['candidate_lane'] for r in queue))}
    with (outdir/'OPTIMIZATION_RUN_RESULTS.json').open('w',encoding='utf8') as f:
        json.dump(stats,f,indent=2,sort_keys=True);f.write('\n')
    return scored,queue,inference,stats


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--register',default='TANKA_ROUTING_REGISTER_2026-11-21.csv')
    ap.add_argument('--calibration',default='selma_tanka_calibration.json')
    ap.add_argument('--output-dir',default='.')
    ap.add_argument('--queue-size',type=int,default=30)
    args=ap.parse_args()
    if not 1<=args.queue_size<=848:ap.error('queue-size must be 1..848')
    with open(args.calibration,encoding='utf-8') as f:config=json.load(f)
    _,_,_,stats=run(Path(args.register),config,Path(args.output_dir),args.queue_size)
    print(json.dumps(stats,indent=2))
if __name__=='__main__':main()