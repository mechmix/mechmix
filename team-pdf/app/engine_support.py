"""Portable-engine launch environment and local troubleshooting output."""
import datetime
import os
import pathlib
import subprocess
import tempfile
from platform_tools import process_options

ROOT=pathlib.Path(__file__).resolve().parent.parent

def log_path():
    for folder in [ROOT/'Logs',pathlib.Path(tempfile.gettempdir())/'TeamPDF-Logs']:
        try:
            folder.mkdir(parents=True,exist_ok=True)
            return folder/'converter.log'
        except OSError:pass
    return None

def record(message):
    path=log_path()
    if path:
        try:
            if path.exists() and path.stat().st_size>2*1024*1024:path.write_text('Log restarted.\n',encoding='utf-8')
            with path.open('a',encoding='utf-8') as out:
                out.write('\n'+datetime.datetime.now().isoformat(timespec='seconds')+'\n'+message+'\n')
        except OSError:pass
    return path

def run_engine(arguments,timeout=180):
    executable=pathlib.Path(arguments[0]).resolve()
    env=os.environ.copy()
    # Match the portable launcher's DLL search path; isolate it from host Python.
    env['PATH']=str(executable.parent)+os.pathsep+env.get('PATH','')
    for key in ['PYTHONHOME','PYTHONPATH','URE_BOOTSTRAP','UNO_PATH']:
        env.pop(key,None)
    try:
        result=subprocess.run([str(executable)]+list(arguments[1:]),cwd=str(executable.parent),env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout,**process_options())
    except Exception as error:
        record('Engine start failed: '+repr(error)+'\nEngine: '+str(executable))
        raise RuntimeError('Windows could not start the conversion engine. Run Check Converter.cmd and share Logs/converter.log.') from error
    record('Engine: '+str(executable)+'\nArguments: '+repr(list(arguments[1:]))+'\nExit code: '+str(result.returncode)+' (0x%08X)'%(result.returncode&0xffffffff)+'\nSTDOUT:\n'+result.stdout+'\nSTDERR:\n'+result.stderr)
    return result

def failure_message(result):
    code=result.returncode&0xffffffff
    if code==0xC0000135:reason='The engine could not load a required Windows component.'
    elif code==0xC000007B:reason='Windows reported an incompatible engine dependency.'
    elif code==0xC0000005:reason='The conversion engine crashed.'
    else:
        lines=[line.strip() for line in (result.stderr+'\n'+result.stdout).splitlines() if line.strip()]
        reason=(lines[-1][:220] if lines else 'The engine returned no PDF or diagnostic text.')
    return 'Visio conversion failed: '+reason+' Run Check Converter.cmd; details are in Logs/converter.log.'
