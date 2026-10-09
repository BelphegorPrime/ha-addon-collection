"""Regression tests for data isolation and post-hoc diagnostic safety."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

from local_diagnose import diagnose, _score  # noqa: E402
from runner import prepare, prepare_experiment  # noqa: E402

SOURCE = APP / "training" / "scenarios.json"
EXTRAS = APP / "training" / "augmentation_v026.json"


class Version026Tests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.work = Path(tmp.name)

    def test_augmented_data_never_overwrites_original_models_or_test(self):
        prepare(self.work, SOURCE)
        preserved = {
            f: (self.work / f).read_bytes()
            for f in ("train.jsonl", "test.jsonl", "validation.jsonl")
        }
        model = self.work / "candidate-local-confidence.cact"
        model.write_bytes(b"keep-old-model-unchanged")
        experiment = prepare_experiment(self.work, SOURCE, EXTRAS)
        self.assertEqual(experiment, self.work / "experiments" / "v026")
        for name, data in preserved.items():
            self.assertEqual((self.work / name).read_bytes(), data)
        self.assertEqual(model.read_bytes(), b"keep-old-model-unchanged")
        self.assertEqual((experiment / "test.jsonl").read_bytes(),
                         preserved["test.jsonl"])
        generated = (experiment / "train.jsonl").read_text().splitlines()
        self.assertEqual(len(generated), 312)  # 216 original + 16 x 6
        manifest = json.loads((experiment / "data_manifest.json").read_text())
        self.assertEqual(manifest["counts"], {
            "train": 312, "validation": 36, "test": 36
        })
        self.assertTrue(manifest["experiment_only"])
        with self.assertRaises(FileExistsError):
            prepare_experiment(self.work, SOURCE, EXTRAS)

    def test_root_test_tampering_blocks_staging(self):
        prepare(self.work, SOURCE)
        with (self.work / "test.jsonl").open("a") as out:
            out.write("{}\n")
        with self.assertRaisesRegex(ValueError, "held-out test differs"):
            prepare_experiment(self.work, SOURCE, EXTRAS)
        self.assertFalse((self.work / "experiments" / "v026").exists())

    def test_train_only_extras_reject_test_leakage(self):
        prepare(self.work, SOURCE)
        wrong = json.loads(EXTRAS.read_text())
        wrong["scenarios"][0]["split"] = "test"
        data = self.work / "bad-additions.json"
        data.write_text(json.dumps(wrong))
        with self.assertRaisesRegex(ValueError, "train-only"):
            prepare_experiment(self.work, SOURCE, data)

    def test_report_diagnosis_scenario_taxonomy_and_sweep(self):
        locales = ("de", "en", "fr", "es", "it", "nl")
        examples = []
        for group in ("p18", "l06", "t06", "p16", "c06", "p17"):
            for locale in locales:
                # Native output on negative cases with 0.5 confidence.
                negative = group in ("p18", "l06", "t06")
                examples.append({
                    "scenario_id": group, "locale": locale,
                    "family": "locks" if group == "l06" else "power",
                    "risk": "critical" if negative else "normal",
                    "expected": None if negative else "turn_on",
                    "raw_action": "unlock" if group == "l06" else "turn_on",
                    "confidence": .5,
                    "error": None,
                })
        report = {
            "format": 1,
            "purpose": "read_only_held_out_never_deploy",
            "dataset": {"cases": 36},
            "baseline": {"cases": examples},
            "candidate": {"cases": examples, "weights_sha256": "hash"},
        }
        analyzed = diagnose(report)
        self.assertEqual(
            analyzed["native_generation"]["by_category"][
                "hypothetical_question"]["wrong_generated_action"], 6
        )
        sweep = analyzed["counterfactual_threshold_sweep"]
        self.assertEqual(sweep[1]["unsafe_approvals"], 18)  # 0.4
        self.assertEqual(sweep[3]["unsafe_approvals"], 0)  # 0.6
        self.assertEqual(analyzed["safety"]["verdict"], "NOT_APPROVED")

    def test_incomplete_cases_cannot_be_laundered_into_clean_sweep(self):
        rows = [{"expected": None, "raw_action": None,
                 "confidence": .9, "error": "connection refused"}]
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            _score(rows, .8)


if __name__ == "__main__":
    unittest.main()
