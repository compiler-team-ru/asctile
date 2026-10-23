import unittest
from qualification import incompatible


class QualificationTests(unittest.TestCase):
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
