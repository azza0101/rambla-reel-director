"""Run unittest and the repository's plain test functions without extra dependencies."""
import sys,unittest,inspect
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'tests'/'unit'))
sys.path.insert(0,str(root/'worker'))
suite=unittest.defaultTestLoader.discover(str(root/'tests'/'unit'),pattern='test_*.py')
for module in list(sys.modules.values()):
 path=getattr(module,'__file__',None)
 if path and Path(path).parent==root/'tests'/'unit':
  for name,fn in inspect.getmembers(module,inspect.isfunction):
   if name.startswith('test_') and not inspect.signature(fn).parameters:suite.addTest(unittest.FunctionTestCase(fn))
result=unittest.TextTestRunner(verbosity=1).run(suite)
sys.exit(not result.wasSuccessful())
