"""Replay an identifier-convention case against the verified upstream release."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from src.experience_manager.boundary_memory import BoundaryMemory
from src.experience_manager.convention_router import ConventionRouter, values
from src.experience_manager.verified_conventions import VerifiedConventions


def decision(lock, inputs, skip_id=None, learn=True):
    task = lock["task"]
    gate = ConventionRouter(task["project"], task["version"])
    for receipt, style, text, options, observed in lock["past"]:
        if receipt != skip_id:
            gate.observe(*gate.scope, receipt, style, text, options, observed)
    style = task["style"]
    engine = VerifiedConventions(style, lock["spec"], lock["history"])
    boundary = BoundaryMemory(lock["history"])
    selected = []
    for text, draft in inputs:
        candidates = values(style, text, draft, engine, boundary)
        action = gate.choose(style, text, candidates, lock["probes"], learn=learn)
        selected.append(candidates[action])
    return selected


def replay(archive, evidence):
    if hashlib.sha256(archive.read_bytes()).hexdigest() != "4efefbb0e0e1cb53e492b16bfcadc677598527e88cb9a7a0c8300b9013c4098f":
        raise ValueError("Unexpected upstream archive.")
    sys.path.insert(0, str(archive) + "/python-case-converter-1.2.0")
    from caseconverter import macrocase
    if str(archive) not in sys.modules["caseconverter"].__file__:
        raise RuntimeError("Expected the bundled original release.")
    record = json.loads(evidence.read_text("utf8"))
    lock, pairs = record["target"], record["model_cases"]
    ref = [macrocase(x) for x, _ in pairs]
    raw = [expected for _, expected in pairs]
    frozen = decision(lock, pairs, learn=False)
    rolled = decision(lock, pairs)
    withdrawn = decision(lock, pairs, skip_id=record["router_receipt_removed"])
    print("inputs:", ", ".join(x for x, _ in pairs))
    for name, vals in (("upstream reference", ref), ("input drafts", raw), ("fixed routing", frozen),
                       ("learned routing", rolled), ("one prior receipt removed", withdrawn)):
        print(f"{name:26s} {vals!r}")
    wrong_acronym = [macrocase(re.sub(r"[A-Z](?=[A-Z]+[A-Z][a-z])", "", x, count=1)) for x, _ in pairs]
    wrong_digit = [macrocase(re.sub(r"\d+", "", x)) for x, _ in pairs]
    print("two ordinary logic variants detected:", rolled != wrong_acronym, rolled != wrong_digit)
    if not (rolled == ref and frozen != ref and withdrawn != ref and rolled != wrong_acronym and rolled != wrong_digit):
        raise AssertionError("The case did not reproduce the expected differences.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=ROOT / "example.json",
                        help="Defaults to the authored teaching example included here.")
    parser.add_argument("--archive", type=Path,
                        help="Existing case-converter 1.2.0 ZIP for offline replay.")
    args = parser.parse_args()
    if args.archive:
        replay(args.archive.resolve(), args.evidence)
        return
    with TemporaryDirectory(prefix="seeda-convention-replay-") as directory:
        archive = Path(directory) / "case-converter-1.2.0.zip"
        url = "https://codeload.github.com/chrisdoherty4/python-case-converter/zip/refs/tags/v1.2.0"
        with urlopen(url, timeout=30) as response:
            archive.write_bytes(response.read())
        replay(archive, args.evidence)


if __name__ == "__main__":
    main()
