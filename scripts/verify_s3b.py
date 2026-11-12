"""S3-B completion acceptance using real Serving and the existing Poisson verifier."""
import argparse
from datetime import datetime
import json
import os
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def summarize(directory):
    def load(name):
        return json.loads((directory / (name + '.json')).read_text(encoding='utf-8'))
    summary, h, mobility = load('summary'), load('handover'), load('mobility')
    tokens, flows, radio = load('output_tokens'), load('network_flows'), load('wireless_transfers')
    starts = [e for e in h['events'] if e['event']=='handover_start']
    assert len(starts)==h['summary']['completed_handover_count']
    assert len(h['moves'])==mobility['summary']['pending_moves_added']
    assert len(h['moves'])==len(starts)+h['summary']['pending_move_count']+h['summary']['cancelled_move_count']
    assert h['summary']['completed_draining_count']+h['summary']['incomplete_draining_count']==len(starts)
    for move in h['moves']:
        assert move['draining_wait_s']==round(sum(i['end_s']-i['start_s'] for i in move['draining_wait_intervals']),12)
        if move['status']=='completed':
            assert move['handover_delay_s']==round(move['actual_handover_time_s']-move['planned_at'],12)
        else:
            assert move['handover_delay_s'] is None
    for sid in {e['session_id'] for e in starts}:
        own=[e for e in starts if e['session_id']==sid]
        for a,b in zip(own,own[1:]):
            assert a['drain_end_s'] is not None and b['time_s']>=a['drain_end_s']
    delivered=[tuple(t['token_id']) for t in tokens if t['delivered']]
    assert len(delivered)==len(set(delivered))
    generated=[tuple(t['token_id']) for t in tokens]
    assert len(generated)==len(set(generated))
    logged=[]
    commits_during_drain=0
    with (directory/'events.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            event=json.loads(line)
            if event['event']=='downlink_done': logged.append(tuple(event['token_id']))
            if event['event']=='token_committed' and any(
                    e['session_id']==event['session_id'] and e['time_s']<event['time_s']
                    < (e['drain_end_s'] if e['drain_end_s'] is not None else summary['observation_end_s'])
                    for e in starts):
                commits_during_drain+=1
    duplicates=len(logged)-len(set(logged))
    assert duplicates==0 and set(logged)==set(delivered)
    assert all(0<=f['transferred_bytes']<=f['ready_bytes'] for f in flows+radio)
    by_id={f['flow_id']:f for f in flows}
    with (directory/'network_events.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            row=json.loads(line)
            if row.get('kind')!='allocation': continue
            groups={}
            for fid in row['active_flow_ids']:
                f=by_id[fid]
                if f['flow_type'] in ('response','handover'):
                    key=(f['session_id'],f['turn_index'])
                    groups[key]=groups.get(key,0)+1
            assert all(count<=1 for count in groups.values())
            assert all(0<=link['utilization']<=1 for link in row['links'].values())
    for name,values in (
            ('handover_delay',[e['time_s']-e['planned_at'] for e in starts]),
            ('draining_duration',[e['drain_end_s']-e['time_s'] for e in starts if e['drain_end_s'] is not None]),
            ('draining_wait',[m['draining_wait_s'] for m in h['moves'] if m['draining_wait_s']>0])):
        values=sorted(values)
        expected={'mean':sum(values)/len(values) if values else None,
                  'max':max(values,default=None),
                  'p95':values[math.ceil(.95*len(values))-1] if values else None}
        for label,value in expected.items():
            actual=h['summary'][f'{label}_{name}_s']
            assert actual is None if value is None else abs(actual-value)<1e-9
    return dict(summary=summary, handover=h['summary'], mobility=mobility['summary'],
                generated_tokens=len(tokens), delivered_tokens=len(delivered),
                arrived_sessions=len(load('sessions')),
                gpu_kv_commits_during_draining=commits_during_drain,
                undelivered_tokens=len(tokens)-len(delivered), duplicate_deliveries=duplicates,
                original_response_bytes=sum(f['transferred_bytes'] for f in flows if f['flow_type']=='response'),
                handover_forward_bytes=sum(f['transferred_bytes'] for f in flows if f['flow_type']=='handover'),
                wireless_delivered_bytes=sum(t['text_bytes'] for t in tokens if t['delivered']),
                wireless_down_transferred_bytes=sum(f['transferred_bytes'] for f in radio if f['flow_type']=='download'),
                moves=h['moves'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path)
    parser.add_argument('--workload-results',type=Path,help='Existing verify_workload output from this source version')
    args=parser.parse_args()
    out=(args.out or ROOT/'runs'/('s3b_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))).resolve()
    out.mkdir(parents=True,exist_ok=False)
    env=dict(os.environ,PYTHONPATH=str(ROOT/'src'),PYTHONIOENCODING='utf-8')
    commands=[]
    def run(label,arguments):
        command=[sys.executable,*arguments]
        with (out/(label+'.log')).open('w',encoding='utf-8') as log:
            result=subprocess.run(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
        commands.append(dict(command=command,exit_code=result.returncode))
        if result.returncode: raise RuntimeError(f'{label} failed: {out}')
    run('deterministic',['-m','unittest','discover','-s','tests','-p','test_handover*.py','-v'])
    workload=args.workload_results.resolve() if args.workload_results else out/'poisson'
    if args.workload_results is None:
        run('poisson',['scripts/verify_workload.py','--out',str(workload)])
    verification=json.loads((workload/'verification.json').read_text(encoding='utf-8'))
    assert all(c['exit_code']==0 for c in verification['commands'])
    normal=summarize(workload/'serving')
    # Same real seeded multi-Area Poisson input and cutoff, slower radio
    # deliberately expose live Draining and queued plans. Only local output config.
    config=json.loads((ROOT/'configs/poisson_session_smoke.json').read_text(encoding='utf-8'))
    config['network']['wireless_down_bits_per_second']=.08
    config_path=out/'incomplete_config.json'
    config_path.write_text(json.dumps(config,indent=2),encoding='utf-8')
    run('incomplete_poisson',['-m','replacement.demos.serving_demo','--config',str(config_path),'--out',str(out/'incomplete')])
    incomplete=summarize(out/'incomplete')
    assert incomplete['handover']['incomplete_draining_count']>0
    assert incomplete['handover']['pending_move_count']>0
    assert incomplete['summary']['mean_full_turn_e2e_s'] is None
    assert normal['gpu_kv_commits_during_draining']+incomplete['gpu_kv_commits_during_draining']>0
    assert normal['arrived_sessions']>1 and normal['summary']['planned_turns']>normal['arrived_sessions']
    result=dict(commands=commands,normal=normal,incomplete=incomplete)
    (out/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('S3-B acceptance PASS:',out/'summary.json')


if __name__=='__main__': main()
