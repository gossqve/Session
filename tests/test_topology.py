"""S2-A model-derived positive/negative topology acceptance."""
import copy
from dataclasses import FrozenInstanceError, asdict
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from replacement.core.entities import EdgeState
from replacement.simulation.events import EventQueue
from replacement.network.entities import Area, DirectedLink, FixedPath
from replacement.network.topology import NetworkTopology


def fixture():
    q = EventQueue()
    areas = [Area("A", "gA"), Area("B", "gB"), Area("C", "gC")]
    edges = [EdgeState(name, 10, 1, 100, frozenset(), q, area_id=area)
             for name, area in [("E1", "A"), ("E2", "A"), ("E3", "B"), ("E4", "B"), ("E5", "C"), ("E6", "C")]]
    links = [DirectedLink("12", "E1", "E2", 100), DirectedLink("21", "E2", "E1", 80),
             DirectedLink("1a", "E1", "gA", 90), DirectedLink("ab", "gA", "gB", 70),
             DirectedLink("b3", "gB", "E3", 60), DirectedLink("3b", "E3", "gB", 50),
             DirectedLink("ba", "gB", "gA", 40), DirectedLink("a1", "gA", "E1", 30),
             DirectedLink("ac", "gA", "gC", 20), DirectedLink("cb", "gC", "gB", 10)]
    paths = [FixedPath("p12", "E1", "E2", ("12",)), FixedPath("p21", "E2", "E1", ("21",)),
             FixedPath("p13", "E1", "E3", ("1a", "ab", "b3")), FixedPath("p31", "E3", "E1", ("3b", "ba", "a1"))]
    return dict(areas=areas, edges=edges, links=links, paths=paths,
                allowed_serving_pairs=[("E1", "E3"), ("E2", "E2")],
                mobility_adjacency={"E1": ["E2", "E3"]}, mobility_transitions=[("E1", "E2"), ("E1", "E3")])


