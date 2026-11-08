"""Independent per-user wireless rates using the same byte kernel as wired."""
import math
from ..core.entities import number
from .runtime import NetworkRuntime
from .flow import FlowType


def shannon_rate_bps(bandwidth_hz, snr_linear, efficiency):
    number(bandwidth_hz,positive=True)
    number(snr_linear,positive=True)
    number(efficiency,positive=True)
    if efficiency>1:raise ValueError('Wireless efficiency must be <= 1')
    rate=efficiency*bandwidth_hz*(math.log1p(snr_linear)/math.log(2))
    number(rate,positive=True)
    return rate


def resolve_wireless_rate(network_config, direction):
    if direction not in ('up','down'):raise ValueError('Wireless direction must be up/down')
    effective=f'wireless_{direction}_bits_per_second'
    physical=f'wireless_{direction}'
    if effective in network_config and physical in network_config:
        raise ValueError('Specify either effective wireless rate or Shannon parameters')
    if effective in network_config:
        value=network_config[effective];number(value,positive=True);return value
    if physical not in network_config:raise ValueError(f'Missing wireless {direction} rate')
    row=network_config[physical]
    if not isinstance(row,dict) or set(row)!={'bandwidth_hz','snr_linear','efficiency'}:
        raise ValueError('Wireless parameters require bandwidth_hz, snr_linear, efficiency')
    return shannon_rate_bps(**row)


class WirelessRuntime(NetworkRuntime):
    _flow_types = frozenset((FlowType.UPLOAD,FlowType.DOWNLOAD))

    def __init__(self,queue,event_kind='wireless_completion'):
        super().__init__(queue,None,event_kind=event_kind)

    def _path(self,path,rate_bps):
        if path is not None:raise ValueError('Wireless transfer has no wired path')
        if rate_bps is None:raise ValueError('Wireless transfer requires an effective rate')
        number(rate_bps)
        return None

    def _rates(self,active):
        users=set()
        for r in active:
            key=(r.view.session_id,r.view.flow_type)
            if key in users:raise ValueError('Only one pending wireless transfer per Session/direction; use FIFO')
            users.add(key)
        return {r.view.flow_id:r.override for r in active}
