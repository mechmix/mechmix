"""Bounded reader for EXFO AppReg Format Ex TRC containers.
Container layout adapted from Hakendo/AnalizadorSOR's MIT-licensed reader.
See TRC-Reader-License.txt. Trace scaling/coordinates validated against stored
sample cursors; unsupported layouts fail rather than guessing coordinates.
"""
import math
import pathlib
import statistics
import struct
import zlib

MAGIC=b'AppReg Format Ex'
LIMIT=64*1024*1024

class Reader:
    def __init__(self,raw):
        if not raw.startswith(MAGIC):raise ValueError('Only EXFO AppReg Format Ex TRC files are currently supported.')
        header=raw.find(MAGIC,16,1024*1024)
        if header<0 or header+40>len(raw):raise ValueError('The EXFO container header is missing or truncated.')
        total=struct.unpack_from('<I',raw,header+24)[0]
        if not 28<=total<=LIMIT:raise ValueError('The expanded TRC file exceeds the supported size or is invalid.')
        pos=header+40;out=bytearray()
        while len(out)<total:
            if pos>len(raw):raise ValueError('Truncated TRC compression header.')
            size=struct.unpack_from('<I',raw,pos-4)[0]
            if not 0<size<=len(raw)-pos:raise ValueError('Invalid compressed TRC block length.')
            decoder=zlib.decompressobj()
            chunk=decoder.decompress(raw[pos:pos+size],total-len(out)+1)
            if len(chunk)>total-len(out) or not decoder.eof or decoder.unused_data:
                raise ValueError('Invalid or oversized compressed TRC block.')
            out.extend(chunk);pos+=size+4
        self.buf=bytes(out)
        if pos-4!=len(raw):raise ValueError('Unexpected trailing TRC data; this container variant is unsupported.')
    def record(self,off):
        b=self.buf
        if not isinstance(off,int) or off<0 or off+16>len(b):raise ValueError('Invalid TRC record offset.')
        name_off,kind,size,value_off=struct.unpack_from('<IIII',b,off)
        if name_off>=len(b) or value_off>len(b) or size>len(b)-value_off:raise ValueError('TRC record extends beyond its container.')
        end=b.find(b'\0',name_off,min(len(b),name_off+1024))
        if end<0:raise ValueError('Unterminated TRC record name.')
        return b[name_off:end].decode('latin1'),kind,b[value_off:value_off+size]
    def node(self,off):
        _,kind,value=self.record(off)
        if kind!=0 or len(value)%4 or len(value)>40000:raise ValueError('Invalid TRC record container.')
        out={}
        for (child,) in struct.iter_unpack('<I',value):
            name,kind,v=self.record(child)
            if name in out:raise ValueError('Duplicate fields in a TRC record.')
            if kind==0:out[name]=child
            elif kind==1 and len(v)==4:out[name]=struct.unpack('<i',v)[0]
            elif kind==3 and len(v)==8:out[name]=struct.unpack('<d',v)[0]
            elif kind==4:out[name]=v.decode('utf-16-le').rstrip('\0')
            else:out[name]=v
        return out
    def children(self,off,prefix):
        node=self.node(off);count=node.get('Count',0)
        if not isinstance(count,int) or not 0<=count<=10000:raise ValueError('Unsupported TRC record count.')
        return [self.node(node[prefix+str(i)]) for i in range(count)]

def finite(value,name,positive=False):
    if not isinstance(value,(float,int)) or not math.isfinite(value) or (positive and value<=0):
        raise ValueError('The TRC '+name+' is missing or invalid.')
    return value

def read_trc(source):
    raw=pathlib.Path(source).read_bytes()
    if len(raw)>100*1024*1024:raise ValueError('TRC file exceeds 100 MB.')
    try:
        r=Reader(raw);root=r.node(12);otdr=r.node(root['OtdrData']);traces=[]
        for fiber in r.children(otdr['Fibers'],'Fiber'):
            for trace in r.children(fiber['Traces'],'Trace'):
                if len(traces)>=128:raise ValueError('Too many traces in this TRC file.')
                traces.append(decode_trace(r,fiber,trace))
        if not traces:raise ValueError('No trace records were found.')
        return traces
    except (KeyError,IndexError,struct.error,zlib.error,UnicodeError) as error:
        raise ValueError('Could not read this TRC container: missing, damaged, or unsupported records.') from error

def decode_trace(r,fiber,trace):
    sections=r.children(trace['FiberSectionCharacteristics'],'Section')
    if len(sections)!=1 or abs(sections[0].get('HelixFactor',0))>1e-12:
        raise ValueError('Variable fiber index or helix compensation is not yet supported.')
    ior=finite(sections[0].get('Ior'),'group index',True)
    step=finite(trace.get('SamplingPeriod'),'sampling period',True)*299792458/(2*ior)
    scale=finite(trace.get('ScaleFactor'),'sample scale',True)
    raw_samples=trace.get('RawSamples',b'')
    if not isinstance(raw_samples,bytes) or len(raw_samples)%2 or not 4<=len(raw_samples)<=4000000:
        raise ValueError('Unsupported TRC sample array.')
    entries=r.children(trace['EventTable'],'Event');events=[e for e in entries if 'Type' in e];segments=[e for e in entries if 'Type' not in e]
    anchors=[];npts=len(raw_samples)//2
    for event in events:
        for cursor,position in [('CursorA','CursorAPosition'),('CursorB','CursorBPosition')]:
            n=event.get(cursor);distance=event.get(position)
            if isinstance(n,int) and 0<=n<npts and isinstance(distance,(int,float)) and math.isfinite(distance):
                anchors.append(distance-n*step)
        finite(event.get('Position'),'event position')
    if len(anchors)<2:raise ValueError('TRC coordinates cannot be validated against stored event cursors.')
    origin=statistics.median(anchors)
    if max(abs(a-origin) for a in anchors)>.02:
        raise ValueError('TRC event cursors disagree with the trace distance scale.')
    points=[(origin+i*step,value/scale) for i,(value,) in enumerate(struct.iter_unpack('<H',raw_samples))]
    # For this format the logarithmic samples match stored event CurveLevel.
    errors=[]
    for event in events:
        n=event.get('CursorA');level=event.get('CurveLevel')
        if isinstance(n,int) and 0<=n<npts and isinstance(level,(float,int)) and math.isfinite(level):errors.append(abs(points[n][1]-level))
    if not errors or statistics.median(errors)>1:
        raise ValueError('TRC sample scaling cannot be validated against recorded event levels.')
    custom={}
    if 'CustomIDList' in trace:
        custom={item.get('Name'):item.get('Value') for item in r.children(trace['CustomIDList'],'CustomID')}
    acq=r.children(trace['AcquisitionDatas'],'AcquisitionData') if 'AcquisitionDatas' in trace else []
    return {'fiber':fiber,'trace':trace,'module':r.node(trace['ModuleInformation']) if 'ModuleInformation' in trace else {},'job':r.node(trace['JobInformation']) if 'JobInformation' in trace else {},'events':events,'segments':segments,'points':points,'step':step,'origin':origin,'ior':ior,'custom':custom,'acquisition':acq}
