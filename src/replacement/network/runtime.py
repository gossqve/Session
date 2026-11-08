"""Exact fluid byte kernel driven exclusively by the caller's EventQueue.

Times are decimal Fractions internally. Forecasts round UP to the shared
queue's 1 ps grid; progress never rounds positive pending bytes to zero.
"""
from copy import deepcopy
from dataclasses import dataclass, field, replace
from fractions import Fraction
from types import MappingProxyType
from ..core.entities import identifier, integer, number
from .flow import Flow, FlowStatus, FlowType, TokenBoundary, TransferNotice
from .max_min import MaxMinAllocator
from .entities import FixedPath


def _exact(value):
    return Fraction(str(value))


@dataclass
class _Record:
    view: Flow
    boundaries: list = field(default_factory=list)
    override: float | None = None
    forecast: float | None = None


class NetworkRuntime:
    _flow_types = frozenset(FlowType) - {FlowType.UPLOAD,FlowType.DOWNLOAD}

    def __init__(self, queue, topology, allocator=None, event_kind='network_completion'):
        self.queue = queue
        self.topology = topology
        self.allocator = allocator if allocator is not None else MaxMinAllocator()
        self.event_kind = event_kind
        self._records = {}
        self._time = Fraction(0)
        # Never roll this counter back: predictions enqueued by an aborted
        # transaction must not alias a later prediction after state recovery.
        self._version = 0
        self.trace = []

    @property
    def time_s(self):
        return float(self._time)

    @property
    def flows(self):
        return MappingProxyType({k: self._snapshot(r) for k,r in self._records.items()})

    def _snapshot(self, r):
        return replace(r.view, token_boundaries=tuple(r.boundaries), rate_limit_bps=r.override)

    def _record(self, flow_id):
        if flow_id not in self._records:
            raise ValueError(f'Unknown Flow: {flow_id}')
        return self._records[flow_id]

    def _audit(self, r, kind):
        f = self._snapshot(r)
        self.trace.append(dict(time_s=self.time_s, kind=kind, flow_id=f.flow_id,
            session_id=f.session_id, turn_index=f.turn_index, flow_type=f.flow_type.value,
            path_id=f.path_id, link_ids=f.link_ids, ready_bytes=f.ready_bytes,
            transferred_bytes=float(f.transferred_bytes), pending_bytes=float(f.pending_bytes),
            producer_closed=f.producer_closed, status=f.status.value, rate_bps=float(f.rate_bps)))

    def _path(self, path, rate_bps):
        if not isinstance(path,FixedPath) or not path.link_ids or self.topology.paths.get(path.path_id) != path:
            raise ValueError('Wired Flow requires a registered nonempty fixed path')
        if rate_bps is not None:
            number(rate_bps)
            if rate_bps > min(self.topology.links[l].capacity_bps for l in path.link_ids):
                raise ValueError('Rate exceeds fixed-path capacity')
        return self.topology.paths[path.path_id]

    def create(self, flow_id, flow_type, session_id, turn_index, time_s, *, path=None,
               rate_bps=None, operation_id=None):
        for value in (flow_id,session_id):identifier(value)
        if flow_id in self._records:raise ValueError('Duplicate Flow ID')
        if operation_id is not None:identifier(operation_id)
        if turn_index is not None:integer(turn_index, minimum=0)
        flow_type = FlowType(flow_type)
        if flow_type not in self._flow_types:raise ValueError('Flow type does not belong to this transport domain')
        path = self._path(path, rate_bps)
        notices = self.advance(time_s)
        f=Flow(flow_id,flow_type,session_id,turn_index,operation_id,path,0,Fraction(0),False,
               FlowStatus.CREATED,self.time_s,None,self.time_s,None,None,0,0,())
        self._records[flow_id]=_Record(f, override=rate_bps)
        self._audit(self._records[flow_id], 'created')
        return notices

    def _change(self, flow_id, time_s, kind, change):
        self._record(flow_id)
        saved=deepcopy(self._records)
        saved_time=self._time
        trace_len=len(self.trace)
        try:
            notices=list(self.advance(time_s))
            r=self._record(flow_id)
            change(r)
            notices.extend(self._settle_boundaries())
            self._allocate(kind)
        except Exception:
            self._records=saved
            self._time=saved_time
            del self.trace[trace_len:]
            raise
        self._audit(self._record(flow_id),kind)
        self._predict()
        return tuple(notices)

    def start(self, flow_id, time_s):
        def change(r):
            f=r.view
            if f.cancelled_at is not None:raise ValueError('Cancelled Flow cannot start')
            if f.started_at is None:r.view=replace(f,started_at=self.time_s)
        return self._change(flow_id,time_s,'started',change)

    def supply(self, flow_id, byte_count, time_s, *, token_id=None):
        integer(byte_count,minimum=0)
        if token_id is not None:
            if isinstance(token_id,tuple) and len(token_id)==3:
                identifier(token_id[0]);integer(token_id[1],minimum=0);integer(token_id[2])
            else:identifier(token_id)
        def change(r):
            f=r.view
            if f.producer_closed or f.cancelled_at is not None:raise ValueError('Flow producer is closed/cancelled')
            if token_id is not None and any(b.token_id==token_id for b in r.boundaries):
                raise ValueError('Duplicate Token identity within Flow')
            r.view=replace(f,ready_bytes=f.ready_bytes+byte_count)
            if token_id is not None:r.boundaries.append(TokenBoundary(token_id,r.view.ready_bytes))
        return self._change(flow_id,time_s,'supplied',change)

    def close(self, flow_id, time_s):
        def change(r):r.view=replace(r.view,producer_closed=True)
        return self._change(flow_id,time_s,'producer_closed',change)

    def cancel(self, flow_id, time_s):
        def change(r):
            f=r.view
            if f.completed_at is None and f.cancelled_at is None:
                r.view=replace(f,cancelled_at=self.time_s,status=FlowStatus.CANCELLED,rate_bps=0)
        return self._change(flow_id,time_s,'cancelled',change)

    def set_rate(self, flow_id, rate_bps, time_s):
        number(rate_bps)
        def change(r):
            self._path(r.view.path,rate_bps)
            r.override=rate_bps
        return self._change(flow_id,time_s,'rate_updated',change)

    def _eligible(self, r):
        f=r.view
        return f.started_at is not None and f.cancelled_at is None and f.completed_at is None and f.pending_bytes>0

    def _rates(self, active):
        rates=self.allocator.allocate(tuple(self._snapshot(r) for r in active),self.topology)
        if set(rates)!={r.view.flow_id for r in active}:raise ValueError('Allocator must return exactly active Flow rates')
        result={}
        for r in active:
            rate=rates[r.view.flow_id]
            if isinstance(rate,Fraction):
                if rate<0:raise ValueError('Allocator rate must be nonnegative')
            else:number(rate)
            result[r.view.flow_id]=rate if r.override is None else min(rate,r.override)
        loads={l:Fraction(0) for l in self.topology.links}
        for r in active:
            for l in r.view.link_ids:loads[l]+=_exact(result[r.view.flow_id])
        if any(loads[l]>_exact(link.capacity_bps) for l,link in self.topology.links.items()):
            raise ValueError('Allocator exceeds directed-link capacity')
        return result

    def _allocate(self, reason='advance'):
        before={f:r.view.rate_bps for f,r in self._records.items()}
        active=[r for r in self._records.values() if self._eligible(r) and r.override != 0]
        rates=self._rates(active)
        for r in self._records.values():
            f=r.view
            rate=rates.get(f.flow_id,0)
            if f.cancelled_at is not None:status=FlowStatus.CANCELLED
            elif f.completed_at is not None:status=FlowStatus.COMPLETED
            elif f.started_at is None:status=FlowStatus.CREATED
            elif f.pending_bytes==0:status=FlowStatus.WAITING_FOR_DATA
            elif rate==0:status=FlowStatus.PAUSED
            else:status=FlowStatus.ACTIVE
            r.view=replace(f,rate_bps=rate,status=status)
            if f.rate_bps!=rate or f.status!=status:self._audit(r,'state_changed')
        for r in self._records.values():
            if not 0<=r.view.transferred_bytes<=r.view.ready_bytes:
                raise RuntimeError('Flow byte conservation violated')
        # Wireless inherits the byte kernel but has independent per-user rates.
        if self.topology is not None:self._audit_allocation(active,before,reason)

    def _audit_allocation(self, active, before, reason):
        participants=sorted(r.view.flow_id for r in active)
        flows={}
        loads={l:Fraction(0) for l in self.topology.links}
        for fid,r in sorted(self._records.items()):
            f=self._snapshot(r)
            for l in f.link_ids:loads[l]+=_exact(f.rate_bps)
            flows[fid]=dict(path_id=f.path_id,link_ids=f.link_ids,
                before_rate_bps=float(before[fid]),rate_bps=float(f.rate_bps),
                ready_bytes=f.ready_bytes,transferred_bytes=float(f.transferred_bytes),
                pending_bytes=float(f.pending_bytes),status=f.status.value,
                rate_limit_bps=f.rate_limit_bps)
        links={}
        for lid,link in self.topology.links.items():
            capacity=_exact(link.capacity_bps);load=loads[lid]
            if not 0<=load<=capacity:raise RuntimeError('Directed-link capacity violated')
            links[lid]=dict(capacity_bps=float(capacity),load_bps=float(load),
                residual_bps=float(capacity-load),utilization=float(load/capacity),
                saturated=load==capacity)
        self.trace.append(dict(time_s=self.time_s,kind='allocation',reason=reason,
            participants=participants,active_flow_ids=participants,flows=flows,links=links,
            rates_bps={fid:row['rate_bps'] for fid,row in flows.items()},
            link_loads_bps={lid:row['load_bps'] for lid,row in links.items()}))

    def _settle_boundaries(self):
        notices=[]
        for r in sorted(self._records.values(),key=lambda r:r.view.flow_id):
            f=r.view
            if f.started_at is None or f.cancelled_at is not None:continue
            for i,b in enumerate(r.boundaries):
                if b.arrived_at is None and f.transferred_bytes>=b.cumulative_bytes:
                    r.boundaries[i]=replace(b,arrived_at=self.time_s)
                    notices.append(TransferNotice(f.flow_id,'token_arrived',self.time_s,b.token_id))
                    self.trace.append(dict(time_s=self.time_s,kind='token_arrived',flow_id=f.flow_id,
                                           token_id=b.token_id,cumulative_bytes=b.cumulative_bytes))
            if f.producer_closed and f.pending_bytes==0 and f.completed_at is None:
                r.view=replace(f,completed_at=self.time_s,status=FlowStatus.COMPLETED,rate_bps=0)
                notices.append(TransferNotice(f.flow_id,'completed',self.time_s))
                self._audit(r,'completed')
        return notices

    def _predict(self):
        for r in self._records.values():
            f=r.view
            self._version+=1
            r.view=replace(f,event_version=self._version)
            r.forecast=None
            if not self._eligible(r) or f.rate_bps==0:continue
            boundary=next((b.cumulative_bytes for b in r.boundaries if b.arrived_at is None),f.ready_bytes)
            remaining=boundary-f.transferred_bytes
            if remaining<=0:raise RuntimeError('Unsettled byte boundary')
            target=self._time+remaining*8/_exact(f.rate_bps)
            ticks=-(-(target*10**12).numerator//(target*10**12).denominator)
            when=float(Fraction(ticks,10**12))
            if _exact(when)<target or when<=self.time_s:
                import math
                when=math.nextafter(max(when,self.time_s),float('inf'))
            if round(when,12)<=self.time_s:
                raise ValueError('Clock magnitude cannot represent positive transfer duration')
            r.forecast=round(when,12)
            self.queue.schedule(when,self.event_kind,flow_id=f.flow_id,version=r.view.event_version)

    def advance(self, time_s):
        number(time_s)
        target=_exact(time_s)
        if target<self._time:raise ValueError('Transport time cannot move backwards')
        forecasts=[r.forecast for r in self._records.values() if r.forecast is not None]
        if forecasts and target>_exact(min(forecasts)):
            raise ValueError('Cannot skip next transport boundary; dispatch shared EventQueue')
        delta=target-self._time
        self._time=target
        for r in self._records.values():
            f=r.view
            amount=min(f.pending_bytes,_exact(f.rate_bps)*delta/8) if self._eligible(r) else 0
            r.view=replace(f,transferred_bytes=f.transferred_bytes+amount,last_update_at=self.time_s)
            if amount:self._audit(r,'progress')
        notices=self._settle_boundaries()
        self._allocate('boundary' if notices else 'advance')
        self._predict()
        return tuple(notices)

    def is_current_event(self,event):
        if event.kind!=self.event_kind:return False
        r=self._records.get(event.payload.get('flow_id'))
        return r is not None and r.forecast==event.time and r.view.event_version==event.payload.get('version')

    def handle_event(self,event):
        return self.advance(event.time) if self.is_current_event(event) else ()
