"""Seeded legal S3 bug-finding workloads, independent event-state oracles.

This is test support, not a policy, workload distribution for experiments, or
another simulator. Reuse the formal topology and unique ServingSimulator.
"""
from copy import deepcopy
from dataclasses import asdict, replace
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import random
import secrets
import sys
import time
import traceback
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from replacement.simulation.serving import ServingSimulator
from replacement.core.workload_generation import WorkloadGenerator


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def case_seed(master,index):
    return int.from_bytes(hashlib.sha256(f'Session:S3:random:v1:{master}:{index}'.encode()).digest(),'big')


def settings(default=50):
    seed=int(os.environ['SESSION_TEST_SEED']) if 'SESSION_TEST_SEED' in os.environ else secrets.randbits(128)
    count=int(os.environ.get('SESSION_TEST_CASES',str(default)))
    if count<1:raise ValueError('SESSION_TEST_CASES must be positive')
    return seed,count


def make_case(master,index):
    seed=case_seed(master,index);rng=random.Random(seed);mode=index%8
    c=json.loads((ROOT/'configs/poisson_session_smoke.json').read_text(encoding='utf-8'))
    c.pop('workload');c['seed']=seed;c['scenario']=f'random_{index}_mode{mode}'
    c['observation_end_s']=rng.choice([2,3,4,6]);c['max_events']=100000
    c['models'][0].update(context_window_tokens=rng.choice([16,32,64]),output_limit_per_turn=6)
    c['models'][1].update(context_window_tokens=48,output_limit_per_turn=6)
    capacity=rng.choice([12,16,24,48,128]) if mode==3 else rng.choice([64,96,256])
    for edge in c['edges']:
        edge.update(gpu_work_per_second=rng.choice([5,8,10,16]),gpu_slots=rng.randint(1,3),kv_capacity_bytes=capacity)
    for link in c['topology']['links']:link['capacity_bps']=rng.choice([40,80,160])
    c['network'].update(wireless_up_bits_per_second=rng.choice([16,40,80,160]),wireless_down_bits_per_second=rng.choice([8,16,40,80]))
    if mode==5:c['network']['wireless_down_bits_per_second']=rng.choice([.5,1,2])
    ids=[e['id'] for e in c['edges']]
    c['topology']['mobility_adjacency']={eid:[ids[(i+1)%len(ids)]] for i,eid in enumerate(ids)}
    c['mobility']['check_interval_s']=rng.choice([.1,.2,.3,.5])
    c['mobility']['min_inter_move_interval_s']=rng.choice([0,.2,.5])
    stay,move=rng.choice([(.25,.75),(.5,.5),(0,1)])
    c['mobility']['transition_probabilities']={eid:{eid:stay,ids[(i+1)%len(ids)]:move} for i,eid in enumerate(ids)}
    if mode==1:
        if index//8%2==0:c.pop('handover')  # real plans without actual switching
        else:c['mobility']['transition_probabilities']={eid:{eid:1} for eid in ids}
    common=rng.choice(ids);sessions=[]
    for i in range(rng.randint(2,5)):
        access=common if mode in (2,3,5) else rng.choice(ids)
        execution=common if mode==0 else (rng.choice(ids) if mode==6 else ids[2])
        turns=[dict(input_tokens=rng.randint(0,3),output_tokens=rng.randint(0,6)) for _ in range(rng.randint(1,3))]
        if i==0:turns[0]['input_tokens']=rng.randint(1,3)
        sessions.append(dict(id=f'S{i}',model_id=rng.choice(['m4','m8']),arrival_time=0 if i==0 or mode==2 else rng.choice([0,.1,.2,.4,.8]),
                             access_edge_id=access,execution_edge_id=execution,turns=turns))
    c['sessions']=sessions
    if mode==0:c.pop('mobility');c.pop('handover')
    if mode==6:
        c.pop('sessions')
        c['workload']=dict(mode='poisson',arrival_rate_per_s=rng.choice([3,5,8]),arrival_horizon_s=.6,model_id='m4',
                           turn_count=dict(min=1,max=3),input_tokens=dict(min=1,max=3),output_tokens=dict(min=0,max=6))
    if mode==4:
        # Independent C13/18/21 recovery Oracle: multiply all times by scale.
        scale=rng.choice([.5,1,2]);c['observation_end_s']=2*scale
        for e in c['edges']:e.update(gpu_work_per_second=10/scale,gpu_slots=1,kv_capacity_bytes=12)
        for link in c['topology']['links']:link['capacity_bps']=80/scale
        c['network'].update(wireless_up_bits_per_second=80/scale,wireless_down_bits_per_second=80/scale)
        c['sessions']=[dict(id=f'S{i}',model_id='m4',arrival_time=0,access_edge_id='E1',execution_edge_id='E3',turns=[dict(input_tokens=1,output_tokens=1)]) for i in range(2)]
        c['sessions'][0]['network']=dict(wireless_down_bits_per_second=8/scale)
        c['mobility'].update(check_interval_s=.65*scale,min_inter_move_interval_s=0,
             transition_probabilities={eid:{({'E1':'E3','E3':'E5'}.get(eid,eid)):1} for eid in ids})
        c['topology']['mobility_adjacency']={eid:([{'E1':'E3','E3':'E5'}[eid]] if eid in ('E1','E3') else []) for eid in ids}
        c['models'][0]['context_window_tokens']=64
    if mode==7:
        # Real simultaneous HO + third Prompt, preserving the hand-derived
        # three-Flow contention shape while varying physical time/element size.
        c=json.loads((ROOT/'configs/s3c_hand_shared.json').read_text(encoding='utf-8'))
        c['seed']=seed;c['scenario']=f'random_{index}_mode7';scale=rng.choice([.5,1,1.5,2])
        c['observation_end_s']*=scale;c['mobility']['check_interval_s']*=scale
        for e in c['edges']:e['gpu_work_per_second']/=scale
        for link in c['topology']['links']:link['capacity_bps']/=scale
        for key in ('wireless_up_bits_per_second','wireless_down_bits_per_second'):c['network'][key]/=scale
        for s in c['sessions']:s['arrival_time']*=scale
    c['topology']['edges']=deepcopy(c['edges'])
    if 'mobility' in c:
        c['topology']['mobility_transitions']=[[source,target]
            for source,row in c['mobility']['transition_probabilities'].items()
            for target,p in row.items() if target!=source and p>0]
    return c


