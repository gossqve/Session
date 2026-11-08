"""S2-B disjoint-link allocator, replaceable by S2-C progressive filling."""
class S2CRequired(NotImplementedError):
    """Shared directed-link competition needs the S2-C allocator."""


class DisjointPathAllocator:
    def allocate(self, active_flows, topology):
        occupied = set()
        rates = {}
        for flow in sorted(active_flows, key=lambda f: f.flow_id):
            links = set(flow.path.link_ids)
            shared = occupied & links
            if shared:
                raise S2CRequired(f'S2-C required: shared directed links {sorted(shared)}')
            occupied.update(links)
            rates[flow.flow_id] = min(topology.links[l].capacity_bps for l in links)
        return rates
