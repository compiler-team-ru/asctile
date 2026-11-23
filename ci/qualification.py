"""Retain narrowly identified upstream incompatibilities; reject unexplained failures."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from target import target_names


def incompatible(job, log, version):
    target = re.fullmatch(r'wheel \((cp39-(?:x86_64|aarch64)), [^,]+, [^)]+\)', job['name'])
    assert target and job['conclusion'] == 'failure', 'Unexplained failed target'
    failed_steps = [s['name'] for s in job['steps'] if s['conclusion'] == 'failure']
    assert failed_steps == ['Build wheel and check clean installations'], failed_steps
    assert 'Successfully installed ' in log and 'pyasc-dev-' + version in log
    assert '/asc/runtime/jit.py", line 36' in log
    assert '@dataclass(frozen=True, slots=True)' in log
    assert "TypeError: dataclass() got an unexpected keyword argument 'slots'" in log
    return target.group(1), {
        'status': 'incompatible', 'reason': 'Upstream asc/runtime/jit.py uses dataclass(slots=True), which requires Python 3.10 or newer.',
        'job_url': job['html_url'], 'log_sha256': hashlib.sha256(log.encode()).hexdigest(),
    }


def matrix_jobs(jobs):
    targets = [j for j in jobs if j['name'].startswith('wheel (')]
    names = []
    for job in targets:
        match = re.fullmatch(r'wheel \((cp\d+-(?:x86_64|aarch64)), [^,]+, [^)]+\)', job['name'])
        assert match, 'Unexpected wheel job name'
        names.append(match.group(1))
    assert len(names) == len(set(names)), 'Duplicate wheel target jobs'
    assert set(names) == set(target_names()), 'Incomplete wheel target jobs'
    return targets


def main():
    artifacts, run_id, output = sys.argv[1:]
    passports = [json.loads(p.read_text()) for p in Path(artifacts).glob('*/build-passport.json')]
    assert passports and {str(p['run_id']) for p in passports} == {run_id}
    versions = {p['version'] for p in passports}
    sources = {p['source_sha'] for p in passports}
    assert len(versions) == len(sources) == 1
    repo = os.environ['GITHUB_REPOSITORY']
    run = json.loads(subprocess.check_output(['gh', 'api', f'repos/{repo}/actions/runs/{run_id}'], text=True))
    assert run['head_branch'] == 'main' and run['path'] == '.github/workflows/wheels.yml'
    assert run['event'] in ('push', 'schedule', 'workflow_dispatch')
    assert {p['recipe_commit'] for p in passports} == {run['head_sha']}
    jobs = json.loads(subprocess.check_output(['gh', 'api', f'repos/{repo}/actions/runs/{run_id}/jobs?per_page=100'], text=True))['jobs']
    result = {}
    targets = matrix_jobs(jobs)
    for job in targets:
        assert job['status'] == 'completed'
        if job['conclusion'] == 'success':
            continue
        log = subprocess.check_output(['gh', 'api', '--allow-escape-sequences', f'repos/{repo}/actions/jobs/{job["id"]}/logs'], text=True)
        target, evidence = incompatible(job, log, next(iter(versions)))
        evidence['source_sha'] = next(iter(sources))
        result[target] = evidence
    Path(output).write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
