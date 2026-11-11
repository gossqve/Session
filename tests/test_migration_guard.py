"""Single-inflight admission is not an implementation of Copy or Cutover."""
from dataclasses import FrozenInstanceError
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from replacement.simulation.migration_guard import MigrationAdmissionGuard


class MigrationGuardTests(unittest.TestCase):
    def test_duplicate_rejected_and_target_is_fixed(self):
        guard = MigrationAdmissionGuard()
        lease = guard.try_begin("S1", "E1", "E2")
        self.assertIsNotNone(lease)
        self.assertIsNone(guard.try_begin("S1", "E1", "E3"))
        self.assertEqual(guard.rejected_duplicate_count, 1)
        self.assertIs(guard.active["S1"], lease)
        with self.assertRaises(FrozenInstanceError): lease.target_edge_id = "E3"

    def test_complete_releases_without_automatic_catchup(self):
        guard = MigrationAdmissionGuard(); lease = guard.try_begin("S1", "E1", "E2")
        guard.try_begin("S1", "E1", "E3")
        guard.complete(lease)
        self.assertEqual(dict(guard.active), {})
        self.assertEqual([e["event"] for e in guard.events], ["admitted", "duplicate_rejected", "completed"])
        later = guard.try_begin("S1", "E2", "E3")
        self.assertNotEqual(later.operation_id, lease.operation_id)
        with self.assertRaises(ValueError): guard.complete(lease)
        self.assertIs(guard.active["S1"], later)

    def test_fail_releases_and_other_sessions_are_independent(self):
        guard = MigrationAdmissionGuard()
        a = guard.try_begin("S1", "E1", "E2"); b = guard.try_begin("S2", "E2", "E3")
        guard.fail(a, "transport_failure")
        self.assertEqual(dict(guard.active), {"S2": b})
        with self.assertRaises(TypeError): guard.active["S3"] = a
        self.assertFalse(hasattr(guard, "cancel"))

    def test_invalid_noop_and_foreign_lease_rejected(self):
        a, b = MigrationAdmissionGuard(), MigrationAdmissionGuard()
        lease = a.try_begin("S1", "E1", "E2")
        other = b.try_begin("S1", "E1", "E2")
        with self.assertRaises(ValueError): a.complete(other)
        self.assertIs(a.active["S1"], lease)
        for args in [("", "E1", "E2"), ("S", "E1", "E1")]:
            with self.assertRaises(ValueError): a.try_begin(*args)
