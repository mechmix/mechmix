"""Run from the extracted embedded runtime under a standard Windows account."""
import argparse
import ctypes
import json
import os
import pathlib
import queue
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request

p=argparse.ArgumentParser();p.add_argument('--package',required=True);p.add_argument('--results',required=True);args=p.parse_args()
root=pathlib.Path(args.package).resolve();results=pathlib.Path(args.results).resolve();results.mkdir(parents=True,exist_ok=True)
assert os.name=='nt','This verification must run on native Windows'
assert not ctypes.windll.shell32.IsUserAnAdmin(),'Verification must run without administrator privileges'
os.environ['TEAM_PDF_AUTOTEST']='1'
log=results/'launcher.log'
command='cmd.exe /d /s /c ""'+str(root/'Start Converter.cmd')+'" --self-test --test-output "'+str(results/'self-test')+'""'
run=subprocess.run(command,cwd=root,capture_output=True,text=True,errors='replace',timeout=600)
log.write_text(run.stdout+'\n'+run.stderr,encoding='utf-8')
assert run.returncode==0,'Launcher failed; see launcher.log'
checks=json.loads((results/'self-test/verification.json').read_text())
assert checks['passed'] and checks['administrator'] is False
assert {r.get('format') for r in checks['results']} >= {'.vsd','.vsdx','.sor','.trc','.bdr'}
# Verify normal startup, upload endpoint, browser page and actual Downloads output.
process=subprocess.Popen([str(root/'runtime/python.exe'),'-B',str(root/'app/entry.py'),'--no-browser'],cwd=root,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace')
lines=queue.Queue();captured=[]
def collect():
 for line in process.stdout:lines.put(line)
threading.Thread(target=collect,daemon=True).start()
try:
 deadline=time.monotonic()+180;url=None
 while time.monotonic()<deadline:
  try:line=lines.get(timeout=1)
  except queue.Empty:
   if process.poll() is not None:raise RuntimeError('Server exited before opening: '+''.join(captured))
   continue
  captured.append(line)
  if line.strip().startswith('http://127.0.0.1:'):url=line.strip();break
 assert url,'No server URL received'
 page=urllib.request.urlopen(url,timeout=30).read();assert b'Drop your Visio' in page
 sys.path.insert(0,str(root/'app'))
 from test_fixtures import create_all
 from platform_tools import downloads_dir
 fixtures=results/'fixtures';generated=create_all(fixtures)
 for file in generated+[root/'app/testassets/example.vsd',root/'app/testassets/example.vsdx']:
  filename='CI test '+file.name
  response=urllib.request.urlopen(urllib.request.Request(url+'convert?name='+urllib.parse.quote(filename),data=file.read_bytes()),timeout=240)
  payload=json.load(response);dest=pathlib.Path(payload['folder']);pdf=dest/payload['filename']
  assert dest.resolve()==downloads_dir().resolve()
  assert pdf.read_bytes().startswith(b'%PDF-')
  shutil.copyfile(pdf,results/('HTTP-'+payload['filename']))
 # Check the optional local diagnostics on generated input, without uploading its raw log.
 from diagnose_visio import diagnose
 diagnostic=diagnose(fixtures/'media-drawing.vsdx',results/'diagnostic-smoke')
 assert len(diagnostic['attempts'])==5 and all(case['passed'] for case in diagnostic['attempts'])
 # Start a real Chromium browser separately against this still-running server.
 (results/'ui-url.txt').write_text(url,encoding='utf-8')
 (results/'server-ready.txt').write_text('ready')
 deadline=time.monotonic()+600
 while not (results/'ui-finished.txt').exists():
  if time.monotonic()>deadline:raise RuntimeError('Browser verification did not complete')
  time.sleep(.5)
 report={'passed':True,'administrator':False,'launcher':True,'default_downloads':True,'formats':['VSD','VSDX','SOR','TRC','BDR'],'browser_endpoint':True,'diagnostic_methods':[{'method':case['method'],'passed':case['passed']} for case in diagnostic['attempts']],'self_checks':[{'input':r['input'],'format':r.get('format'),'passed':r['passed']} for r in checks['results']]}
 (results/'native-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
finally:
 process.terminate()
 try:process.wait(timeout=15)
 except subprocess.TimeoutExpired:process.kill()
 (results/'server.log').write_text(''.join(captured),encoding='utf-8')
