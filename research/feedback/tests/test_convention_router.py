import pytest

from src.experience_manager.boundary_memory import BoundaryMemory
from src.experience_manager.convention_router import ConventionRouter, OPTIONS


def options(rule, draft):
    return dict(rule=rule, draft=draft, patch=draft, patched_rule=rule)


def test_public_failure_leads_to_abstention_only_on_the_next_task():
    router = ConventionRouter("package", "2")
    now = options("abc-widget", "abcwidget")
    smoke = [["Blue", dict.fromkeys(OPTIONS, "blue"), "blue"]]
    assert router.choose("kebab", "ABCWidget", now, smoke, learn=True) == "rule"
    earlier = ("package", "2", "receipt", "kebab", "IOReader", options("io-reader", "ioreader"), "ioreader")
    router.observe(*earlier)
    router.observe(*earlier)
    assert len(router.events) == 1
    assert router.choose("kebab", "ABCWidget", now, smoke, learn=True) == "draft"
    assert router.choose("kebab", "ABCWidget", now, smoke, learn=False) == "rule"
    # Successful tests of this task take precedence over old experience.
    decisive = [["XMLTools", options("xml-tools", "xmltools"), "xml-tools"]]
    assert router.choose("kebab", "ABCWidget", now, decisive, learn=True) == "rule"
    with pytest.raises(ValueError):
        router.observe(*earlier[:-1], "changed")
    with pytest.raises(ValueError):
        router.observe("package", "1", *earlier[2:])


def test_boundary_memory_requires_independent_examples_and_can_keep_draft():
    # This package keeps acronym and following word together.
    records = [("kebab", "IOReader", "ioreader"), ("kebab", "IDWriter", "idwriter")]
    assert BoundaryMemory(records[:1]).apply("kebab","DBLoader","db-loader") == ("db-loader", 0)
    assert BoundaryMemory(records).apply("kebab","DBLoader","db-loader") == ("dbloader", 1)
    assert BoundaryMemory(records).apply("kebab","DBLoader","different") == ("different", 0)
