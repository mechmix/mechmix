"""Generated, non-customer OTDR examples for portable self-tests."""
import math
import pathlib
import struct
import zlib
from check_converter import make_drawing

def make_sor(path):
    def text(s):return s.encode()+b'\0'
    gen=b'GenParams\0EN'+text('DEMO')+text('Fiber01')+struct.pack('<HH',652,1550)+text('Test A')+text('Test B')+b'\0BC'+struct.pack('<ii',0,0)+text('Self-test')+b'\0'
    sup=b'SupParams\0'+b''.join(text(s) for s in ['Demo supplier','Demo OTDR','DEMO-1','Demo module','DEMO-2','1.0',''])
    fixed=b'FxdParams\0'+struct.pack('<I2sHiiHHIIIHIH IiiHhHHHH2siiii'.replace(' ',''),1700000000,b'mt',15500,0,0,1,30,100000,1000,146833,819,10,10,500000,0,0,0,1000,0,20,40000,5000,b'ST',0,0,0,0)
    key=b'KeyEvents\0'+struct.pack('<HiiiHii',0,0,0,0,0,0,0)
    pts=b'DataPts\0'+struct.pack('<IHIH',1000,1,1000,1000)+b''.join(struct.pack('<H',20000+i*5) for i in range(1000))
    blocks=[('GenParams',gen),('SupParams',sup),('FxdParams',fixed),('KeyEvents',key),('DataPts',pts)]
    size=12+sum(len(n)+7 for n,_ in blocks)
    mapping=b'Map\0'+struct.pack('<HIH',200,size,len(blocks)+1)+b''.join(text(n)+struct.pack('<HI',200,len(b)) for n,b in blocks)
    pathlib.Path(path).write_bytes(mapping+b''.join(b for _,b in blocks))

def make_trc(path,bidirectional=False):
    ior=1.468325;period=3.125e-9;step=period*299792458/(2*ior);origin=-100*step
    event=lambda cursor,status:{'Position':origin+cursor*step,'Length':step*4,'Type':3,'Status':status,'CursorA':cursor,'CursorB':cursor+4,'CursorAPosition':origin+cursor*step,'CursorBPosition':origin+(cursor+4)*step,'Loss':float('nan') if cursor in [0,900] else .05,'Reflectance':-45.0,'CurveLevel':20-cursor*.001}
    segment=lambda cursor,length:{'Position':origin+cursor*step,'Length':length*step,'Loss':.1}
    trace={'EventTable':{'Count':5,'Event0':event(0,8),'Event1':segment(0,100),'Event2':event(100,64),'Event3':segment(100,800),'Event4':event(900,128)},'SamplingPeriod':period,'ScaleFactor':1024.0,'RawSamples':b''.join(struct.pack('<H',int((20-i*.001)*1024)) for i in range(1200)),'FiberSectionCharacteristics':{'Count':1,'Section0':{'Ior':ior,'HelixFactor':0.0}},'ModuleInformation':{'ModelName':'Synthetic test module','SerialNumber':'DEMO'},'AcquisitionDatas':{'Count':1,'AcquisitionData0':{'ExactWavelength':1.55e-6}},'Wavelength':1.55e-6,'Date':'2024-01-01T12:00:00','Pulse':30e-9,'Duration':15,'Range':1000.0,'SpansLength':800*step,'SpansLoss':.25,'TotalOrl':35.0}
    tree={'OtdrData':{'Fibers':{'Count':1,'Fiber0':{'Identifier':'Demo fiber','Traces':{'Count':1,'Trace0':trace}}}}}
    if bidirectional:
        import copy
        reverse=copy.deepcopy(trace)
        reverse['SpansLoss']=.35
        reverse['EventTable']['Event2']['Loss']=-.03
        paired={}
        for i in range(5):
            ab=trace['EventTable']['Event'+str(i)];ba=reverse['EventTable']['Event'+str(i)]
            entry={'EventAB':ab,'EventBA':ba,'MeanPosition':ab['Position'],'MeanLength':ab['Length'],'MeanLoss':(ab['Loss']+ba['Loss'])/2}
            if 'Type' in ab:entry.update(Type=ab['Type'],Status=ab['Status'],HighestReflectance=-44.0)
            paired['Event'+str(i)]=entry
        paired['Count']=5
        tree={'OtdrData':{'BidirectionalFibers':{'Count':1,'BidirectionalFiber0':{'FiberAB':{'Identifier':'Demo bidirectional fiber'},'FiberBA':{'Identifier':'Demo bidirectional fiber'},'BidirectionalTraces':{'Count':1,'BidirectionalTrace0':{'TraceAB':trace,'TraceBA':reverse,'EventTable':paired,'Date':'2024-01-01T12:00:00'}}}}}}
    buf=bytearray(12)
    def add(name,value):
        off=len(buf);buf.extend(bytes(16));name_off=len(buf);buf.extend(name.encode()+b'\0')
        if isinstance(value,dict):
            children=[add(n,v) for n,v in value.items()];kind=0;payload=b''.join(struct.pack('<I',c) for c in children)
        elif isinstance(value,int):kind=1;payload=struct.pack('<i',value)
        elif isinstance(value,float):kind=3;payload=struct.pack('<d',value)
        elif isinstance(value,str):kind=4;payload=(value+'\0').encode('utf-16-le')
        else:kind=2;payload=value
        value_off=len(buf);buf.extend(payload);struct.pack_into('<IIII',buf,off,name_off,kind,len(payload),value_off)
        return off
    assert add('OtdrFile',tree)==12
    compressed=zlib.compress(buf);magic=b'AppReg Format Ex'
    header=magic+b'  \0\0'+struct.pack('<IIIII',2,len(buf),1,0,len(compressed))
    pathlib.Path(path).write_bytes(magic+bytes(24)+header+compressed)

def create_all(folder):
    folder=pathlib.Path(folder);folder.mkdir(parents=True,exist_ok=True)
    make_drawing(folder/'generated.vsdx');make_sor(folder/'generated.sor');make_trc(folder/'generated.trc');make_trc(folder/'generated.bdr',bidirectional=True)
    from media_fixture import create
    create(folder/'media-drawing.vsdx')
    import zipfile
    sentinel=folder/'deleted-shape-id.vsdx';make_drawing(sentinel)
    with zipfile.ZipFile(sentinel) as archive:parts={n:archive.read(n) for n in archive.namelist()}
    parts['visio/pages/page1.xml']=parts['visio/pages/page1.xml'].replace(b'</Shapes>',b'<Shape Del="1" MasterShape="9" ID="4294967295"/></Shapes>')
    with zipfile.ZipFile(sentinel,'w',zipfile.ZIP_DEFLATED) as archive:
        for n,data in parts.items():archive.writestr(n,data)
    return [folder/'generated.vsdx',folder/'generated.sor',folder/'generated.trc',folder/'generated.bdr',folder/'media-drawing.vsdx',sentinel]
