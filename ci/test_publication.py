import unittest
from publication import reconcile


class PublicationTests(unittest.TestCase):
    def manifest(self):
        return {'wheels': {'cp310-x86_64': {'filename': 'a.whl', 'sha256': 'a' * 64}}}

    def test_partial_upload_is_reconcilable(self):
        reconcile(self.manifest(), {})
        with self.assertRaises(ValueError):
            reconcile(self.manifest(), {}, complete=True)

    def test_existing_conflicting_bytes_fail(self):
        with self.assertRaises(AssertionError):
            reconcile(self.manifest(), {'a.whl': {'digests': {'sha256': 'b' * 64}}})

    def test_verified_url_is_recorded(self):
        manifest = self.manifest()
        reconcile(manifest, {'a.whl': {'digests': {'sha256': 'a' * 64},
                                      'yanked': False, 'url': 'https://files.pythonhosted.org/a.whl'}}, complete=True)
        self.assertEqual(manifest['wheels']['cp310-x86_64']['url'],
                         'https://files.pythonhosted.org/a.whl')
