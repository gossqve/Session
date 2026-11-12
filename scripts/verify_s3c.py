"""Full S3-C acceptance: existing historical chains plus independent trace audit."""
import argparse
from bisect import bisect_left
from datetime import datetime
from fractions import Fraction
import json
import math
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def close(a,b):
    assert abs(float(a)-float(b))<=1e-8,(a,b)


def audit(directory, *, oracle=False):
    """Independent B2-5d/C12-22/E35-39 oracles on actual CLI artifacts.

    GPU integral uses service intervals, KV uses structural parameters and
    per-event deltas, transport uses PRIOR rate*elapsed/8, E2E uses UE logs.
    Small allocation graphs use the independent rational vertex Oracle.
    No production evaluator/MaxMinAllocator is called to make expectations.
    """
    def load(name):return json.loads((directory/(name+'.json')).read_text(encoding='utf-8'))
    config=load('config');summary=load('summary');turns=load('turns')
    tokens=load('output_tokens');sessions=load('sessions');flows=load('network_flows')
    radio=load('wireless_transfers');evaluation=load('evaluation');handover=load('handover')
    by_token={tuple(t['token_id']):t for t in tokens}
    assert len(by_token)==len(tokens)
    events=[json.loads(line) for line in (directory/'events.jsonl').read_text(encoding='utf-8').splitlines()]
    assert all(e['time_s']<=summary['observation_end_s'] for e in events)
    deliveries=[tuple(e['token_id']) for e in events if e['event']=='downlink_done']
    assert len(deliveries)==len(set(deliveries))
    assert set(deliveries)=={k for k,t in by_token.items() if t['delivered']}
    end_events={s['session_id']:s['end_time'] for s in sessions}
    submitted_events={(e['session_id'],e['turn_index']):e['time_s'] for e in events if e['event']=='turn_submit'}
    completed_events={(e['session_id'],e['turn_index']):e['time_s'] for e in events if e['event']=='turn_complete'}
    completed_event_delays=[]
    for row in turns:
        own=[t for t in tokens if t['session_id']==row['session_id'] and t['turn_index']==row['turn_index']]
        assert [t['output_index'] for t in own]==list(range(1,row['decode_done']+1))
        assert [t['output_index'] for t in own if t['delivered']]==list(range(1,row['delivered']+1))
        if row['status']=='completed':
            stop=own[-1]['received_at'] if own else row['generation_ended_at']
            assert row['received_at']==stop
            close(row['e2e_s'],stop-row['submitted_at'])
            key=row['session_id'],row['turn_index']
            assert completed_events[key]==stop
            completed_event_delays.append(completed_events[key]-submitted_events[key])
    completed=[r['e2e_s'] for r in turns if r['status']=='completed']
    planned=(load('workload')['plan']['sessions'] if 'workload' in config and config['workload'].get('mode')=='poisson'
             else config['sessions'])
    assert summary['planned_turns']==sum(len(s['turns']) for s in planned)
    assert summary['submitted_turns']==len(turns)
    assert summary['completed_turns']==len(completed)
    assert summary['unfinished_turns']==summary['planned_turns']-len(completed)
    expected_mean=sum(completed)/len(completed) if completed and len(completed)==summary['planned_turns'] else None
    if expected_mean is None:assert summary['mean_full_turn_e2e_s'] is None
    else:close(summary['mean_full_turn_e2e_s'],expected_mean)
    # G1 is independent of the all-planned diagnostic. Derive its oracle from
    # actual submission/completion events, not from evaluation's own output.
    assert evaluation['summary']['g1_metric']=='mean_completed_full_turn_e2e_s'
    g1=math.fsum(completed_event_delays)/len(completed_event_delays) if completed_event_delays else None
    if g1 is None:assert evaluation['summary']['mean_completed_full_turn_e2e_s'] is None
    else:close(evaluation['summary']['mean_completed_full_turn_e2e_s'],g1)
    assert len(evaluation['active_turn_censoring_lower_bounds'])==evaluation['summary']['right_censored_turns']
    assert len(evaluation['terminated_turns'])==evaluation['summary']['failed_submitted_turns']
    assert evaluation['summary']['unsubmitted_turns']==summary['planned_turns']-len(turns)
    for row in evaluation['unfinished_turns']:
        active=end_events[row['session_id']] is None
        assert row['right_censored']==active
        if active:close(row['right_censored_e2e_lower_bound_s'],summary['observation_end_s']-row['submitted_at'])
        else:assert row['right_censored_e2e_lower_bound_s'] is None
    models={m['id']:m for m in config['models']};edges={e['id']:e for e in config['edges']}
    gpu=load('gpu_events');gpu_work=0;busy=0
    for eid,trace in gpu.items():
        for r in trace:
            if r['event']!='service':continue
            n=r['running_count'];cap=edges[eid]['gpu_work_per_second']
            assert 0<=n<=edges[eid]['gpu_slots']
            expected=r['elapsed_s']*cap if n else 0
            assert -.00000001<=expected-r['consumed_work']<=cap*1e-12+1e-8
            gpu_work+=r['consumed_work'];busy+=r['elapsed_s'] if n else 0
    close(gpu_work,sum(r['gpu_service_work'] for r in turns));close(gpu_work,summary['gpu_work'])
    close(busy,evaluation['summary']['gpu_busy_edge_time_s'])
    kv_checks=0
    for eid,trace in load('kv_events').items():
        ledger={}
        for r in trace:
            sid=r['session_id'];old=ledger.get(sid,0)
            assert r['session_kv_before']==old
            if r['event']=='token_committed':
                m=models[r['model_id']];old+=2*m['layers']*m['kv_heads']*m['head_dim']*m['element_bytes']
            elif r['event']=='kv_release':old=0
            ledger[sid]=old
            assert r['session_kv_after']==old
            assert sum(ledger.values())==r['edge_used_bytes']
            assert 0<=r['edge_used_bytes']<=edges[eid]['kv_capacity_bytes']
            kv_checks+=1
    starts=[e for e in handover['events'] if e['event']=='handover_start']
    origins={s.get('session_id',s.get('id')):s for s in planned}
    for sid,origin in origins.items():
        moves=[e for e in starts if e['session_id']==sid]
        times=[e['time_s'] for e in moves]
        for t in (t for t in tokens if t['session_id']==sid):
            index=bisect_left(times,t['generated_at'])-1
            access=moves[index]['target_edge_id'] if index>=0 else origin['access_edge_id']
            assert (t['access_edge_id'],t['execution_edge_id'])==(access,origin['execution_edge_id'])
        for move in moves:
            frozen=[t for t in tokens if t['session_id']==sid and t['generated_at']<=move['time_s']
                    and (t['received_at'] is None or t['received_at']>move['time_s'])]
            assert [tuple(t['token_id']) for t in frozen]==[tuple(k) for k in move['old_token_ids']]
            expected_end=(max(t['received_at'] for t in frozen) if frozen and all(t['delivered'] for t in frozen)
                          else move['time_s'] if not frozen else None)
            assert expected_end==move['drain_end_s']
    overhead=sum(f['transferred_bytes'] for f in flows if f['flow_type']=='handover')
    close(overhead,evaluation['transport']['handover_forward_bytes'])
    # Stream all per-flow transitions: settle PRIOR Byte using PRIOR rates,
    # including a partial final segment. Never multiply logical Byte by hops.
    def byte_audit(rows,final_rows):
        last={};checks=0
        for r in rows:
            if 'flow_id' not in r or 'transferred_bytes' not in r:continue
            fid=r['flow_id']
            if r['kind']=='progress':
                previous=last[fid]
                amount=min(previous['ready_bytes']-previous['transferred_bytes'],
                           previous['rate_bps']*(r['time_s']-previous['time_s'])/8)
                close(r['transferred_bytes'],previous['transferred_bytes']+amount);checks+=1
            assert 0<=r['transferred_bytes']<=r['ready_bytes']
            last[fid]=r
        assert set(last)=={f['flow_id'] for f in final_rows}
        for f in final_rows:
            recorded=last[f['flow_id']]
            assert recorded['ready_bytes']==f['ready_bytes']
            close(recorded['transferred_bytes'],f['transferred_bytes'])
            close(recorded['rate_bps'],f['rate_bps'])
            assert recorded['status']==f['status']
            if f['status']=='completed':close(f['transferred_bytes'],f['ready_bytes'])
        return checks
    def network_rows():
        with (directory/'network_events.jsonl').open(encoding='utf-8') as stream:
            for line in stream:yield json.loads(line)
    byte_checks=byte_audit(network_rows(),flows)+byte_audit(load('wireless_events'),radio)
    for kind,key in (('prompt','original_prompt_bytes'),('response','original_response_bytes'),('handover','handover_forward_bytes')):
        close(sum(f['transferred_bytes'] for f in flows if f['flow_type']==kind),evaluation['transport'][key])
    for kind,key in (('upload','wireless_upload_bytes'),('download','wireless_download_bytes')):
        close(sum(f['transferred_bytes'] for f in radio if f['flow_type']==kind),evaluation['transport'][key])
    close(sum(t['text_bytes'] for t in tokens if t['delivered']),evaluation['transport']['ue_delivered_response_bytes'])
    oracle_checks=0;cache={}
    by_id={f['flow_id']:f for f in flows}
    sys.path.insert(0,str(ROOT/'tests'))
    from max_min_oracle import vertex_oracle
    for r in network_rows():
        if r.get('kind')!='allocation':continue
        loads={lid:0 for lid in r['links']};shares={}
        for fid,f in r['flows'].items():
            for lid in f['link_ids']:loads[lid]+=f['rate_bps']
            if fid in r['active_flow_ids'] and by_id[fid]['flow_type'] in ('response','handover'):
                key=by_id[fid]['session_id'],by_id[fid]['turn_index'];shares[key]=shares.get(key,0)+1
        assert all(n<=1 for n in shares.values())
        for lid,value in loads.items():
            close(value,r['links'][lid]['load_bps']);assert value<=r['links'][lid]['capacity_bps']+1e-8
        ids=r['active_flow_ids']
        if oracle and ids:
            patterns=tuple(tuple(r['flows'][fid]['link_ids']) for fid in ids)
            capacities={lid:r['links'][lid]['capacity_bps'] for path in patterns for lid in path}
            key=patterns,tuple(sorted(capacities.items()))
            if key not in cache:cache[key]=vertex_oracle({str(i):path for i,path in enumerate(patterns)},capacities)
            for i,fid in enumerate(ids):close(r['flows'][fid]['rate_bps'],cache[key][str(i)])
            oracle_checks+=1
    return dict(summary=evaluation['summary'],transport=evaluation['transport'],
                generated_tokens=len(tokens),delivered_tokens=len(deliveries),
                gpu_integral_work=gpu_work,kv_transition_checks=kv_checks,
                byte_progress_checks=byte_checks,independent_vertex_oracle_allocations=oracle_checks,
                frozen_sets_checked=len(starts),unfinished_turns=evaluation['unfinished_turns'])


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path)
    args=parser.parse_args();out=(args.out or ROOT/'runs'/('s3c_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))).resolve()
    out.mkdir(parents=True,exist_ok=False);commands=[]
    env=dict(os.environ,PYTHONPATH=str(ROOT/'src'),PYTHONIOENCODING='utf-8')
    def run(label,arguments):
        command=[sys.executable,*arguments]
        with (out/(label+'.log')).open('w',encoding='utf-8') as log:
            result=subprocess.run(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
        commands.append(dict(label=label,command=command,exit_code=result.returncode))
        (out/'commands.json').write_text(json.dumps(commands,indent=2),encoding='utf-8')
        if result.returncode:raise RuntimeError(f'{label} failed: {out}')
    run('directed',['-m','unittest','discover','-s','tests','-p','test_s3c*.py','-v'])
    run('history',['scripts/verify_s3a.py','--out',str(out/'s3a')])  # includes S2C Oracle/S1E/full unittest
    run('s3b',['scripts/verify_s3b.py','--out',str(out/'s3b')])  # includes normal Poisson and incomplete radio
    run('hand',['-m','replacement.demos.serving_demo','--config','configs/s3c_hand_shared.json','--out',str(out/'hand')])
    results={name:audit(directory,oracle=name=='hand') for name,directory in (
        ('hand',out/'hand'),('poisson',out/'s3b/poisson/serving'),('incomplete',out/'s3b/incomplete'))}
    assert results['hand']['summary']['completed_turns']==4
    close(results['hand']['gpu_integral_work'],9)
    close(results['hand']['transport']['handover_forward_bytes'],2)
    (out/'summary.json').write_text(json.dumps(dict(status='PASS',commands=commands,scenarios=results),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('S3-C Evidence:',out/'summary.json')


if __name__=='__main__':main()
