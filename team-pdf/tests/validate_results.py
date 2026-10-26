import argparse,json,pathlib
from pypdf import PdfReader
import pypdfium2 as pdfium
p=argparse.ArgumentParser();p.add_argument('folder');args=p.parse_args();root=pathlib.Path(args.folder)
report=json.loads((root/'native-verification.json').read_text());assert report['passed'] and report['administrator'] is False
files=list(root.rglob('*.pdf'));assert len(files)>=12
for path in files:
 reader=PdfReader(path);assert len(reader.pages)>0
 document=pdfium.PdfDocument(str(path));image=document[0].render(scale=1).to_pil().convert('RGB')
 pixels=list(image.getdata());nonwhite=sum(min(pixel)<230 for pixel in pixels)
 assert nonwhite>100,'Blank-looking PDF: '+str(path)
 image.save(root/(path.stem+'-preview.png'));document.close()
print('Validated',len(files),'nonempty PDFs and rendered previews from native Windows conversions.')

combined='\n'.join(page.extract_text() or '' for file in files if 'generated (4)' in file.name for page in PdfReader(file).pages)
assert 'Bidirectional OTDR results' in combined and 'BDR A to B trace' in combined and 'BDR B to A trace' in combined
assert '0.010' in combined and '-0.030' in combined, 'Stored mean and reverse loss must survive PDF conversion'

for file in files:
 if "media-drawing" in file.name:
  assert len(PdfReader(file).pages[0].images)>0, "Embedded bitmap missing from Visio PDF"