def require(condition,message):
    if not condition:raise AssertionError(message)


def assert_current(sim):
    """C12/13/16-18/41 and B2/3 independent current-prefix sums."""
    owners=set()
    for edge in sim.runtime.edges.values():
        rates=edge.compute.scheduler.rates
        require(len(rates)<=edge.gpu_slots,'GPU slots')
        if rates:
            require(all(abs(r-edge.gpu_capacity/len(rates))<1e-9 for r in rates.values()),'GPU equal share')
        for task in edge.running_tasks:
            key=task.session_id,task.turn_index
            require(key not in owners,'double execution');owners.add(key)
            require(task.execution_edge_id==sim.runtime.sessions[task.session_id].execution_edge_id,'GPU authority')
        used=0
        for sid in edge.resident_session_ids:
            s=sim.runtime.sessions[sid];m=sim.runtime.models[s.model_id]
            expected=2*m.layers*m.kv_heads*m.head_dim*m.element_bytes*s.context_tokens
            require(s.execution_edge_id==edge.edge_id and s.authoritative_kv_bytes==expected,'KV structural authority')
            used+=expected
        require(used==edge.kv.used_bytes and 0<=used<=edge.kv_capacity_bytes,'KV capacity')
    for sid,s in sim.runtime.sessions.items():
        require(s.context_tokens==sum(t.prefill_done+t.decode_done for t in s.turns),'Context cumulative')
        require(sum(t.status not in ('completed','failed') for t in s.turns)<=1,'serial Turn')
        for a,b in zip(s.turns,s.turns[1:]):require(a.status=='completed' and b.submitted_at==a.received_at,'zero Idle')
        for t in s.turns:
            require(0<=t.delivered<=t.decode_done==len(t.output_tokens),'delivery prefix')
            require([token.token_id for token in t.output_tokens]==[(sid,t.index,i) for i in range(1,t.decode_done+1)],'generated identity prefix')
            require(0<=t.prefill_done<=t.input_tokens,'Prefill prefix')
        require(not(sid in sim._prompt_active and sid in sim._downlink_busy),'serial protections')
        if sim.mobility:
            state=sim.mobility.sessions[sid];source=s.access_edge_id if sim.handover else s.initial_access_edge_id
            require(state.active==(s.end_time is None),'mobility lifecycle cancellation')
            if not sim.handover:require(s.access_edge_id==s.initial_access_edge_id,'planned/actual separation')
            for move in state.pending_moves:
                # Planned-only queues are intentionally not consumed.
                require(move.source_edge_id==source,'Pending source FIFO')
                require(move.target_edge_id in sim.topology.mobility_adjacency.get(move.source_edge_id,()),'Pending adjacency')
                source=move.target_edge_id
    if sim.network:
        loads={lid:Fraction(0) for lid in sim.topology.links};shares={};active=[]
        for f in sim.network.flows.values():
            require(0<=f.transferred_bytes<=f.ready_bytes,'wired G/Y')
            require(f.rate_bps>=0,'nonnegative wired rate')
            if f.status=='completed':require(f.transferred_bytes==f.ready_bytes,'completed wired G/Y')
            if f.rate_bps:
                require(f.status=='active' and f.started_at is not None and f.pending_bytes>0 and f.completed_at is None and f.cancelled_at is None,'wired positive-rate eligibility')
                active.append(f)
                for lid in f.link_ids:loads[lid]+=Fraction(f.rate_bps)
                if f.flow_type in ('response','handover'):
                    key=f.session_id,f.turn_index;shares[key]=shares.get(key,0)+1
        require(all(loads[lid]<=Fraction(str(link.capacity_bps)) for lid,link in sim.topology.links.items()),'link capacity')
        require(all(n<=1 for n in shares.values()),'single response share')
        if active and len({f.link_ids for f in active})==1:
            # Exact symmetric-path Max-Min Oracle, independently C/n.
            expected=min(Fraction(str(sim.topology.links[l].capacity_bps)) for l in active[0].link_ids)/len(active)
            require(all(f.rate_bps==expected for f in active),'independent symmetric Max-Min')
    for f in sim.wireless.flows.values():
        require(0<=f.transferred_bytes<=f.ready_bytes,'radio G/Y')
        require(f.rate_bps>=0,'nonnegative radio rate')
        if f.rate_bps:require(f.status=='active' and f.started_at is not None and f.pending_bytes>0 and f.completed_at is None and f.cancelled_at is None,'radio positive-rate eligibility')
        if f.status=='completed':require(f.transferred_bytes==f.ready_bytes,'completed radio G/Y')


