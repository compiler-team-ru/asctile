import unittest
from qualification import incompatible, matrix_jobs
from target import target_names


class QualificationTests(unittest.TestCase):
    def test_complete_matrix_required(self):
        jobs = [{'name': f'wheel ({name}, ubuntu-24.04, {name.split("-")[1]})'}
                for name in target_names()]
        self.assertEqual(matrix_jobs(jobs), jobs)
        for invalid in (jobs[:-1], jobs + [jobs[0]], jobs[:-1] + [jobs[0]]):
            with self.assertRaises(AssertionError):
                matrix_jobs(invalid)

    def test_new_python_failures_block_publication(self):
        for tag in ('cp313', 'cp314'):
            job = {'name': f'wheel ({tag}-x86_64, ubuntu-24.04, x86_64)',
                   'conclusion': 'failure'}
            with self.assertRaises(AssertionError):
                incompatible(job, 'dependency resolution failed', '1.1.1.dev1')

    def test_only_known_native_import_incompatibility(self):
        job = {'name': 'wheel (cp39-x86_64, ubuntu-24.04, x86_64)', 'conclusion': 'failure',
               'html_url': 'https://github.com/compiler-team-ru/asctile/actions/runs/1/job/2',
               'steps': [{'name': 'Build wheel and check clean installations', 'conclusion': 'failure'}]}
        log = '''Successfully installed pyasc-dev-1.1.1.dev1
File "/venv/asc/runtime/jit.py", line 36
@dataclass(frozen=True, slots=True)
TypeError: dataclass() got an unexpected keyword argument 'slots'
'''
        self.assertEqual(incompatible(job, log, '1.1.1.dev1')[0], 'cp39-x86_64')
        for bad in (log.replace('slots', 'unknown'), log.replace('1.1.1.dev1', '1.1.1.dev2'), 'network error'):
            with self.assertRaises(AssertionError):
                incompatible(job, bad, '1.1.1.dev1')
        job['name'] = job['name'].replace('cp39', 'cp310')
        with self.assertRaises(AssertionError):
            incompatible(job, log, '1.1.1.dev1')
