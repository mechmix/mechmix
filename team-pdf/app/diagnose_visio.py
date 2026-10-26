"""Local-only diagnostics for one failing drawing; no uploads or installed changes."""
import argparse,hashlib,json,os,pathlib,shutil,subprocess,tempfile,time,zipfile
from converter import engine
from engine_support import run_engine
from portable_runtime import cache_root

def choose_file():
    script="Add-Type -AssemblyName System.Windows.Forms; $d=New-Object System.Windows.Forms.OpenFileDialog; $d.Filter='Visio drawings (*.vsdx)|*.vsdx'; if($d.ShowDialog() -eq 'OK'){[Console]::WriteLine($d.FileName)}"
    result=subprocess.run(['powershell.exe','-NoProfile','-STA','-Command',script],capture_output=True,text=True)
    if result.returncode:raise RuntimeError('Could not open the file picker. Drag the VSDX onto Run Visio Diagnostics.cmd instead.')
    return result.stdout.strip()

def diagnose(source,output=None,executable=None):
    source=pathlib.Path(source).resolve()
    if source.suffix.lower()!='.vsdx':raise ValueError('Choose the failing .vsdx drawing.')
    data=source.read_bytes()
    output=pathlib.Path(output or pathlib.Path(__file__).resolve().parent.parent/'Logs/Visio-Diagnostics')
    output.mkdir(parents=True,exist_ok=True)
    report={'tool':'Visio diagnostics 1','source_name':source.name,'source_bytes':len(data),'source_sha256':hashlib.sha256(data).hexdigest(),'attempts':[],'local_only':True}
    with zipfile.ZipFile(source) as archive:
        report['zip_crc_error']=archive.testzip()
        report['zip_entries']=len(archive.infolist())
        report['largest_entry_bytes']=max(i.file_size for i in archive.infolist())
        report['has_visio_document']='visio/document.xml' in archive.namelist()
    if report['zip_crc_error'] or not report['has_visio_document']:raise ValueError('The uploaded drawing is damaged or has no Visio document.')
    base=cache_root()/'diagnostics';base.mkdir(parents=True,exist_ok=True)
    executable=executable or engine()
    cases=[('explicit-original',True,False,{}),('automatic-original',False,False,{}),('automatic-repacked',False,True,{}),('software-rendering',False,False,{'SAL_SKIA':'raster'}),('legacy-emf-rendering',False,False,{'SAL_SKIA':'raster','EMF_PLUS_DISABLE':'1'}),('compatible-shape-ids',True,False,{})]
    with tempfile.TemporaryDirectory(prefix='diag-',dir=base) as tmp:
        root=pathlib.Path(tmp)
        original=root/'drawing.vsdx';original.write_bytes(data)
        repacked=root/'repacked.vsdx'
        with zipfile.ZipFile(original) as source_zip,zipfile.ZipFile(repacked,'w',zipfile.ZIP_STORED) as dest_zip:
            for entry in source_zip.infolist():dest_zip.writestr(entry.filename,source_zip.read(entry.filename))
        from vsdx_compat import normalize_shape_ids
        compatible=root/'compatible.vsdx';shutil.copyfile(original,compatible)
        report['normalized_shape_ids']=normalize_shape_ids(compatible)
        # Prove repacking changed only ZIP storage, never the document bytes.
        with zipfile.ZipFile(original) as a,zipfile.ZipFile(repacked) as b:
            assert a.namelist()==b.namelist()
            assert all(a.read(n)==b.read(n) for n in a.namelist())
        for index,(label,explicit,repack,overrides) in enumerate(cases):
            print('Checking '+label+' ...',flush=True)
            case=root/label;case.mkdir();out=case/'pdf';out.mkdir();input_path=compatible if label=='compatible-shape-ids' else repacked if repack else original
            arguments=[executable,'-env:UserInstallation='+(case/'profile').as_uri(),'--headless','--nologo','--nodefault','--norestore']
            if explicit:arguments.append('--infilter=Visio Document')
            arguments+=['--convert-to','pdf:draw_pdf_Export','--outdir',str(out),input_path.as_uri()]
            previous={key:os.environ.get(key) for key in overrides};started=time.monotonic()
            try:
                os.environ.update(overrides)
                result=run_engine(arguments,timeout=90)
                pdf=out/(input_path.stem+'.pdf');passed=result.returncode==0 and pdf.is_file() and pdf.read_bytes().startswith(b'%PDF-')
                item={'method':label,'passed':passed,'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr}
                if passed:shutil.copyfile(pdf,output/(label+'.pdf'))
            except Exception as error:item={'method':label,'passed':False,'error':str(error)}
            finally:
                for key,value in previous.items():
                    if value is None:os.environ.pop(key,None)
                    else:os.environ[key]=value
            item['elapsed_seconds']=round(time.monotonic()-started,2);report['attempts'].append(item)
            (output/'diagnostic-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
            print(('PASS ' if item['passed'] else 'FAIL ')+label,flush=True)
    print('\nDiagnostics complete. Share this report in the private chat:\n'+str(output/'diagnostic-report.json'),flush=True)
    print('Any PDFs here are diagnostic samples. Check their layout before using them.',flush=True)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('file',nargs='?');args=p.parse_args()
    try:
        selected=args.file or choose_file()
        if selected:diagnose(selected)
    except Exception as error:print('Diagnostic stopped: '+str(error),flush=True);raise SystemExit(1)
