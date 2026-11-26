"""Select an identifier conversion implementation using public execution feedback."""
from .identifier_conventions import signature, STYLE_GROUP


OPTIONS = ("rule", "draft", "patch", "patched_rule")


def scope_weight(style, text, old_style, old_text):
    shape, old = signature(text), signature(old_text)
    return (1 + 3 * (STYLE_GROUP[style] == STYLE_GROUP[old_style])
            + 5 * (style == old_style) + 5 * (shape == old)
            + sum(a == b for a, b in zip(shape, old)))


def values(style, text, draft, engine, boundary):
    inferred = engine.infer(text, force=True)
    rule = draft if inferred is None else inferred
    return dict(rule=rule, draft=draft, patch=boundary.apply(style, text, draft)[0],
                patched_rule=boundary.apply(style, text, rule)[0])


class ConventionRouter:
    """Store disagreements only. Repeated attempts at one execution count once.

    The owner instantiates a router per repository and version. Current smoke
    results set the fixed decision. Earlier executed tasks can resolve ties
    after the receipt has been recorded.
    """
    def __init__(self, project, version):
        self.scope = (project, version)
        self.events = {}

    def observe(self, project, version, receipt, style, text, candidates, observed):
        if (project, version) != self.scope:
            raise ValueError("Feedback belongs to a different project or version")
        entry = (style, text, {k: candidates[k] == observed for k in OPTIONS})
        if receipt in self.events and self.events[receipt] != entry:
            raise ValueError("Conflicting feedback for one execution")
        self.events[receipt] = entry

    def choose(self, style, text, candidates, probes, *, learn):
        # Give verified local behavior priority. Historical calibration only
        # distinguishes options that agree equally well with current probes.
        local = {k: sum(int(outputs[k] == actual) for _, outputs, actual in probes) for k in OPTIONS}
        tied = [k for k in OPTIONS if local[k] == max(local.values())]
        if not learn or len(tied) == 1 or len({candidates[k] for k in tied}) == 1:
            return tied[0]
        support = {k: 0 for k in tied}
        for old_style, old_text, matched in self.events.values():
            if len({matched[k] for k in tied}) < 2:
                continue
            weight = scope_weight(style, text, old_style, old_text)
            for key in tied:
                if matched[key]:
                    support[key] += weight
        return max(tied, key=support.get)
