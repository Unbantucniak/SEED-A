import json
from pathlib import Path
import subprocess
import sys


CLI=Path(__file__).resolve().parents[1]/"tools"/"experience_feedback.py"


def invoke(db,repo,command,*args,version="1",family="exports",status=0):
    # The CLI runs without site packages. Its test subprocess uses the project's interpreter.
    cmd=[sys.executable,"-S",str(CLI),"--db",str(db),command,"--repo",str(repo),"--version",version,"--family",family,*args]
    run=subprocess.run(cmd,capture_output=True)
    assert run.returncode==status,(run.stdout,run.stderr)
    return json.loads(run.stdout) if run.stdout else None


def test_observed_failure_learns_only_for_same_card_scope_and_mode(tmp_path):
    repo=tmp_path/"repo"
    repo.mkdir()
    db=tmp_path/"history.sqlite3"
    cardfile=repo/"tip.md"
    cardfile.write_text("Candidate experience",encoding="utf8")
    card=invoke(db,repo,"remember","--file",str(cardfile))["card"]
    options=["--task","publish a field","--card",card,"--prior","use"]
    first=invoke(db,repo,"decide",*options,"--policy","learn")
    assert first["recommendation"]=="use" and first["experience"]["text"]=="Candidate experience"
    target=repo/"test_project.py"
    target.write_text("def test_public():\n    assert 1 == 2\n",encoding="utf8")
    failed=invoke(db,repo,"verify","--id",first["id"],"--actual","use","--target",target.name,status=1)
    assert failed["evidence"]["source"]=="pytest" and failed["evidence"]["failed"]==1
    assert not failed["evidence"]["passed"]
    invoke(db,repo,"report","--id",first["id"],"--actual","use","--outcome","pass","--evidence","changed",status=2)
    restarted=invoke(db,repo,"decide",*options,"--policy","learn")
    assert restarted["recommendation"]=="skip" and restarted["experience"] is None
    assert invoke(db,repo,"decide",*options)["recommendation"]=="use"
    assert invoke(db,repo,"decide","--task","no opted-in use","--card",card)["recommendation"]=="skip"
    manual=["--id",restarted["id"],"--actual","skip","--outcome","pass","--evidence","pair reviewed"]
    assert invoke(db,repo,"report",*manual)==invoke(db,repo,"report",*manual)
    assert invoke(db,repo,"show","--id",restarted["id"])["evidence"]["source"]=="manual"
    other=tmp_path/"other"/"repo"
    other.mkdir(parents=True)
    for path,opts in ((other,{}),(repo,dict(version="2")),(repo,dict(family="other"))):
        invoke(db,path,"decide",*options,**opts,status=2)
        assert invoke(db,path,"show",**opts)==[]
        assert invoke(db,path,"cards",**opts)==[]
    cardfile.write_text("Different tip",encoding="utf8")
    new=invoke(db,repo,"remember","--file",str(cardfile))["card"]
    assert {c["id"]:c["body"] for c in invoke(db,repo,"cards")}=={card:"Candidate experience",new:"Different tip"}
    assert invoke(db,repo,"decide","--task","fresh", "--card",new,"--policy","learn","--prior","use")["recommendation"]=="use"


def test_actual_overrides_prior_and_invalid_runs_never_complete(tmp_path):
    db=tmp_path/"local.sqlite3"
    file=tmp_path/"card"
    file.write_text("Validated experience",encoding="utf8")
    card=invoke(db,tmp_path,"remember","--file",str(file))["card"]
    pending=invoke(db,tmp_path,"decide","--task","developer chooses differently","--card",card,"--prior","use")
    test=tmp_path/"test_actions.py"
    test.write_text("import pytest\ndef test_it(): pytest.skip('offline')",encoding="utf8")
    verify=["--id",pending["id"],"--actual","skip","--target",test.name]
    invoke(db,tmp_path,"verify",*verify,status=2)
    assert invoke(db,tmp_path,"show","--id",pending["id"])["completed"] is None
    test.write_text("def test_it(): assert True",encoding="utf8")
    item=invoke(db,tmp_path,"verify",*verify)
    assert item["actual"]=="skip" and item["evidence"]["passed"] and item["decision"]["recommendation"]=="use"
    learn=invoke(db,tmp_path,"decide","--task","control stays separate","--card",card,"--policy","learn","--prior","use")
    assert learn["observations"]["skip"]["local_pass"]==0
    for badtarget in (str(CLI),"does-not-exist.py","-q"):
        invoke(db,tmp_path,"verify","--id",learn["id"],"--actual","use","--target",badtarget,status=2)
    assert invoke(db,tmp_path,"show","--id",learn["id"])["completed"] is None
