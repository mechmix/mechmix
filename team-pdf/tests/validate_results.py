import argparse,json,pathlib
from pypdf import PdfReader
import pypdfium2 as pdfium
p=argparse.ArgumentParser();p.add_argument('folder');args=p.parse_args();root=pathlib.Path(args.folder)
report=json.loads((root/'native-verification.json').read_text());assert report['passed'] and report['administrator'] is False
files=list(root.rglob('*.pdf'));assert len(files)>=10
for path in files:
 reader=PdfReader(path);assert len(reader.pages)>0
 document=pdfium.PdfDocument(str(path));image=document[0].render(scale=1).to_pil().convert('RGB')
 pixels=list(image.getdata());nonwhite=sum(min(pixel)<230 for pixel in pixels)
 assert nonwhite>100,'Blank-looking PDF: '+str(path)
 image.save(root/(path.stem+'-preview.png'));document.close()
print('Validated',len(files),'nonempty PDFs and rendered previews from native Windows conversions.')
