"""Extract the bundled office engine to a short per-user cache, never Program Files."""
import hashlib
import json
import os
import pathlib
import shutil
import tempfile
import time
import zipfile

APP_ROOT=pathlib.Path(__file__).resolve().parent.parent

def native(path):
    value=str(path.resolve())
    if os.name=='nt' and not value.startswith('\\\\?\\'):
        return '\\\\?\\UNC\\'+value[2:] if value.startswith('\\\\') else '\\\\?\\'+value
    return value

def sha256(path):
    h=hashlib.sha256()
    with open(native(path),'rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def cache_root():
    base=pathlib.Path(os.environ.get('LOCALAPPDATA') or tempfile.gettempdir())
    return base/'TeamPDF'

def acquire_lock(path,timeout=600):
    # The OS releases this lock if first-run extraction is interrupted.
    descriptor=os.open(path,os.O_CREAT|os.O_RDWR)
    if os.fstat(descriptor).st_size==0:os.write(descriptor,b'0')
    deadline=time.monotonic()+timeout
    while True:
        try:
            os.lseek(descriptor,0,os.SEEK_SET)
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(descriptor,msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
            return descriptor
        except OSError:
            if time.monotonic()>deadline:
                os.close(descriptor)
                raise RuntimeError('Engine preparation is already running. Wait for the first converter window to finish.')
            time.sleep(.25)

def engine_directory():
    spec=json.loads((APP_ROOT/'office-manifest.json').read_text(encoding='utf-8'))
    target=cache_root()/('o-'+spec['sha256'][:12])
    def valid():
        try:
            if (target/'TeamPDF-ready.txt').read_text()!=spec['sha256']:return False
            return all(sha256(target/name)==expected for name,expected in spec['required'].items())
        except (OSError,ValueError):return False
    if valid():return target
    payload=APP_ROOT/'office.zip'
    if not payload.is_file() or sha256(payload)!=spec['sha256']:
        raise RuntimeError('The office bundle is incomplete or damaged. Download the complete ZIP and use Extract All again.')
    target.parent.mkdir(parents=True,exist_ok=True)
    lock=target.with_suffix('.lock')
    descriptor=acquire_lock(lock)
    if valid():
        os.close(descriptor)
        return target
    stage=pathlib.Path(tempfile.mkdtemp(prefix='office-',dir=str(target.parent)))
    try:
        print('Preparing the bundled conversion engine. This is needed only once.',flush=True)
        with zipfile.ZipFile(payload) as archive:
            entries=archive.infolist()
            for index,entry in enumerate(entries,1):
                if index%1000==0:
                    print('Preparing engine: %s / %s files'%(index,len(entries)),flush=True)
                rel=pathlib.PurePosixPath(entry.filename)
                if rel.is_absolute() or '..' in rel.parts or any(':' in part or '\\' in part for part in rel.parts):raise ValueError('Unsafe path in bundled engine.')
                out=stage.joinpath(*rel.parts)
                if entry.is_dir():os.makedirs(native(out),exist_ok=True);continue
                os.makedirs(native(out.parent),exist_ok=True)
                with archive.open(entry) as source,open(native(out),'wb') as dest:shutil.copyfileobj(source,dest)
        for name,expected in spec['required'].items():
            if sha256(stage/name)!=expected:raise RuntimeError('Engine integrity check failed: '+name)
        (stage/'TeamPDF-ready.txt').write_text(spec['sha256'])
        if target.exists():target.rename(target.with_name(target.name+'-old-'+str(time.time_ns())))
        stage.rename(target)
        return target
    finally:
        if stage.exists():shutil.rmtree(native(stage),ignore_errors=True)
        os.close(descriptor)