def assert_result(sim,c,plan=None):
    out=sim.results();summary=out['summary'];tokens=out['output_tokens']
    ids=[tuple(t['token_id']) for t in tokens]
    require(len(ids)==len(set(ids)),'unique generated Token')
    received=[tuple(e['token_id']) for e in out['events'] if e['event']=='downlink_done']
    require(len(received)==len(set(received)) and set(received)=={tuple(t['token_id']) for t in tokens if t['delivered']},'actual UE identity')
    require(sim.time_s==c['observation_end_s'] and sim.step() is None,'Tobs boundary')
    require(all(e['time_s']<=sim.time_s for e in out['events']),'event after Tobs')
    completed=[r for r in out['turns'] if r['status']=='completed']
    require('workload' not in c or plan is not None,'Poisson oracle requires original immutable input plan')
    planned=sum(len(s.turns) for s in plan.sessions) if plan is not None else sum(len(s['turns']) for s in c['sessions'])
    submitted=sum(len(s.turns) for s in sim.runtime.sessions.values())
    require(summary['planned_turns']==planned and summary['submitted_turns']==submitted==len(out['turns']),'independent workload denominator')
    require(summary['completed_turns']==len(completed) and summary['unfinished_turns']==planned-len(completed),'independent completion counts')
    require(summary['completion_rate']==(len(completed)/planned if planned else None),'independent completion rate')
    expected=round(math.fsum(r['received_at']-r['submitted_at'] for r in completed)/len(completed),12) if completed and len(completed)==planned else None
    require(summary['mean_full_turn_e2e_s']==expected,'main full-population mean')
    by_token={tuple(t['token_id']):t for t in tokens}
    for r in out['turns']:
        key=r['session_id'],r['turn_index']
        deliveries=[e for e in out['events'] if e['event']=='downlink_done' and tuple(e['token_id'])[:2]==key]
        require([tuple(e['token_id']) for e in deliveries]==[(*key,i) for i in range(1,r['delivered']+1)],'UE FIFO identity prefix')
        require([e['time_s'] for e in deliveries]==sorted(e['time_s'] for e in deliveries),'UE FIFO times')
        for i in range(1,r['decode_done']+1):
            token=by_token[(*key,i)];delivered=i<=r['delivered']
            receive=deliveries[i-1]['time_s'] if delivered else None
            require(token['delivered']==delivered and token['received_at']==token['delivered_at']==receive,'UE timestamp identity')
            if delivered:require(token['generated_at']<=receive<=sim.time_s,'real UE cutoff')
        if r['status'] not in ('completed','failed'):
            require(r['received_at'] is None and r['e2e_s'] is None,'no fabricated unfinished time')
        elif r['received_at'] is not None:
            # ContextLimit may deliver its real generated prefix, then fail.
            # This timestamp is real but never gives that Turn G1 credit.
            require(r['delivered']==r['decode_done'],'ended Turn delivery prefix')
            end=deliveries[-1]['time_s'] if deliveries else r['generation_ended_at']
            if r['status']=='failed':
                require(r['generation_ended_at'] is not None,'real failed generation end')
                end=max(end,r['generation_ended_at'])
            require(r['received_at']==end and r['e2e_s']==round(end-r['submitted_at'],12),'real ended-prefix timestamp')
    if 'evaluation' in out:
        evaluation=out['evaluation'];metric=evaluation['summary']
        require(metric['unsubmitted_turns']==planned-submitted,'independent unsubmitted count')
        require(metric['submitted_unfinished_turns']==submitted-len(completed),'independent submitted unfinished count')
        diagnostic=round(math.fsum(r['received_at']-r['submitted_at'] for r in completed)/len(completed),12) if completed else None
        require(metric['mean_completed_full_turn_e2e_s']==diagnostic and metric['mean_full_turn_e2e_s']==expected,'diagnostic/main separation')
        active=[r for r in out['turns'] if r['status']!='completed' and sim.runtime.sessions[r['session_id']].end_time is None]
        require(metric['right_censored_turns']==len(active) and metric['failed_submitted_turns']==submitted-len(completed)-len(active),'censoring/termination counts')
        require(evaluation['active_turn_censoring_lower_bounds']==[dict(session_id=r['session_id'],turn_index=r['turn_index'],lower_bound_s=round(sim.time_s-r['submitted_at'],12)) for r in active],'independent censoring lower bounds')
    for r in completed:
        if r['decode_done']:require(r['received_at']==by_token[(r['session_id'],r['turn_index'],r['decode_done'])]['received_at'],'last UE E2E')
        else:require(r['received_at']==r['generation_ended_at'],'legal zero-output end')
    gpu_work=0
    for eid,trace in out['gpu_events'].items():
        cap=sim.runtime.edges[eid].gpu_capacity
        for row in trace:
            if row['event']=='service':
                require(0<=row['consumed_work']<=cap*row['elapsed_s']+1e-8,'GPU service integral budget')
                expected=cap*row['elapsed_s'] if row['running_count'] else 0
                require(abs(expected-row['consumed_work'])<=cap*1e-12+1e-8,'work-conserving GPU integral')
                gpu_work+=row['consumed_work']
    require(abs(gpu_work-summary['gpu_work'])<1e-8,'GPU total service')
    units=set();independent_work=0
    for edge in sim.runtime.edges.values():
        for task in edge.compute.tasks.values():
            unit=(task.session_id,task.turn_index,task.phase,task.unit_index)
            require(unit not in units,'no recomputed GPU unit');units.add(unit)
            m=sim.runtime.models[sim.runtime.sessions[task.session_id].model_id]
            work=m.prefill_work_per_token if task.phase=='prefill' else m.decode_work_per_token
            require(-1e-8<=task.consumed_work<=work+1e-8,'independent GPU unit budget')
            if task.completion_time is not None:require(abs(task.consumed_work-work)<1e-8,'completed unit work')
            independent_work+=task.consumed_work
    require(abs(gpu_work-independent_work)<1e-8,'GPU trace versus independent unit sum')
    for f in out['network_flows']+out['wireless_transfers']:
        s=sim.runtime.sessions[f['session_id']];turn=s.turns[f['turn_index']-1]
        if f['flow_type'] in ('prompt','upload'):
            require(f['ready_bytes']==turn.input_tokens*s.text_bytes_per_token,'independent Prompt supply')
        if f['flow_type']=='download':require(f['ready_bytes']==s.text_bytes_per_token,'independent Token wireless supply')
        if f['token_boundaries']:
            boundaries=f['token_boundaries'];total=0
            for b in boundaries:
                total+=by_token[tuple(b['token_id'])]['text_bytes']
                require(b['cumulative_bytes']==total,'independent frozen Token Byte boundary')
            require(f['ready_bytes']==total,'response supply equals frozen Token Byte')
    feature=dict(kv_blocked=sum(t['block_count'] for t in out['turns']),recovered=sum(e['event']=='pending_committed' for e in out['events']),
                 zero_output_completed=sum(r['decode_done']==0 for r in completed),queue_wait=summary['gpu_queue_wait_s']>0,
                 completed_turns=len(completed),sessions=len(out['sessions']),handovers=0,pending=0,incomplete_drains=0)
    if sim.mobility:
        for sid,state in sim.mobility.sessions.items():
            s=sim.runtime.sessions[sid];previous=s.initial_access_edge_id;last_time=None
            events=[e for e in out['mobility']['events'] if e['session_id']==sid]
            rejected={e['check_index'] for e in events if e['event']=='mobility_move_rejected'}
            end_index=next((i for i,e in enumerate(events) if e['event']=='mobility_session_end'),len(events))
            for number,e in enumerate((e for e in events if e['event']=='mobility_check'),1):
                require(e['check_index']==number,'sequential mobility index')
                require(e['time_s']==round(s.arrival_time+number*c['mobility']['check_interval_s'],12),'arrival-relative mobility clock')
                # Mobility phase80 can precede a zero-Turn completion at phase85
                # at the SAME clock. Use recorded lifecycle order as well as time.
                require((s.end_time is None or e['time_s']<=s.end_time) and events.index(e)<end_index,'ended Session mobility')
                require(e['source_edge_id']==previous,'previous planned Markov row')
                target=e['target_edge_id']
                if number not in rejected:require(c['mobility']['transition_probabilities'][previous].get(target,0)>0,'positive Markov transition')
                else:require(target==previous,'rejected move must preserve planned Access')
                if target!=previous:
                    if last_time is not None:require(round(e['time_s']-last_time,12)>=c['mobility'].get('min_inter_move_interval_s',0),'accepted plan interval')
                    last_time=e['time_s']
                previous=target
    if sim.handover:
        starts=[e for e in out['handover']['events'] if e['event']=='handover_start']
        last={}
        for e in starts:
            sid=e['session_id']
            own=[m for m in out['mobility']['events'] if m['event']=='mobility_pending_added' and m['session_id']==sid]
            used=sum(h['session_id']==sid for h in starts[:starts.index(e)])
            require(used<len(own) and all(e[k]==own[used][k] for k in ('check_index','planned_at','source_edge_id','target_edge_id')),'consumed Pending FIFO history')
            require(e['time_s']>=e['planned_at'],'no future move consumption')
            if sid in last:require(last[sid]['drain_end_s'] is not None and e['time_s']>last[sid]['time_s'] and e['time_s']>=last[sid]['drain_end_s'],'serial HO/Drain')
            source=last[sid]['target_edge_id'] if sid in last else sim.runtime.sessions[sid].initial_access_edge_id
            require(e['source_edge_id']==source,'actual Access source chain')
            if sid in last:require(round(e['time_s']-last[sid]['time_s'],12)>=c['mobility'].get('min_inter_move_interval_s',0),'actual switch minimum interval')
            frozen=[t for t in tokens if t['session_id']==sid and t['generated_at']<=e['time_s'] and (t['received_at'] is None or t['received_at']>e['time_s'])]
            require([tuple(t['token_id']) for t in frozen]==[tuple(t) for t in e['old_token_ids']],'frozen old set')
            end=max(t['received_at'] for t in frozen) if frozen and all(t['delivered'] for t in frozen) else e['time_s'] if not frozen else None
            require(end==e['drain_end_s'],'drain UE boundary');last[sid]=e
        origins=out.get('workload',{}).get('plan',{}).get('sessions',c.get('sessions',[]))
        for origin in origins:
            sid=origin.get('session_id',origin.get('id'));own=[e for e in starts if e['session_id']==sid]
            for t in (t for t in tokens if t['session_id']==sid):
                before=[e for e in own if e['time_s']<t['generated_at']]
                access=before[-1]['target_edge_id'] if before else origin['access_edge_id']
                require((t['access_edge_id'],t['execution_edge_id'])==(access,origin['execution_edge_id']),'frozen generation provenance')
        moves=out['mobility']['summary']
        require(moves['pending_moves_added']==len(starts)+moves['pending_moves_cancelled']+moves['pending_moves_at_observation_end'],'Pending conservation')
        feature.update(handovers=len(starts),pending=moves['pending_moves_at_observation_end'],incomplete_drains=out['handover']['summary']['incomplete_draining_count'])
        y=sum(f['transferred_bytes'] for f in out['network_flows'] if f['flow_type']=='handover')
        require(abs(y-out['evaluation']['transport']['handover_forward_bytes'])<1e-8,'actual HO logical Y')
    for trace in (out['network_events'],out['wireless_events']):
        previous={}
        for r in trace:
            if 'flow_id' not in r or 'transferred_bytes' not in r:continue
            if r['kind']=='progress':
                old=previous[r['flow_id']]
                amount=min(old['ready_bytes']-old['transferred_bytes'],old['rate_bps']*(r['time_s']-old['time_s'])/8)
                require(abs(r['transferred_bytes']-old['transferred_bytes']-amount)<1e-8,'independent prior-rate Byte integral')
            previous[r['flow_id']]=r
    if c['scenario'].endswith('mode4'):
        scale=c['observation_end_s']/2
        require(summary['completed_turns']==2 and summary['gpu_work']==4 and summary['peak_kv_bytes']==12 and summary['final_kv_bytes']==0,'scaled KV recovery Oracle')
        require(abs(out['turns'][1]['blocked_time_s']-.9*scale)<1e-9,'independent KV wait Oracle')
        require(abs(out['turns'][1]['received_at']-1.8*scale)<1e-9,'independent recovery E2E Oracle')
    return out,feature


