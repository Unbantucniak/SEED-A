import pytest
from src.experience_manager.feedback_gate import FeedbackGate


def test_bad_selected_experience_switches_next_action_and_can_be_replayed():
    g=FeedbackGate()
    scope=("example","1.2","number")
    assert g.choose(*scope)
    g.update(*scope,True,False,"first")
    assert not g.choose(*scope)
    assert g.choose(*scope,adaptive=False)
    assert g.choose("example","2.0","number")
    assert not g.choose(*scope,eligible=False)
    g.update(*scope,True,False,"first")
    assert not FeedbackGate(g.receipts.values()).choose(*scope)
    with pytest.raises(ValueError):
        g.update(*scope,True,True,"first")


def test_starts_with_caller_default_and_learns_to_use_as_well_as_abstain():
    gate=FeedbackGate()
    args=("example","main","config")
    assert not gate.choose(*args,prior_use=False)
    gate.update(*args,False,False,"a")
    assert gate.choose(*args,prior_use=False)
    gate.update(*args,True,True,"b")
    assert gate.choose(*args,prior_use=False)
