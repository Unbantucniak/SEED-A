"""Local durable use/skip decisions for an explicitly scoped development workflow."""

from contextlib import closing, contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
from uuid import uuid4
from xml.etree import ElementTree

from src.experience_manager.feedback_gate import FeedbackGate


def now():
    return datetime.now(timezone.utc).isoformat()


def scope_for(repo,version,family):
    folder = Path(repo).expanduser().resolve(strict=True)
    if not folder.is_dir() or not version.strip() or not family.strip():
        raise ValueError("请输入真实项目目录、版本和任务族。")
    return (os.path.normcase(str(folder)),version.strip(),family.strip())


@contextmanager
def connect(path):
    path.parent.mkdir(parents=True,exist_ok=True)
    with closing(sqlite3.connect(path,timeout=15)) as db, db:
        db.row_factory=sqlite3.Row
        db.executescript("""
           CREATE TABLE IF NOT EXISTS cards (
             id TEXT PRIMARY KEY, project TEXT, version TEXT, family TEXT, body TEXT, source TEXT);
           CREATE TABLE IF NOT EXISTS trials (
             id TEXT PRIMARY KEY, project TEXT, version TEXT, family TEXT, task TEXT,
             card TEXT, policy TEXT, decided TEXT, decision TEXT, actual TEXT, completed TEXT, evidence TEXT);
           CREATE INDEX IF NOT EXISTS trials_scope ON trials(project,version,family,policy);
        """)
        db.execute("BEGIN IMMEDIATE")
        yield db


def card_from_file(db,scope,path):
    body = path.read_text(encoding="utf-8-sig")
    if not body.strip():
        raise ValueError("经验文件为空。")
    key = sha256(json.dumps([*scope,body],ensure_ascii=False).encode("utf8")).hexdigest()
    db.execute("INSERT OR IGNORE INTO cards VALUES (?,?,?,?,?,?)",(key,*scope,body,str(path.resolve())))
    return dict(card=key,project=scope[0],version=scope[1],family=scope[2])


def decide(db,scope,task,card,policy,prior):
    if not task.strip():
        raise ValueError("请填写此次要完成的具体任务。")
    candidate = None
    if card:
        candidate = db.execute("SELECT * FROM cards WHERE id=? AND project=? AND version=? AND family=?",
                               (card,*scope)).fetchone()
        if candidate is None:
            raise ValueError("经验不属于当前项目、版本及任务族，或编号不存在。")
    gate = FeedbackGate()
    history = db.execute("""SELECT id,actual,evidence FROM trials
       WHERE project=? AND version=? AND family=? AND card=? AND policy='learn' AND completed IS NOT NULL""",(*scope,card))
    for row in history:
        result = json.loads(row["evidence"])
        gate.update(*scope,row["actual"]=="use",result["passed"],row["id"])
    detail = gate.explain(*scope,eligible=bool(candidate),prior_use=prior=="use",adaptive=policy=="learn")
    recommendation = "use" if detail["use"] else "skip"
    data = dict(recommendation=recommendation,prior=prior,eligible=bool(candidate),
                observations={action:detail["stats"][action=="use"] for action in ("use","skip")})
    key = uuid4().hex
    db.execute("INSERT INTO trials (id,project,version,family,task,card,policy,decided,decision) VALUES (?,?,?,?,?,?,?,?,?)",
               (key,*scope,task,card,policy,now(),json.dumps(data)))
    return dict(id=key,project=scope[0],version=scope[1],family=scope[2],task=task,policy=policy,
                **data,experience=dict(id=card,source=candidate["source"],text=candidate["body"]) if recommendation=="use" else None)


def find_trial(db,scope,key):
    row = db.execute("SELECT * FROM trials WHERE id=? AND project=? AND version=? AND family=?", (key,*scope)).fetchone()
    if row is None:
        raise ValueError("当前项目、版本和任务族中没有这次决策。")
    return row


def display(row):
    value = dict(row)
    for name in ("decision","evidence"):
        value[name] = json.loads(value[name]) if value[name] is not None else None
    return value


def validate_action(row,actual):
    if actual == "use" and row["card"] is None:
        raise ValueError("此次决策没有已登记的候选经验，无法记录为使用。")


def record(db,scope,key,actual,evidence):
    trial = find_trial(db,scope,key)
    validate_action(trial,actual)
    if trial["completed"]:
        if trial["actual"] == actual and json.loads(trial["evidence"]) == evidence:
            return display(trial)
        raise ValueError("本次决策已有不可覆盖的完成回执。")
    db.execute("UPDATE trials SET actual=?,completed=?,evidence=? WHERE id=?",
               (actual,now(),json.dumps(evidence,ensure_ascii=False),key))
    return display(find_trial(db,scope,key))


def pytest_evidence(repo,targets,timeout,python):
    """Only completed positive-size pytest suites with actual pass/fail produce feedback."""
    if timeout <= 0 or any(not target or target.startswith("-") for target in targets):
        raise ValueError("请提供 pytest 文件或节点名，并指定大于零的超时秒数。")
    for target in targets:
        path = (Path(repo)/target.split("::",1)[0]).resolve(strict=True)
        if not path.is_relative_to(Path(repo)):
            raise ValueError("pytest 目标必须位于此次决策的项目目录内。")
    executable = sys.executable if python is None else str(Path(python).expanduser().resolve(strict=True))
    with TemporaryDirectory(prefix="seeda-pytest-") as temp:
        report = Path(temp)/"report.xml"
        # Options belong before user positional node IDs. Never invoke a shell.
        cmd = [executable,"-m","pytest",f"--junitxml={report}","--",*targets]
        run = subprocess.run(cmd,cwd=repo,capture_output=True,timeout=timeout)
        output = (run.stdout+run.stderr).decode("utf8","replace")
        if run.returncode not in (0,1) or not report.is_file():
            raise ValueError(f"pytest 未完成可计分的验收（退出码 {run.returncode}）。\n{output[-2000:]}")
        cases = ElementTree.parse(report).getroot().findall(".//testcase")
        errors = sum(c.find("error") is not None for c in cases)
        skipped = sum(c.find("skipped") is not None for c in cases)
        failures = sum(c.find("failure") is not None for c in cases)
        if errors or len(cases) == skipped or bool(failures) != bool(run.returncode):
            raise ValueError(f"pytest 有环境错误、没有实际执行的断言用例，或报告不完整。错误 {errors}，跳过 {skipped}，失败 {failures}。")
        return dict(source="pytest",passed=run.returncode==0,exit_code=run.returncode,python=executable,
                    targets=targets,tests=len(cases),skipped=skipped,failed=failures,
                    executed=[dict(suite=c.get("classname"),name=c.get("name"),
                                   result="failed" if c.find("failure") is not None else "skipped" if c.find("skipped") is not None else "passed")
                              for c in cases])
