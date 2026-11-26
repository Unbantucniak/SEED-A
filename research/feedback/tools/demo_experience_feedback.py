"""Exercise the public CLI against a fixed release of an independent Python library."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tempfile import mkdtemp
from urllib.request import urlopen
from zipfile import ZipFile

CLI=Path(__file__).with_name("experience_feedback.py").resolve()
RELEASE="https://codeload.github.com/chrisdoherty4/python-case-converter/zip/refs/tags/v1.2.0"
EXPECTED="4efefbb0e0e1cb53e492b16bfcadc677598527e88cb9a7a0c8300b9013c4098f"
ORIGIN="https://github.com/chrisdoherty4/python-case-converter/blob/c37a1240f08b0f8ec1963910fdfda23b51f013a1/"


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive",type=Path,help="可选。同一上游版本的本地 ZIP，可离线运行。")
    parser.add_argument("--output",type=Path,help="可选。将演示回执另存为新的 JSON 文件。")
    args=parser.parse_args()
    dest=Path(mkdtemp(prefix="seeda-developer-feedback-"))
    archive=args.archive
    if archive is None:
        archive=dest/"release.zip"
        with urlopen(RELEASE,timeout=30) as response:
            archive.write_bytes(response.read())
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=EXPECTED:
        raise ValueError("上游归档内容与固定发行版不符。")
    with ZipFile(archive) as z:
        z.extractall(dest)
    repo=dest/"python-case-converter-1.2.0"
    db=dest/"decisions.sqlite3"
    scope=["--repo",str(repo),"--version","1.2.0","--family","public naming adapters"]
    trace=[]

    def cli(command,*options,status=0):
        cmd=[sys.executable,str(CLI),"--db",str(db),command,*scope,*options]
        result=subprocess.run(cmd,capture_output=True)
        if status is not None and result.returncode!=status:
            raise RuntimeError((cmd,result.returncode,result.stderr))
        response=json.loads(result.stdout)
        trace.append(dict(command=cmd,exit=result.returncode,response=response))
        return response

    source_test="caseconverter/caseconverter_test.py::test_no_strip_punctuation"
    documented=subprocess.run([sys.executable,"-m","pytest","-q",source_test],cwd=repo,capture_output=True,check=True)
    card_text=("The package accepts strip_punctuation=False when punctuation must be preserved. "
               "The author's camelcase example retains a comma and exclamation mark. "
               f"Source: {ORIGIN}caseconverter/caseconverter_test.py#L17")
    file=dest/"punctuation.md"
    file.write_text(card_text,encoding="utf8")
    card=cli("remember","--file",str(file))["card"]
    runs=[]
    for style,policy in [("camel","learn"),("pascal","fixed"),("pascal","learn")]:
        pending=cli("decide","--card",card,"--task",f"Expose a {style} adapter matching the author's default tests.",
                    "--policy",policy,"--prior","use")
        action=pending["recommendation"]
        name=style+"case"
        # Two explicit developer actions. Keep the original converter package unchanged.
        option=", strip_punctuation=False" if action=="use" else ""
        code=f"from caseconverter import {name} as upstream\n\ndef {name}(text):\n    return upstream(text{option})\n"
        (repo/"developer_feature.py").write_text(code,encoding="utf8")
        upstream_file=f"caseconverter/{style}_test.py"
        original=(repo/upstream_file).read_text(encoding="utf8")
        assert original.count("from . import *")==1
        target="test_developer_adapter.py"
        (repo/target).write_text(original.replace("from . import *",f"from developer_feature import {name}"),encoding="utf8")
        receipt=cli("verify","--actual",action,"--id",pending["id"],"--target",target,status=None)
        restored=cli("show","--id",pending["id"])
        assert restored==receipt
        runs.append(dict(style=style,policy=policy,action=action,wrapper=code,source=ORIGIN+upstream_file,
                         decision=pending,receipt=restored))
    assert [(r["action"],r["receipt"]["evidence"]["passed"]) for r in runs]==[("use",False),("use",False),("skip",True)]
    result=dict(upstream_sha256=EXPECTED,repo=str(repo),database=str(db),original_test=source_test,
                original_result=documented.stdout.decode("utf8","replace"),experience=card_text,trials=runs,calls=trace)
    payload=json.dumps(result,ensure_ascii=False,indent=2)+"\n"
    (dest/"demo.json").write_text(payload,encoding="utf8")
    if args.output:
        args.output.parent.mkdir(exist_ok=True,parents=True)
        with args.output.open("x",encoding="utf8") as output:
            output.write(payload)
    print(str(dest/"demo.json"))
    for item in runs:
        e=item["receipt"]["evidence"]
        print(item["style"],item["policy"],item["action"],e["tests"]-e["failed"],"/",e["tests"])


if __name__=="__main__":
    main()
