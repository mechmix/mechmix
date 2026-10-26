"""Generated Visio example containing bitmap and Enhanced Metafile images."""
import pathlib,struct,sys,zipfile
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent.parent/'app'))
from check_converter import make_drawing

def create(path):
 make_drawing(path)
 with zipfile.ZipFile(path) as z:parts={n:z.read(n) for n in z.namelist()}
 # Valid minimal EMF: header, rectangle and EOF, generated from public format constants.
 emf=bytearray(108)
 struct.pack_into('<II',emf,0,1,108)
 struct.pack_into('<4i',emf,8,0,0,200,100);struct.pack_into('<4i',emf,24,0,0,5292,2646)
 struct.pack_into('<IIIIHH',emf,40,0x464D4520,0x10000,152,3,1,0)
 struct.pack_into('<4i',emf,72,1920,1080,508,286)
 struct.pack_into('<2i',emf,100,508000,286000)
 emf+=struct.pack('<II4i',43,24,10,10,190,90)+struct.pack('<IIIII',14,20,0,0,20)
 bmp=struct.pack('<2sIHHI',b'BM',70,0,0,54)+struct.pack('<IiiHHIIiiII',40,2,2,1,24,0,16,2835,2835,0,0)+bytes([0,0,255,0,255,0,0,0,255,0,0,255,255,255,0,0])
 r='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
 shapes=''
 for i,kind in [(2,'EnhMetaFile'),(3,'Bitmap')]:
  shapes+='<Shape ID="%s" Type="Foreign"><Cell N="PinX" V="4"/><Cell N="PinY" V="%s"/><Cell N="Width" V="3"/><Cell N="Height" V="1"/><Cell N="LocPinX" V="1.5"/><Cell N="LocPinY" V="0.5"/><ForeignData ForeignType="%s" MappingMode="8" ExtentX="200" ExtentY="100"><Rel xmlns:r="%s" r:id="rId%s"/></ForeignData></Shape>'%(i,i,kind,r,i)
 parts['visio/pages/page1.xml']=parts['visio/pages/page1.xml'].replace(b'</Shapes>',shapes.encode()+b'</Shapes>')
 parts['visio/pages/_rels/page1.xml.rels']=b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image1.emf"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image2.bmp"/></Relationships>'
 parts['visio/media/image1.emf']=bytes(emf);parts['visio/media/image2.bmp']=bmp
 parts['[Content_Types].xml']=parts['[Content_Types].xml'].replace(b'</Types>',b'<Default Extension="emf" ContentType="image/x-emf"/><Default Extension="bmp" ContentType="image/bmp"/></Types>')
 with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
  for n,data in parts.items():z.writestr(n,data)
if __name__=='__main__':create(sys.argv[1])
