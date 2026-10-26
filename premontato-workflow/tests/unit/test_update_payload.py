import unittest,tempfile,subprocess,zipfile,hashlib,sys,os
from pathlib import Path
ROOT=Path(__file__).parents[2]
PS=Path(os.environ.get('SystemRoot','C:/Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe'
@unittest.skipUnless(PS.exists(),'Windows PowerShell required')
class UpdatePayloadTests(unittest.TestCase):
 def validate(self,extra):
  with tempfile.TemporaryDirectory() as folder:
   target=Path(folder)/'com.rambla.premontato';target.mkdir();(target/'WorkflowIntegration.node').write_bytes(b'private test sentinel')
   archive=Path(folder)/'update.zip'
   with zipfile.ZipFile(archive,'w') as z:
    for name in ['plugin/main.js','plugin/updater.js','plugin/update.ps1','plugin/package.json','worker/protocol.py','runtime/python.exe','runtime/THIRD_PARTY_NOTICES.txt',*extra]:z.writestr(name,'fixture')
   sha=hashlib.sha256(archive.read_bytes()).hexdigest()
   result=subprocess.run([str(PS),'-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(ROOT/'plugin/update.ps1'),'-PluginRoot',str(target),'-ArchivePath',str(archive),'-ExpectedSha256',sha,'-Version','0.10.2','-ValidateOnly'],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=45)
   return result.returncode,result.stdout+result.stderr
 def test_accepts_new_and_future_flat_python_modules(self):
  code,output=self.validate(['worker/active_speaker.py','worker/asd_features.py','worker/automatic_editor.py','worker/local_audio.py','worker/future_algorithm.py']);self.assertEqual(code,0,output)
 def test_accepts_day_catalog_and_performance_panel_modules(self):
  code,output=self.validate(['plugin/day_catalog_resolve.js','plugin/day_catalog_store.js','plugin/day_catalog_session.js','plugin/day_catalog_ipc.js','plugin/day_catalog_ui.js','plugin/performance.js','worker/scene_catalog.py']);self.assertEqual(code,0,output)
 def test_still_rejects_traversal_executables_and_sdk_with_useful_error(self):
  for name in ['worker/../escape.py','worker/evil.ps1','plugin/WorkflowIntegration.node']:
   code,output=self.validate([name]);self.assertNotEqual(code,0);self.assertNotIn('FullyQualifiedErrorId : ScriptHalted',output)
if __name__=='__main__':unittest.main()
