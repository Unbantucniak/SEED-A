"""Choose, apply and verify a local development experience without a model or server."""

import argparse
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.workbench.feedback_decisions import (
    card_from_file,connect,decide,display,find_trial,pytest_evidence,record,scope_for,validate_action
)


def main():
    cli=argparse.ArgumentParser(description="按项目、版本和任务族，记录经验选用与开发验收结果。")
    cli.add_argument("--db",type=Path,default=ROOT/"results/workbench/session/feedback_decisions.sqlite3",
                     help="SQLite 文件，默认位于工作台持久化目录")
    commands=cli.add_subparsers(dest="command",required=True)
    for name,label in (("remember","登记一条当前版本的经验"),("cards","读回当前项目、版本和任务族的经验快照"),("decide","为新任务选择是否使用经验"),
                       ("verify","实际执行 pytest 并记录结果"),("report","记录人工验收及其依据"),("show","查阅此前的决策和收据")):
        sub=commands.add_parser(name,help=label)
        sub.add_argument("--repo",type=Path,required=True,help="真实项目的根目录")
        sub.add_argument("--version",required=True)
        sub.add_argument("--family",required=True,help="可比较任务的类别")
        if name=="remember":
            sub.add_argument("--file",type=Path,required=True,help="UTF-8 经验文本文件")
        elif name=="decide":
            sub.add_argument("--task",required=True)
            sub.add_argument("--card",help="remember 返回的经验编号")
            sub.add_argument("--policy",choices=("fixed","learn"),default="fixed")
            sub.add_argument("--prior",choices=("use","skip"),default="skip",help="固定选择或学习模式的初始偏好")
        elif name!="cards":
            sub.add_argument("--id",required=name!="show",help="decide 返回的决策编号")
            if name in ("verify","report"):
                sub.add_argument("--actual",choices=("use","skip"),required=True,help="开发中实际采取的动作")
            if name=="verify":
                sub.add_argument("--target",action="append",required=True,help="相对项目目录的 pytest 文件或节点，可重复")
                sub.add_argument("--timeout",type=int,default=120)
                sub.add_argument("--python",type=Path,help="项目虚拟环境中的 Python 可执行文件")
            if name=="report":
                sub.add_argument("--outcome",choices=("pass","fail"),required=True)
                sub.add_argument("--evidence",required=True,help="人工验收依据或其位置")
    a=cli.parse_args()
    try:
        scope=scope_for(a.repo,a.version,a.family)
        if a.command=="verify":
            with connect(a.db) as db:
                trial=find_trial(db,scope,a.id)
                validate_action(trial,a.actual)
                if trial["completed"]:
                    raise ValueError("本次决策已经完成。用 show 查阅原回执。")
            # Long-running tests execute outside the database transaction.
            evidence=pytest_evidence(scope[0],a.target,a.timeout,a.python)
        with connect(a.db) as db:
            if a.command=="remember":
                result=card_from_file(db,scope,a.file)
            elif a.command=="cards":
                result=[dict(row) for row in db.execute(
                    "SELECT id,source,body FROM cards WHERE project=? AND version=? AND family=? ORDER BY id",scope)]
            elif a.command=="decide":
                result=decide(db,scope,a.task,a.card,a.policy,a.prior)
            elif a.command=="verify":
                result=record(db,scope,a.id,a.actual,evidence)
            elif a.command=="report":
                if not a.evidence.strip():
                    raise ValueError("请填写人工验收的依据。")
                result=record(db,scope,a.id,a.actual,dict(source="manual",passed=a.outcome=="pass",note=a.evidence))
            elif a.id:
                result=display(find_trial(db,scope,a.id))
            else:
                result=[display(r) for r in db.execute(
                    "SELECT * FROM trials WHERE project=? AND version=? AND family=? ORDER BY decided,id",scope)]
        print(json.dumps(result,ensure_ascii=True))
        if a.command=="verify" and not result["evidence"]["passed"]:
            return 1
        return 0
    except (OSError,ValueError,sqlite3.Error,subprocess.TimeoutExpired) as error:
        cli.exit(2,f"{error}\n")


if __name__=="__main__":
    raise SystemExit(main())