def _exercise(c):
    plan=WorkloadGenerator(c).generate() if 'workload' in c else None
    sim=ServingSimulator(c,workload_plan=plan)
    # Paired-prefix test changes private future output and future mobility seed.
    candidates=plan.sessions if plan else c['sessions']
    if candidates:
        first=min(candidates,key=lambda s:s.arrival_time if plan else s['arrival_time'])
        arrival=first.arrival_time if plan else first['arrival_time']
        input_count=first.turns[0].input_tokens if plan else first['turns'][0]['input_tokens']
        if input_count:
            rate=first.wireless_up_bits_per_second if plan else first.get('network',{}).get('wireless_up_bits_per_second',c['network']['wireless_up_bits_per_second'])
            delta=input_count*8/rate/2
            if sim.mobility:delta=min(delta,c['mobility']['check_interval_s']/2)
            prefix=round(arrival+delta,12)
            other=deepcopy(c);other['seed']+=1
            if plan:
                turns=(replace(first.turns[0],hidden_output_tokens=(first.turns[0].hidden_output_tokens+1)%7),*first.turns[1:])
                paired=replace(plan,seed=other['seed'],sessions=tuple(replace(s,turns=turns) if s.session_id==first.session_id else s for s in plan.sessions))
            else:
                paired=None;entry=next(s for s in other['sessions'] if s['id']==first['id'])
                entry['turns'][0]['output_tokens']=(entry['turns'][0]['output_tokens']+1)%7
            peer=ServingSimulator(other,workload_plan=paired)
            sim.advance_to(prefix);peer.advance_to(prefix)
            require(sim.observation()==peer.observation() and sim.events==peer.events,'causal prefix equality')
    steps=0
    while sim.step() is not None:
        steps+=1;require(steps<100000,'event progress');assert_current(sim)
    result,features=assert_result(sim,c,plan)
    # DTOs may contain experienced values only, never plans/config/forecasts.
    encoded=json.dumps(asdict(sim.observation()),sort_keys=True)
    for key in ('hidden_output_tokens','next_check_index','observation_end_s','transition_probabilities','planned_turns'):
        require('"'+key+'"' not in encoded,'observation future field: '+key)
    return result,features


