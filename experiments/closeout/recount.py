"""Recount whole-task outcomes from the public score tables (Python 3.9+)."""
import csv
from pathlib import Path


HERE = Path(__file__).resolve().parent
ARMS = ("none", "rag", "fixed", "feedback")


def read_rows(filename):
    with (HERE / filename).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def collect(rows, key_fields, scores):
    """Make one paired comparison per task. Reject duplicated or missing arms."""
    tasks = {}
    for row in rows:
        key = tuple(row[field] for field in key_fields)
        bucket = tasks.setdefault(key, {})
        for arm, passed in scores(row).items():
            if arm not in ARMS or arm in bucket:
                raise ValueError(f"Duplicate or unknown arm for {key}: {arm}")
            bucket[arm] = bool(passed)
    for key, bucket in tasks.items():
        if set(bucket) != set(ARMS):
            raise ValueError(f"Incomplete comparison for {key}")
    return tasks


def report(label, tasks, expected_size, expected_counts):
    totals = tuple(sum(row[arm] for row in tasks.values()) for arm in ARMS)
    if len(tasks) != expected_size or totals != expected_counts:
        raise ValueError(f"{label}: found {len(tasks)} tasks, counts {totals}")
    print(f"{label:<30} {len(tasks):>4}   " + "   ".join(f"{n:>3}" for n in totals))


def whole_naming(row):
    is_feature = row["kind"] == "feature"
    correct = int(row["matched_outputs"]) == (12 if is_feature else 2)
    killed = is_feature or int(row["detected_mutants"]) == 2
    return {row["arm"]: row["valid"] == "1" and correct and killed}


def binary_scores(row):
    return {arm: int(row[arm]) == 1 for arm in ARMS}


def main():
    print("Study                          Tasks   None   RAG Fixed Feedback")
    naming = read_rows("naming.csv")
    for kind, expected in (("feature", (3, 5, 6, 6)), ("test", (13, 17, 23, 25))):
        rows = [r for r in naming if r["kind"] == kind]
        tasks = collect(rows, ("project", "version", "style"), whole_naming)
        report("Naming " + kind, tasks, 28, expected)
        for key, scores in tasks.items():
            if scores["feedback"] != scores["fixed"]:
                winner = "feedback" if scores["feedback"] else "fixed"
                print(f"  {' / '.join(key)}: {winner} only (feedback vs fixed)")

    author = read_rows("author-tests.csv")
    if sum(int(row["assertions"]) for row in author) != 365:
        raise ValueError("Unexpected number of author assertions")
    tasks = collect(author, ("project", "style"),
                    lambda r: {a: int(r[a]) == int(r["assertions"]) for a in ARMS})
    report("Author tests (all assertions)", tasks, 28, (6, 8, 8, 8))

    native = read_rows("native-features.csv")
    expected_by_mode = {
        "original": (3, 5, 4, 5),
        "bindings_only": (4, 6, 5, 6),
        "format_only": (4, 5, 5, 5),
        "both": (5, 6, 6, 6),
    }
    for mode, expected in expected_by_mode.items():
        rows = [r for r in native if r["integration"] == mode]
        report("Native features " + mode, collect(rows, ("task",), binary_scores), 6, expected)

    rows = read_rows("native-tests.csv")
    tasks = collect(rows, ("project", "task"), lambda r: {
        r["arm"]: r["passed_on_original"] == "1" and int(r["detected_mutants"]) == 2
                  and int(r["copied_assertions"]) == 0
    })
    report("Native pytest design", tasks, 6, (4, 3, 2, 2))

    dates = read_rows("date-formats.csv")
    report("Date formats", collect(dates, ("project", "locale", "style"), binary_scores),
           168, (122, 137, 149, 154))
    after = sum(int(r["always_morning"] if r["style"] in ("LT", "LTS") else r["always_mixed"])
                for r in dates)
    if after != 155:
        raise ValueError("Unexpected post-hoc date rule count")
    print(f"Post-hoc date rule: {after}/{len(dates)}")


if __name__ == "__main__":
    main()
