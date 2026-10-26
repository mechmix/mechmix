"""Local engine health test; does not read or upload user drawings."""
import pathlib
import platform
import tempfile
import zipfile
from converter import engine
from engine_support import record,run_engine,log_path


def make_drawing(path):
    v='http://schemas.microsoft.com/office/visio/2012/main'
    r='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    p='http://schemas.openxmlformats.org/package/2006/relationships'
    files={
    '[Content_Types].xml':'''<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/visio/document.xml" ContentType="application/vnd.ms-visio.drawing.main+xml"/><Override PartName="/visio/pages/pages.xml" ContentType="application/vnd.ms-visio.pages+xml"/><Override PartName="/visio/pages/page1.xml" ContentType="application/vnd.ms-visio.page+xml"/></Types>''',
    '_rels/.rels':'<Relationships xmlns="'+p+'"><Relationship Id="rId1" Type="http://schemas.microsoft.com/visio/2010/relationships/document" Target="visio/document.xml"/></Relationships>',
    'visio/document.xml':'<VisioDocument xmlns="'+v+'" xmlns:r="'+r+'"><DocumentSettings/><FaceNames><FaceName ID="0" Name="Arial"/></FaceNames><StyleSheets/><DocumentSheet/></VisioDocument>',
    'visio/_rels/document.xml.rels':'<Relationships xmlns="'+p+'"><Relationship Id="rId1" Type="http://schemas.microsoft.com/visio/2010/relationships/pages" Target="pages/pages.xml"/></Relationships>',
    'visio/pages/pages.xml':'<Pages xmlns="'+v+'" xmlns:r="'+r+'"><Page ID="0" NameU="Diagnostic" Name="Diagnostic"><PageSheet><Cell N="PageWidth" V="8.5"/><Cell N="PageHeight" V="11"/></PageSheet><Rel r:id="rId1"/></Page></Pages>',
    'visio/pages/_rels/pages.xml.rels':'<Relationships xmlns="'+p+'"><Relationship Id="rId1" Type="http://schemas.microsoft.com/visio/2010/relationships/page" Target="page1.xml"/></Relationships>',
    'visio/pages/page1.xml':'<PageContents xmlns="'+v+'"><Shapes><Shape ID="1" NameU="Rectangle" Type="Shape"><Cell N="PinX" V="4"/><Cell N="PinY" V="7"/><Cell N="Width" V="3"/><Cell N="Height" V="2"/><Cell N="LocPinX" V="1.5"/><Cell N="LocPinY" V="1"/><Cell N="FillForegnd" V="#205E4D"/><Cell N="FillPattern" V="1"/><Section N="Geometry" IX="0"><Row T="MoveTo" IX="1"><Cell N="X" V="0"/><Cell N="Y" V="0"/></Row><Row T="LineTo" IX="2"><Cell N="X" V="3"/><Cell N="Y" V="0"/></Row><Row T="LineTo" IX="3"><Cell N="X" V="3"/><Cell N="Y" V="2"/></Row><Row T="LineTo" IX="4"><Cell N="X" V="0"/><Cell N="Y" V="2"/></Row><Row T="LineTo" IX="5"><Cell N="X" V="0"/><Cell N="Y" V="0"/></Row></Section><Text>Converter diagnostic</Text></Shape></Shapes></PageContents>'}
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,value in files.items():archive.writestr(name,value)


def main():
    print('Checking the bundled conversion engine. No user drawings are read.\n',flush=True)
    record('=== CHECK CONVERTER ===\nOS: '+platform.platform()+'\nPython: '+platform.python_version())
    executable=engine()
    for name in ['soffice.com','soffice.bin','mergedlo.dll','sdlo.dll','vcruntime140.dll','vcruntime140_1.dll']:
        item=pathlib.Path(executable).parent/name
        record(name+': '+('present, '+str(item.stat().st_size)+' bytes' if item.is_file() else 'MISSING'))
    version=run_engine([executable,'--version'],timeout=30)
    print('Engine version:',version.stdout.strip() or version.stderr.strip() or 'No response',flush=True)
    with tempfile.TemporaryDirectory(prefix='TeamPDF-check-') as tmp:
        root=pathlib.Path(tmp)
        (root/'test.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="500" height="300"><rect x="20" y="20" width="400" height="220" fill="#205e4d"/><text x="40" y="130" fill="white">Converter diagnostic</text></svg>',encoding='utf-8')
        make_drawing(root/'test.vsdx')
        for extension in ['svg','vsdx']:
            out=root/('output-'+extension);out.mkdir()
            result=run_engine([executable,'-env:UserInstallation='+(root/('profile-'+extension)).as_uri(),'--headless','--nologo','--nodefault','--norestore','--convert-to','pdf:draw_pdf_Export','--outdir',str(out),str(root/('test.'+extension))])
            pdf=out/'test.pdf'
            ok=result.returncode==0 and pdf.is_file() and pdf.read_bytes().startswith(b'%PDF-')
            text=extension.upper()+' conversion: '+('PASS' if ok else 'FAIL')
            print(text,flush=True);record(text)
    print('\nPlease share this file with the converter developer:',flush=True)
    print(log_path(),flush=True)

if __name__=='__main__':
    try:main()
    except Exception as error:
        print('Check failed:',error,flush=True);record('Check failed: '+repr(error));print('Log:',log_path(),flush=True)
