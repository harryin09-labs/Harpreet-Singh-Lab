import importlib.util
from pathlib import Path
import tempfile
import types
import unittest

P = Path(__file__).parents[1] / 'scripts' / 'a1_launcher.py'
spec = importlib.util.spec_from_file_location('launcher', P)
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)

class FakeOci:
    class auth:
        class signers:
            class InstancePrincipalsSecurityTokenSigner:
                pass
    class retry:
        class NoneRetryStrategy:
            def __call__(self): return None
    class exceptions:
        class ServiceError(Exception): pass
    def __init__(self, instances=()):
        self.instances = instances
        self.calls = 0
        outer = self
        class ComputeClient:
            def __init__(self, *args, **kwargs): pass
            def list_instances(self, **kwargs): return types.SimpleNamespace(data=outer.instances)
        class Pagination:
            @staticmethod
            def list_call_get_all_results(method, **kwargs): return method(**kwargs)
        self.core = types.SimpleNamespace(ComputeClient=ComputeClient)
        self.pagination = Pagination

class TestLauncher(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name)
        self.cfg = dict(region='ap-hyderabad-1',compartment_id='test',instance_name='max-free-a1',shape='VM.Standard.A1.Flex')
    def tearDown(self): self.tmp.cleanup()
    def test_dry_run_no_launch(self):
        fake=FakeOci()
        self.assertEqual(launcher.execute(self.cfg,self.state,False,fake),'dry-run')
        self.assertFalse((self.state/'pending.json').exists())
    def test_existing_a1_holds(self):
        x=types.SimpleNamespace(shape='VM.Standard.A1.Flex',lifecycle_state='PROVISIONING',display_name='max-free-a1',id='abc')
        self.assertEqual(launcher.execute(self.cfg,self.state,False,FakeOci([x])),'existing')
    def test_pending_holds(self):
        (self.state/'pending.json').write_text('{}')
        self.assertEqual(launcher.execute(self.cfg,self.state,False,FakeOci()),'hold')
    def test_success_marker_holds(self):
        (self.state/'success.txt').write_text('old')
        self.assertEqual(launcher.execute(self.cfg,self.state,False,FakeOci()),'hold')
    def test_capacity_classification(self):
        err=types.SimpleNamespace(status=500,message='Out of host capacity.')
        self.assertTrue(launcher.is_capacity_error(err))
        err.message='some ambiguous internal error'
        self.assertFalse(launcher.is_capacity_error(err))

if __name__=='__main__': unittest.main()
