"""Native model auto-discovery regression tests without Home Assistant."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "rootfs" / "app"
sys.path.insert(0, str(APP))

from model_select import choose_weights, valid_approval  # noqa: E402


class DiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.share = Path(self.tmp.name)
        self.model = self.share / "approved.cact"
        self.approval = self.share / "approved.json"

    def make_approved(self) -> None:
        self.model.write_bytes(b"Cactus Needle test model\0" * 80)
        digest = hashlib.sha256(self.model.read_bytes()).hexdigest()
        self.approval.write_text(json.dumps({
            "schema_version": 1,
            "model_file": "approved.cact",
            "sha256": digest,
            "confidence_head": "verified",
            "human_reviewed": True,
            "confidence_threshold": 0.8,
            "evaluation": {
                "unsafe_approvals": 0,
                "missing_confidence": 0,
                "transport_errors": 0,
                "critical_unsafe_approvals": 0,
                "by_locale": {
                    locale: {
                        "cases": 6,
                        "unsafe_approvals": 0,
                        "missing_confidence": 0,
                        "transport_errors": 0,
                    }
                    for locale in ("de", "en", "fr", "es", "it", "nl")
                },
            },
        }), encoding="utf-8")

    def test_no_trained_weights_uses_base(self) -> None:
        self.assertIsNone(choose_weights("", True, self.share)[0])

    def test_lora_adapter_and_uncalibrated_export_are_not_auto_selected(self) -> None:
        (self.share / "needle_lora.safetensors").write_bytes(b"adapter")
        (self.share / "experimental-uncalibrated.cact").write_bytes(b"archive")
        selection, reason = choose_weights("", True, self.share)
        self.assertIsNone(selection)
        self.assertIn("no approved", reason)

    def test_valid_approved_candidate_is_detected(self) -> None:
        self.make_approved()
        path, reason = choose_weights("", True, self.share)
        self.assertEqual(path, str(self.model))
        self.assertIn("approved trained model", reason)

    def test_explicit_weights_precede_autodiscovery(self) -> None:
        self.make_approved()
        custom = self.share / "my-model.cact"
        custom.write_bytes(b"explicit")
        path, reason = choose_weights(str(custom), True, self.share)
        self.assertEqual(path, str(custom))
        self.assertEqual(reason, "explicit")

    def test_invalid_explicit_path_is_not_silently_replaced(self) -> None:
        self.make_approved()
        with self.assertRaises(ValueError):
            choose_weights("relative.cact", True, self.share)
        with self.assertRaises(FileNotFoundError):
            choose_weights("/nonexistent/custom.cact", True, self.share)

    def test_user_can_disable_auto_models(self) -> None:
        self.make_approved()
        self.assertIsNone(choose_weights("", False, self.share)[0])

    def test_hash_changed_falls_back_to_base(self) -> None:
        self.make_approved()
        self.model.write_bytes(b"tampered" * 200)
        result, reason = choose_weights("", True, self.share)
        self.assertIsNone(result)
        self.assertIn("SHA256", reason)

    def test_missing_confidence_attestation_falls_back(self) -> None:
        self.make_approved()
        data = json.loads(self.approval.read_text())
        data["confidence_head"] = "none"
        self.approval.write_text(json.dumps(data))
        self.assertIsNone(choose_weights("", True, self.share)[0])

    def test_missing_critical_locale_does_not_enable_model(self) -> None:
        self.make_approved()
        data = json.loads(self.approval.read_text())
        del data["evaluation"]["by_locale"]["de"]
        self.approval.write_text(json.dumps(data))
        self.assertIsNone(choose_weights("", True, self.share)[0])

    def test_any_unsafe_case_blocks_automatic_activation(self) -> None:
        self.make_approved()
        data = json.loads(self.approval.read_text())
        data["evaluation"]["unsafe_approvals"] = 1
        self.approval.write_text(json.dumps(data))
        self.assertIsNone(choose_weights("", True, self.share)[0])

    def test_no_attestation_blocks_auto_activation(self) -> None:
        self.model.write_bytes(b"candidate" * 200)
        self.assertIsNone(choose_weights("", True, self.share)[0])

    def test_symlinks_not_accepted(self) -> None:
        self.make_approved()
        original = self.share / "source.cact"
        self.model.rename(original)
        self.model.symlink_to(original)
        self.assertIsNone(choose_weights("", True, self.share)[0])

    def test_invalid_approval_is_false(self) -> None:
        self.assertFalse(valid_approval(None))
        self.assertFalse(valid_approval({}))


if __name__ == "__main__":
    unittest.main()
