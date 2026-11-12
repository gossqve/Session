"""Offline Section III.E evaluation derived from the unique Serving records.

No runtime references, future plan queries, scheduling, or mutable resource ledger.
The existing summary and per-resource traces remain the authoritative inputs.
G1 uses normal completed Turns, including legal zero-output completion. The
legacy all-planned mean is retained only as a diagnostic, never as G1.
"""
import math


def evaluate_serving(result):
    summary=result['summary']
    sessions={s['session_id']:s for s in result['sessions']}
    unfinished=[]
    for turn in result['turns']:
        if turn['status']=='completed':
            continue
        session=sessions[turn['session_id']]
        censored=session['end_time'] is None
        reason=turn['reason']
        if reason is None:
            reason=('InputUpload' if turn['prompt_arrived_at'] is None else
                    'Computing' if turn['generation_ended_at'] is None else 'OutputDelivery')
        unfinished.append(dict(session_id=turn['session_id'],turn_index=turn['turn_index'],
                               submitted_at=turn['submitted_at'],status=turn['status'],reason=reason,
                               right_censored=censored,
                               right_censored_e2e_lower_bound_s=round(summary['observation_end_s']-turn['submitted_at'],12)
                               if censored else None,
                               termination_time_s=session['end_time']))
    services=[e for trace in result['gpu_events'].values() for e in trace if e['event']=='service']
    raw=dict(summary)
    completed=[t['received_at']-t['submitted_at'] for t in result['turns']
               if t['status']=='completed']
    raw.update(mean_completed_full_turn_e2e_s=round(math.fsum(completed)/len(completed),12) if completed else None,
               g1_metric='mean_completed_full_turn_e2e_s',
               g1_scope='normally completed Turns including legal zero-output; excludes unfinished and terminated Turns',
               mean_full_turn_e2e_scope='legacy all-planned complete-data diagnostic; not G1',
               unsubmitted_turns=summary['planned_turns']-summary['submitted_turns'],
               submitted_unfinished_turns=len(unfinished),
               right_censored_turns=sum(t['right_censored'] for t in unfinished),
               failed_submitted_turns=sum(not t['right_censored'] for t in unfinished),
               p95_full_turn_e2e_s=summary['completed_turn_p95_e2e_s'],
               p95_scope='normally completed Turn subset; nearest-rank, not a full-population estimate',
               gpu_busy_edge_time_s=sum(e['elapsed_s'] for e in services if e['running_count']),
               gpu_running_turn_time_s=sum(e['elapsed_s']*e['running_count'] for e in services),
               completed_sessions=sum(s['status']=='ended' for s in sessions.values()),
               terminated_sessions=sum(s['status']=='failed' for s in sessions.values()),
               unfinished_sessions=sum(s['end_time'] is None for s in sessions.values()))
    def byte_sum(rows,kind):
        return sum(float(f['transferred_bytes']) for f in rows if f['flow_type']==kind)
    transport=dict(original_prompt_bytes=byte_sum(result['network_flows'],'prompt'),
                   original_response_bytes=byte_sum(result['network_flows'],'response'),
                   handover_forward_bytes=byte_sum(result['network_flows'],'handover'),
                   wireless_upload_bytes=byte_sum(result['wireless_transfers'],'upload'),
                   wireless_download_bytes=byte_sum(result['wireless_transfers'],'download'),
                   ue_delivered_response_bytes=sum(t['text_bytes'] for t in result['output_tokens'] if t['delivered']))
    return dict(summary=raw,transport=transport,unfinished_turns=unfinished,
                active_turn_censoring_lower_bounds=[dict(session_id=t['session_id'],turn_index=t['turn_index'],
                    lower_bound_s=t['right_censored_e2e_lower_bound_s']) for t in unfinished if t['right_censored']],
                terminated_turns=[dict(t) for t in unfinished if not t['right_censored']],
                generated_tokens=len(result['output_tokens']),
                delivered_tokens=sum(t['delivered'] for t in result['output_tokens']),
                scope='offline current-prefix evaluation; no fabricated submission for unsubmitted Turns')
