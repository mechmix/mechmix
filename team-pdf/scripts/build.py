"""Reproducible no-install Windows bundle; only upstream public runtimes."""
import hashlib
import json
import os
import pathlib
import shutil
import sys
import time
import urllib.request
import zipfile

ROOT=pathlib.Path(__file__).resolve().parent.parent
DOWNLOADS=ROOT/'downloads';BUILD=ROOT/'build/TeamPDF';DIST=ROOT/'dist'
PY_URL='https://www.python.org/ftp/python/3.13.14/python-3.13.14-embed-amd64.zip'
LO_URL='https://download.documentfoundation.org/libreoffice/portable/26.2.4/LibreOfficePortable_26.2.4_MultilingualStandard.paf.exe'
PY_SHA='90b4e5b9898b72d744650524bff92377c367f44bd5fbd09e3148656c080ad907';LO_SHA='4bde93374aef4409243505b20d16561a4628ac7591457dd01fc6e1ccf571ba65'

def digest(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()

def download(url,name,expected=None):
 DOWNLOADS.mkdir(exist_ok=True);p=DOWNLOADS/name
 if p.exists() and (not expected or digest(p)==expected):
  print('Using cached '+name,flush=True);return p
 urls=[url]
 if url==LO_URL:
  suffix='/libreoffice/portable/26.2.4/LibreOfficePortable_26.2.4_MultilingualStandard.paf.exe'
  urls=['https://ftp.wayne.edu/tdf'+suffix,'https://mirror.fcix.net/tdf'+suffix,url]
 error=None
 for candidate in urls:
  partial=p.with_suffix(p.suffix+'.part')
  try:
   print('Downloading '+name+' from '+candidate,flush=True);started=time.monotonic();count=0;next_report=20*1024*1024
   with urllib.request.urlopen(candidate,timeout=30) as response,partial.open('wb') as stream:
    while True:
     block=response.read(1024*1024)
     if not block:break
     stream.write(block);count+=len(block)
     if count>=next_report:
      print('%s: %s MiB received'%(name,count//1024//1024),flush=True);next_report+=20*1024*1024
     if time.monotonic()-started>180:raise TimeoutError('Mirror download took too long')
   if expected and digest(partial)!=expected:raise ValueError('Download checksum mismatch: '+name)
   partial.replace(p);return p
  except Exception as e:
   error=e;partial.unlink(missing_ok=True);print('Download attempt failed: '+str(e),flush=True)
 raise RuntimeError('Could not download '+name) from error

def build(archive_tool,office_source=None):
 import subprocess
 if BUILD.exists():shutil.rmtree(BUILD)
 BUILD.mkdir(parents=True);DIST.mkdir(exist_ok=True)
 py=download(PY_URL,'python.zip',PY_SHA)
 lo=download(LO_URL,'office.paf.exe',LO_SHA)
 if office_source:
  office=pathlib.Path(office_source)
 else:
  extraction=ROOT/'build/office-extracted'
  extraction.mkdir(parents=True,exist_ok=True)
  subprocess.run([str(archive_tool),'x','-y','-o'+str(extraction),'-xr!help','-xr!dict-*','-xr!nlpsolver','-xr!wiki-publisher','-xr!$PLUGINSDIR',str(lo)],check=True)
  office=extraction/'App/libreoffice'
 if not (office/'program/soffice.com').is_file():raise ValueError('Office extraction is incomplete')
 shutil.copytree(ROOT/'app',BUILD/'app',ignore=shutil.ignore_patterns('__pycache__','testassets'))
 with zipfile.ZipFile(py) as archive:archive.extractall(BUILD/'runtime')
 (BUILD/'runtime/python313._pth').write_text('python313.zip\n.\n../app\n',encoding='ascii')
 payload=BUILD/'office.zip'
 with zipfile.ZipFile(payload,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
  for p in sorted(office.rglob('*')):
   if p.is_file():
    relative=p.relative_to(office)
    if relative.parts[0]=='help' or relative.parts[:2]==('share','extensions'):
     continue
    archive.write(p,relative.as_posix())
 required=['program/soffice.com','program/soffice.bin','program/mergedlo.dll','program/sdlo.dll','program/services/services.rdb','share/registry/draw.xcd']
 spec={'version':'26.2.4','sha256':digest(payload),'required':{name:digest(office/name) for name in required}}
 (BUILD/'office-manifest.json').write_text(json.dumps(spec,indent=2))
 assets=BUILD/'app/testassets';assets.mkdir()
 fixtures=[('Visio11FormatLine.vsd','example.vsd','c06587d91be2cd43050fb7e9fbc05b4c7e4cb708'),('color-boxes.vsdx','example.vsdx','ef8f6a1298baba23055c664e5794049dbca2f860')]
 for upstream,name,blob in fixtures:
  path=download('https://raw.githubusercontent.com/LibreOffice/libvisio/master/src/test/data/'+upstream,upstream)
  data=path.read_bytes();git_blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
  if git_blob!=blob:raise ValueError('Fixture changed upstream: '+upstream)
  shutil.copyfile(path,assets/name)
 license_path=download('https://raw.githubusercontent.com/LibreOffice/libvisio/master/COPYING.MPL','libvisio-MPL.txt')
 shutil.copyfile(license_path,assets/'LICENSE.txt')
 (assets/'SOURCES.txt').write_text('Public test examples from https://github.com/LibreOffice/libvisio/tree/master/src/test/data . MPL-2.0 license included. No customer files.\n')
 launcher='''@echo off\r
setlocal DisableDelayedExpansion\r
title Team PDF Converter - Keep this window open\r
if not exist "%~dp0runtime\\python.exe" goto missing\r
"%~dp0runtime\\python.exe" -B "%~dp0app\\entry.py" %*\r
if errorlevel 1 goto failed\r
exit /b 0\r
:missing\r
echo Extract the complete ZIP before starting the converter.\r
:failed\r
echo The converter could not complete its startup checks.\r
if not "%TEAM_PDF_AUTOTEST%"=="1" pause\r
exit /b 1\r
'''
 (BUILD/'Start Converter.cmd').write_bytes(launcher.encode('ascii'))
 (BUILD/'Check Converter.cmd').write_bytes(b'@echo off\r\ncall "%~dp0Start Converter.cmd" --self-test\r\npause\r\n')
 shutil.copyfile(ROOT/'README.md',BUILD/'READ ME FIRST.txt')
 components={'version':'2.1','python':{'url':PY_URL,'sha256':PY_SHA,'license':'runtime/LICENSE.txt'},'office':{'url':LO_URL,'sha256':LO_SHA,'source':'https://download.documentfoundation.org/libreoffice/src/26.2.4/','license':'office.zip -> license.txt'},'other_licenses':['app/OTDR-Reader-License.txt','app/TRC-Reader-License.txt','app/testassets/LICENSE.txt']}
 (BUILD/'COMPONENTS.json').write_text(json.dumps(components,indent=2))
 package=DIST/'TeamPDF-Windows-Portable-v2.1.zip'
 with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
  for p in sorted(BUILD.rglob('*')):
   if p.is_file():
    name=(pathlib.Path('TeamPDF')/p.relative_to(BUILD)).as_posix()
    if len(name)>80:raise ValueError('Outer package path is too long: '+name)
    archive.write(p,name,compress_type=zipfile.ZIP_STORED if p.name in ['office.zip','python313.zip'] else zipfile.ZIP_DEFLATED)
 with zipfile.ZipFile(package) as archive:
  if archive.testzip():raise ValueError('Package ZIP integrity failed')
 (DIST/'TeamPDF-Windows-Portable-v2.1.sha256.txt').write_text(digest(package)+'  '+package.name+'\n')
 print('BUILT: '+str(package),flush=True)

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--7zip',dest='archive_tool',required=True);p.add_argument('--office-source');args=p.parse_args();build(args.archive_tool,args.office_source)