class TopologyTests(unittest.TestCase):
    def test_registered_objects_and_area_index_reuse_existing_edges(self):
        f = fixture(); t = NetworkTopology(**f)
        self.assertIs(t.edges["E1"], f["edges"][0])
        self.assertEqual(t.edges_in_area("A"), ("E1", "E2"))
        self.assertEqual(t.node_area("gB"), "B")
        self.assertNotIn("gA", t.edges)
        self.assertEqual(len(t.areas), 3)

    def test_full_duplex_capacity_is_independent(self):
        t = NetworkTopology(**fixture())
        self.assertEqual((t.links["12"].capacity_bps, t.links["21"].capacity_bps), (100, 80))
        self.assertEqual(t.get_path("E3", "E1").link_ids, ("3b", "ba", "a1"))

    def test_bad_capacities_rejected(self):
        for capacity in (0, -1, float("nan"), float("inf"), True, "10"):
            with self.subTest(capacity=capacity), self.assertRaises(ValueError):
                DirectedLink("bad", "E1", "E2", capacity)

    def test_duplicate_link_and_unknown_endpoint_rejected(self):
        for link in (DirectedLink("12", "E1", "E2", 1), DirectedLink("bad", "E1", "unknown", 1)):
            f = fixture(); f["links"].append(link)
            with self.assertRaises(ValueError): NetworkTopology(**f)

    def test_duplicate_area_boundary_edge_path_and_pair_rejected(self):
        for field, value in (("areas", Area("A", "new")), ("areas", Area("new", "gA")),
                             ("areas", Area("new", "E1")), ("edges", fixture()["edges"][0]),
                             ("paths", FixedPath("p12", "E2", "E1", ("21",))),
                             ("paths", FixedPath("other", "E1", "E2", ("12",)))):
            f = fixture(); f[field].append(value)
            with self.subTest(field=field), self.assertRaises(ValueError): NetworkTopology(**f)

    def test_s2_requires_explicit_existing_area_s1_still_allows_none(self):
        for area in (None, "missing"):
            f=fixture();f["edges"] = [EdgeState("bad",10,1,1,frozenset(),EventQueue(),area_id=area)]
            with self.assertRaises(ValueError): NetworkTopology(**f)
        self.assertIsNone(EdgeState("old",10,1,1,frozenset(),EventQueue()).area_id)

    def test_single_and_multilink_fixed_paths(self):
        t=NetworkTopology(**fixture())
        self.assertEqual(t.get_path("E1","E2").link_ids,("12",))
        self.assertEqual(t.get_path("E1","E3").link_ids,("1a","ab","b3"))
        self.assertEqual(t.validate_access_execution("E1","E3"), (t.get_path("E1","E3"),t.get_path("E3","E1")))

    def test_bad_path_order_start_end_missing_link_and_direction(self):
        for path in (FixedPath("bad","E1","E3",("ab","1a","b3")),
                     FixedPath("bad","E2","E3",("1a","ab","b3")),
                     FixedPath("bad","E1","E4",("1a","ab","b3")),
                     FixedPath("bad","E2","E1",("missing",)),
                     FixedPath("bad","E2","E1",("12",)),
                     FixedPath("bad","E1","E2",())):
            f=fixture();f["paths"].append(path)
            with self.subTest(path=path), self.assertRaises(ValueError): NetworkTopology(**f)

    def test_third_area_transit_rejected(self):
        f=fixture();f["paths"]=[FixedPath("bad","E1","E3",("1a","ac","cb","b3"))]
        with self.assertRaises(ValueError): NetworkTopology(**f)

    def test_direct_cross_edge_and_wrong_area_exit_links_rejected(self):
        for link in (DirectedLink("bad","E1","E3",1), DirectedLink("bad","E1","gB",1)):
            f=fixture();f["links"].append(link)
            with self.assertRaises(ValueError): NetworkTopology(**f)

    def test_missing_entry_or_exit_rejected(self):
        for ids in (("ab","b3"),("1a","ab")):
            f=fixture();f["paths"][2]=FixedPath("p13","E1","E3",ids)
            with self.assertRaises(ValueError): NetworkTopology(**f)

    def test_same_edge_local_empty_and_boundary_not_service(self):
        t=NetworkTopology(**fixture())
        self.assertEqual(t.get_path("E4","E4").link_ids,())
        self.assertEqual(t.validate_access_execution("E4","E4")[0].source_node,"E4")
        with self.assertRaises(ValueError): t.validate_access_execution("gA","E1")

    def test_same_area_missing_path_not_free_even_with_links(self):
        f=fixture();f["paths"]=f["paths"][1:];f["mobility_transitions"]=[]
        t=NetworkTopology(**f)
        with self.assertRaises(ValueError): t.get_path("E1","E2")

    def test_no_automatic_reverse_path_or_link(self):
        for remove in ("p13","p31"):
            f=fixture();f["paths"]=[p for p in f["paths"] if p.path_id!=remove]
            with self.assertRaises(ValueError): NetworkTopology(**f)
        f=fixture();f["links"]=[l for l in f["links"] if l.link_id!="ba"]
        with self.assertRaises(ValueError): NetworkTopology(**f)

    def test_only_declared_serving_pairs_prechecked(self):
        t=NetworkTopology(**fixture())
        with self.assertRaises(ValueError): t.validate_access_execution("E1","E6")
        self.assertEqual(t.validate_serving_pairs(), (("E1","E3"),("E2","E2")))

    def test_mobility_adjacency_and_wire_paths_are_independent(self):
        f=fixture();f["mobility_adjacency"]={"E1":["E2"]}
        with self.assertRaises(ValueError): NetworkTopology(**f)
        f=fixture();f["mobility_transitions"].append(("E1","E6"));f["mobility_adjacency"]["E1"].append("E6")
        with self.assertRaises(ValueError): NetworkTopology(**f)

    def test_mobility_uses_old_to_new_direction_not_reverse(self):
        f=fixture();f["paths"]=[p for p in f["paths"] if p.path_id!="p12"]
        with self.assertRaises(ValueError): NetworkTopology(**f)

    def test_every_transition_checked_self_transition_needs_no_wire(self):
        f=fixture();f["mobility_transitions"].append(("E4","E4"))
        t=NetworkTopology(**f)
        self.assertEqual(len(t.validate_mobility_transitions()),3)
        f["mobility_transitions"].append(("E6","unknown"))
        with self.assertRaises(ValueError): NetworkTopology(**f)

    def test_static_entities_and_registries_are_detached_readonly(self):
        f=fixture();t=NetworkTopology(**f);f["paths"].clear();f["mobility_adjacency"]["E1"].clear()
        self.assertEqual(t.get_path("E1","E2").link_ids,("12",))
        self.assertEqual(t.validate_mobility_transitions(),(("E1","E2"),("E1","E3")))
        with self.assertRaises(TypeError):t.links["x"]=t.links["12"]
        with self.assertRaises(FrozenInstanceError):t.links["12"].capacity_bps=2

    def test_config_load_demo_determinism_and_no_s1_side_effects(self):
        from replacement.demos.topology_demo import run_demo
        from replacement.simulation.serving import ServingSimulator
        from test_serving import config
        c=json.loads(Path("configs/s2a_topology_smoke.json").read_text(encoding="utf8"))
        sim=ServingSimulator(config());sim.advance_to(0.25);before=sim.observation();events=copy.deepcopy(sim.events)
        a=run_demo(c);b=run_demo(copy.deepcopy(c))
        self.assertEqual(a,b);self.assertEqual(a["summary"]["areas"],3);self.assertEqual(a["summary"]["edges"],6)
        self.assertEqual(sim.observation(),before);self.assertEqual(sim.events,events)
        t=NetworkTopology.from_config(c, edges=fixture()["edges"])
        self.assertEqual(t.get_path("E1","E3").link_ids, ("E1-out","A-B","E3-in"))
        self.assertNotIn("workload", vars(t));self.assertNotIn("queue", vars(t));self.assertNotIn("flows", vars(t))
