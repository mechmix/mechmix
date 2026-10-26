"""End-to-end portable checks with generated/public samples, no customer data."""
import ctypes
import json
import pathlib
import shutil
import tempfile
import time
from converter import convert,engine
from portable_runtime import APP_ROOT,cache_root
from test_fixtures import create_all

def run(output=None):
    output=pathlib.Path(output or cache_root()/'checks');output.mkdir(parents=True,exist_ok=True)
    cases=[];executable=engine();started=time.time()
    with tempfile.TemporaryDirectory(prefix='TeamPDF-selfcheck-') as tmp:
        cases=create_all(tmp)
        assets=APP_ROOT/'app/testassets'
        for name in ['example.vsd','example.vsdx']:
            if (assets/name).is_file():cases.append(assets/name)
        results=[]
        for source in cases:
            try:
                pdf=convert(source,output,executable)
                if not pdf.read_bytes().startswith(b'%PDF-'):raise ValueError('Invalid PDF signature')
                results.append({'input':source.name,'format':source.suffix,'passed':True,'output':str(pdf)})
                print('PASS: '+source.name,flush=True)
            except Exception as error:
                results.append({'input':source.name,'format':source.suffix,'passed':False,'error':str(error)})
                print('FAIL: '+source.name+' - '+str(error),flush=True)
        # Reject a broken drawing rather than claiming a successful conversion.
        broken=pathlib.Path(tmp)/'broken.vsdx';broken.write_bytes(b'not a drawing')
        try:convert(broken,output,executable);rejected=False
        except Exception:rejected=True
        results.append({'input':'broken.vsdx','passed':rejected,'check':'invalid file rejection'})
    is_admin=bool(ctypes.windll.shell32.IsUserAnAdmin()) if hasattr(ctypes,'windll') else None
    report={'passed':all(r['passed'] for r in results),'results':results,'elapsed_seconds':round(time.time()-started,2),'administrator':is_admin}
    (output/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    if not report['passed']:raise RuntimeError('The portable self-check failed. See '+str(output/'verification.json'))
    return report
