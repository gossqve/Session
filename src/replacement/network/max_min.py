"""Unweighted, exact progressive filling across complete directed paths."""
from fractions import Fraction
from ..core.entities import number


def _rational(value):
    if isinstance(value, Fraction):
        if value < 0:raise ValueError('Rate/capacity must be nonnegative')
        return value
    number(value)
    return Fraction(str(value))


class MaxMinAllocator:
    """Stateless environment mechanism; limits are demand caps, never weights.

    Frozen flows continue consuming every link on their path. Each iteration
    freezes at least one flow, giving at most F iterations and O(F² L) work
    in this deliberately small-network implementation. No tolerance or float
    subtraction is used at capacity boundaries.
    """
    def allocate(self, active_flows, topology):
        paths = {}
        limits = {}
        for flow in sorted(active_flows, key=lambda f:f.flow_id):
            links = tuple(flow.path.link_ids)
            if flow.flow_id in paths:raise ValueError('Duplicate Flow ID')
            if not links or len(set(links)) != len(links) or any(l not in topology.links for l in links):
                raise ValueError('Flow requires a nonempty legal directed path')
            paths[flow.flow_id] = links
            limit = getattr(flow, 'rate_limit_bps', None)
            if limit is not None:limits[flow.flow_id] = _rational(limit)
        capacities = {l:_rational(topology.links[l].capacity_bps) for p in paths.values() for l in p}
        users = {l:tuple(f for f,p in paths.items() if l in p) for l in capacities}
        rates = {f:Fraction(0) for f in paths}
        unfrozen = set(paths)
        while unfrozen:
            # Subtract ALL allocated rates, including previously frozen flows.
            residual = {l:cap-sum((rates[f] for f in users[l]), Fraction(0)) for l,cap in capacities.items()}
            counts = {l:sum(f in unfrozen for f in users[l]) for l in capacities}
            candidates = [residual[l]/n for l,n in counts.items() if n]
            candidates.extend(limits[f]-rates[f] for f in unfrozen if f in limits)
            delta = min(candidates)
            if delta < 0:raise RuntimeError('Negative progressive-filling residual')
            for f in unfrozen:rates[f] += delta
            saturated = {l for l,n in counts.items() if n and residual[l] == n*delta}
            frozen = {f for f in unfrozen if any(l in saturated for l in paths[f])
                      or (f in limits and rates[f] == limits[f])}
            if not frozen:raise RuntimeError('Progressive filling made no progress')
            unfrozen.difference_update(frozen)
        return rates
