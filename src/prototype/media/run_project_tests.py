"""Run the one pytest file selected by the developer and report observed counts."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    import pytest
    root = Path.cwd().resolve()
    source, test = (Path(arg).resolve(strict=True) for arg in sys.argv[1:])
    for path in (source, test):
        if not path.is_relative_to(root) or path.suffix != '.py':
            raise ValueError('源文件、测试文件须位于当前 Python 工作区')
    source_hash, test_hash = digest(source), digest(test)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='seeda-pytest-') as directory:
        xml = Path(directory) / 'result.xml'
        options = [sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', '--junitxml', str(xml),
                   '--', './' + test.relative_to(root).as_posix()]
        proc = subprocess.run(options, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120,
            env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONIOENCODING': 'utf-8'})
        report = ET.parse(xml).getroot() if xml.exists() else None
        cases = report.findall('.//testcase') if report is not None else []
        passed = sum(not any(row.find(tag) is not None for tag in ('skipped', 'error', 'failure')) for row in cases)
        skipped = sum(row.find('skipped') is not None for row in cases)
        if (source_hash, test_hash) != (digest(source), digest(test)):
            raise ValueError('运行期间源文件或测试文件已变化，请重新验证')
        print(json.dumps(dict(passed=passed, total=len(cases), skipped=skipped, exit_code=proc.returncode,
            seconds=time.monotonic()-started, file_sha256=source_hash, test_sha256=test_hash, executor_sha256=digest(Path(__file__)),
            pytest_version=pytest.__version__, output=proc.stdout[-6000:].decode('utf-8', errors='replace'))))


if __name__ == '__main__':
    main()