def exercise(c):
    # Preserve the actual failing prefix without hiding the original error.
    # _exercise's traceback frame owns the unique simulator; no replacement run.
    try:
        return _exercise(c)
    except Exception as error:
        tb=error.__traceback__;prefix=None
        while tb:
            sim=tb.tb_frame.f_locals.get('sim')
            if isinstance(sim,ServingSimulator):
                prefix=dict(time_s=sim.time_s,events=list(sim.events))
                try:prefix['result']=sim.results()
                except Exception as snapshot_error:prefix['snapshot_error']=repr(snapshot_error)
            tb=tb.tb_next
        error.random_prefix=prefix
        raise


def run_cases(master,count, *, indices=None, emit=print):
    started=time.monotonic();rows=[]
    emit(json.dumps(dict(random_master_seed=master,requested_cases=count)))
    for index in (range(count) if indices is None else indices):
        seed=case_seed(master,index);config=None;out=None
        try:
            config=make_case(master,index)
            out,features=exercise(config)
            row=dict(case_index=index,case_seed=seed,config_digest=digest(config),result_digest=digest(out),features=features)
        except Exception as error:
            directory=ROOT/'runs'/('random_failure_'+uuid.uuid4().hex)
            directory.mkdir(parents=True,exist_ok=False)
            (directory/'config.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
            (directory/'error.txt').write_text(traceback.format_exc(),encoding='utf-8')
            if getattr(error,'random_prefix',None) is not None:
                (directory/'prefix.json').write_text(json.dumps(error.random_prefix,indent=2,default=str),encoding='utf-8')
            elif out is not None:
                (directory/'prefix.json').write_text(json.dumps(out,indent=2,default=str),encoding='utf-8')
            metadata=dict(master_seed=master,case_index=index,case_seed=seed,requested_cases=count,completed_cases=len(rows),
                          reproduce=f'python scripts/verify_random.py --seed {master} --case-index {index}')
            (directory/'failure.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
            emit(json.dumps(dict(random_failure=metadata,artifacts=str(directory))))
            raise
        rows.append(row);emit(json.dumps(dict(random_case=row),sort_keys=True))
    return dict(master_seed=master,requested_cases=count,passed=len(rows),failed=0,cases=rows,
                selected_indices=indices,sequence_digest=digest(rows),seconds=time.monotonic()-started)
