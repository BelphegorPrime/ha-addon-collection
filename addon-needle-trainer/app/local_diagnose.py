"""Explain a saved six-language Needle evaluation without running inference.

Completely offline and read-only with respect to trained models. Any threshold
sweep is a *counterfactual* over the stored raw_action/confidence pairs and
DOES NOT simulate the full HA safety gate or authorize changing it.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

WORK = Path("/share/needle-training")
THRESHOLDS = (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
# Transparent *dataset-specific* categories, not execution rules.
KNOWN_HELDOUT_CATEGORIES = {
    "p18": "unsupported_target_in_wrong_tool_family",
    "l06": "hypothetical_question",
    "t06": "explicit_prohibition",
}


def category(case: dict) -> str:
    return KNOWN_HELDOUT_CATEGORIES.get(case["scenario_id"], "other")


def _validate_report(report: dict) -> list[dict]:
    if report.get("format") != 1 or report.get("purpose") != "read_only_held_out_never_deploy":
        raise ValueError("Not an evaluate_local report")
    if report.get("dataset", {}).get("cases") != 36:
        raise ValueError("Only the 36-case held-out report is supported")
    base = report.get("baseline", {}).get("cases")
    candidate = report.get("candidate", {}).get("cases")
    if not isinstance(base, list) or not isinstance(candidate, list):
        raise ValueError("Missing raw evaluation cases")
    keys = {}
    for kind, cases in (("baseline", base), ("candidate", candidate)):
        seen = set()
        for case in cases:
            if not isinstance(case, dict):
                raise ValueError("Malformed case")
            key = (case.get("scenario_id"), case.get("locale"))
            if (not all(isinstance(item, str) for item in key)
                or key in seen
                or case.get("expected") is not None and not isinstance(case["expected"], str)):
                raise ValueError("Duplicate or malformed case identifiers")
            seen.add(key)
        if len(cases) != 36:
            raise ValueError("Missing benchmark cases")
        keys[kind] = seen
    if keys["baseline"] != keys["candidate"]:
        raise ValueError("Base/candidate case mismatch")
    return candidate


def _score(cases: list[dict], threshold: float) -> dict:
    correct = unsafe = missing_valid = safe_rejection = 0
    for x in cases:
        if x.get("error") is not None:
            raise ValueError("Incomplete native inference; no threshold sweep possible")
        confidence = x.get("confidence")
        if type(confidence) not in (int, float) or not math.isfinite(confidence):
            raise ValueError("Missing or nonfinite native confidence")
        if not 0 <= confidence <= 1:
            raise ValueError("Invalid native confidence")
        predicted = x.get("raw_action")
        accepted = predicted if predicted is not None and confidence >= threshold else None
        if accepted is not None and not isinstance(accepted, str):
            raise ValueError("Invalid raw action")
        expected = x["expected"]
        correct += accepted is not None and accepted == expected
        unsafe += accepted is not None and accepted != expected
        missing_valid += accepted is None and expected is not None
        safe_rejection += accepted is None and expected is None
    return {
        "threshold": threshold,
        "correct_approvals": correct,
        "unsafe_approvals": unsafe,
        "missed_valid": missing_valid,
        "correct_rejections": safe_rejection,
    }


def _aggregate(cases: list[dict]) -> dict:
    result = Counter()
    for x in cases:
        expected, raw = x["expected"], x.get("raw_action")
        result["cases"] += 1
        result["correct_generated"] += expected is not None and raw == expected
        result["wrong_generated_action"] += raw is not None and raw != expected
        result["no_action_correct"] += expected is None and raw is None
        result["expected_action_missing"] += expected is not None and raw is None
    return dict(result)


def diagnose(report: dict) -> dict:
    rows = _validate_report(report)
    by_scenario = defaultdict(list)
    by_category = defaultdict(list)
    by_locale = defaultdict(list)
    by_family = defaultdict(list)
    by_risk = defaultdict(list)
    for case in rows:
        by_scenario[case["scenario_id"]].append(case)
        by_category[category(case)].append(case)
        by_locale[case["locale"]].append(case)
        by_family[case["family"]].append(case)
        by_risk[case["risk"]].append(case)

    return {
        "format": 1,
        "derived_from": "evaluation/test-report.json",
        "candidate_sha256": report["candidate"]["weights_sha256"],
        "limitations": [
            "Counterfactual threshold sweep uses stored native combined confidence and raw_action only",
            "It intentionally DOES NOT recompute Needle suppression, grounding or the full Home Assistant route validator",
            "No threshold in this report is authorization for production use",
            "Separate JAX head-only scores cannot be subtracted from native combined confidence to derive decode probabilities",
            "No held-out test utterances were added to training",
        ],
        "native_generation": {
            "overall": _aggregate(rows),
            "by_scenario": {k: _aggregate(v) for k, v in sorted(by_scenario.items())},
            "by_category": {k: _aggregate(v) for k, v in sorted(by_category.items())},
            "by_locale": {k: _aggregate(v) for k, v in sorted(by_locale.items())},
            "by_family": {k: _aggregate(v) for k, v in sorted(by_family.items())},
            "by_risk": {k: _aggregate(v) for k, v in sorted(by_risk.items())},
        },
        "counterfactual_threshold_sweep": [_score(rows, gate) for gate in THRESHOLDS],
        "safety": {"verdict": "NOT_APPROVED",
                   "reason": "Observed unsafe candidate generations and no validated safe deployment gate"},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path, nargs="?", default=WORK)
    args = parser.parse_args(argv)
    source = args.work / "evaluation" / "test-report.json"
    if not source.is_file():
        raise FileNotFoundError(source)
    result = diagnose(json.loads(source.read_text(encoding="utf-8")))
    destination = args.work / "evaluation" / "diagnosis.json"
    from local_evaluate import write_report
    write_report(destination, result)
    print(json.dumps({
        "report": str(destination),
        "generation": result["native_generation"],
        "threshold_sweep": result["counterfactual_threshold_sweep"],
        "safety": result["safety"],
    }, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
