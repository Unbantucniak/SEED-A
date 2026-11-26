"""Choose whether a version-compatible experience should enter a developer's next task."""
from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True)
class GateReceipt:
    scope: str
    version: str
    family: str
    use: bool
    success: bool
    receipt_id: str


class FeedbackGate:
    """Two-action policy. The caller submits evidence for the action actually taken.

    Past outcomes in the same family get full weight. Other families in the
    project and version contribute at most one effective observation per action.
    A weak prior favors the caller's static policy on cold start. No model call
    or access to labels is required at decision time.
    """

    def __init__(self, receipts=()):
        self.receipts = {}
        self.counts = Counter()
        self.totals = Counter()
        for r in receipts:
            self.update(r.scope,r.version,r.family,r.use,r.success,r.receipt_id)

    def update(self, scope, version, family, use, success, receipt_id):
        if not all(isinstance(k,str) and k.strip() for k in (scope,version,family,receipt_id)):
            raise ValueError("A project, version, family and unique receipt are required.")
        if type(use) is not bool or type(success) is not bool:
            raise ValueError("Both chosen action and observed success must be boolean.")
        receipt = GateReceipt(scope, version, family, use, success, receipt_id)
        key = (scope,version,receipt_id)
        if key in self.receipts:
            if self.receipts[key] != receipt:
                raise ValueError("The same receipt cannot change a prior action or outcome.")
            return
        self.receipts[key] = receipt
        self.counts[scope,version,family,use,success] += 1
        self.totals[scope,version,use,success] += 1

    def explain(self, scope, version, family, eligible=True, prior_use=True, adaptive=True):
        if not all(isinstance(k,str) and k.strip() for k in (scope,version,family)):
            raise ValueError("A project, version and family are required.")
        stats = {}
        for use in (False,True):
            hits = self.counts[scope,version,family,use,True]
            misses = self.counts[scope,version,family,use,False]
            other_hits = self.totals[scope,version,use,True] - hits
            others = other_hits + self.totals[scope,version,use,False] - misses
            weight = min(1,others)
            # Symmetric 2-trial prior with a 0.2 pseudo-success preference.
            mean = (1 + 0.2 * (use == prior_use) + hits + other_hits/max(1,others)) / (2+hits+misses+weight)
            stats[use] = dict(score=mean, local_pass=hits, local_fail=misses, outside_family=others)
        if adaptive:
            use = max((False,True), key=lambda action: (stats[action]["score"], action==prior_use))
        else:
            use = prior_use
        return dict(use=bool(eligible and use), fixed_use=bool(eligible and prior_use), stats=stats)

    def choose(self, scope, version, family, eligible=True, prior_use=True, adaptive=True):
        return self.explain(scope,version,family,eligible,prior_use,adaptive)["use"]
