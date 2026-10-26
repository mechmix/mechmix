"""EXFO AppReg BDR reports with stored paired events and both source traces."""
import struct
import zlib
import textwrap
import pathlib
from sor_report import PDF,header
from trc_report import number,create_report as trace_report
from trc_reader import Reader,decode_trace,finite

def read_bdr(source):
    raw=pathlib.Path(source).read_bytes()
    if len(raw)>100*1024*1024:raise ValueError('BDR file exceeds 100 MB.')
    try:
        r=Reader(raw);otdr=r.node(r.node(12)['OtdrData']);pairs=[]
        fibers=r.children(otdr['BidirectionalFibers'],'BidirectionalFiber')
        for fiber in fibers:
            for bidir in r.children(fiber['BidirectionalTraces'],'BidirectionalTrace'):
                if len(pairs)>=64:raise ValueError('Too many bidirectional traces in this BDR file.')
                directions=[]
                for direction in ['AB','BA']:
                    item=decode_trace(r,r.node(fiber['Fiber'+direction]),r.node(bidir['Trace'+direction]))
                    item['direction']='A to B' if direction=='AB' else 'B to A'
                    directions.append(item)
                if abs(directions[0]['trace']['Wavelength']-directions[1]['trace']['Wavelength'])>1e-10:
                    raise ValueError('BDR paired wavelengths do not agree.')
                entries=[]
                for e in r.children(bidir['EventTable'],'Event'):
                    finite(e.get('MeanPosition'),'BDR mean event position')
                    finite(e.get('MeanLength'),'BDR mean event length')
                    entry=dict(e)
                    for direction in ['AB','BA']:
                        key='Event'+direction
                        # An unmatched event may have no reference. Do not replace it with zero loss.
                        entry[direction]=r.node(e[key]) if key in e else {}
                    entries.append(entry)
                if not entries:raise ValueError('This BDR has no paired event table.')
                pairs.append({'directions':directions,'entries':entries,'date':bidir.get('Date','Not recorded')})
        if not pairs:raise ValueError('No bidirectional traces were found in this BDR file.')
        return pairs
    except (KeyError,IndexError,UnicodeError,struct.error,zlib.error) as error:
        raise ValueError('This BDR layout is incomplete or unsupported.') from error

def create_report(source,output):
    pairs=read_bdr(source);pdf=PDF();page=0;traces=[]
    def finish():
        pdf.line(42,42,570,42)
        pdf.text(42,26,'BDR data report | Stored results; no pass/fail assessment',8)
        pdf.text(535,26,page,9);pdf.page()
    for index,pair in enumerate(pairs,1):
        directions=pair['directions'];traces.extend(directions)
        wavelength=number(directions[0]['trace'].get('Wavelength',0)*1e9,0,' nm')
        context=pathlib.Path(source).name+' | Pair %s of %s | %s'%(index,len(pairs),wavelength)
        page+=1;header(pdf,context,'Bidirectional OTDR results');y=648
        for label,value in [('Wavelength',wavelength),('Analysis date (as stored)',pair['date']),('Fiber ID',directions[0]['fiber'].get('Identifier') or 'Not recorded'),('Span A to B / B to A',number(directions[0]['trace'].get('SpansLength'),3,' m')+' / '+number(directions[1]['trace'].get('SpansLength'),3,' m')),('Span loss A to B / B to A',number(directions[0]['trace'].get('SpansLoss'),3,' dB')+' / '+number(directions[1]['trace'].get('SpansLoss'),3,' dB'))]:
            pdf.text(42,y,label,9,True)
            lines=textwrap.wrap(str(value),55)
            for j,line in enumerate(lines):pdf.text(240,y-j*12,line,9)
            y-=max(25,len(lines)*12+8)
        for kind,title in [(True,'Paired point events'),(False,'Paired fiber sections')]:
            entries=[e for e in pair['entries'] if ('Type' in e)==kind]
            if y<190:finish();page+=1;header(pdf,context,title);y=648
            pdf.text(42,y,title,12,True);y-=25
            def columns():
                for x,label in [(42,'#'),(65,'Mean km'),(145,'A>B dB'),(224,'B>A dB'),(303,'Mean dB'),(386,'Max refl. dB' if kind else 'Mean m'),(481,'Type / flags')]:pdf.text(x,y,label,8,True)
                pdf.line(42,y-8,570,y-8)
            columns();y-=29
            for n,e in enumerate(entries,1):
                if y<100:
                    finish();page+=1;header(pdf,context,title+' (continued)');y=648;columns();y-=29
                values=[(42,str(n)),(65,number(e['MeanPosition']/1000,4)),(145,number(e['AB'].get('Loss'))),(224,number(e['BA'].get('Loss'))),(303,number(e.get('MeanLoss'))),(386,number(e.get('HighestReflectance') if kind else e.get('MeanLength'))),(481,('%s / 0x%02X'%(e.get('Type'),e.get('Status',0))) if kind else '-')]
                for x,value in values:pdf.text(x,y,value,8)
                pdf.line(42,y-9,570,y-9);y-=23
            y-=22
        notes=['Mean positions, lengths, losses and highest reflectances are reproduced from the stored bidirectional table.', 'A>B and B>A columns use the paired directional event references. Positions retain the stored mean axis.', 'Missing or unset values show Not recorded. Negative directional losses are retained. No pass/fail is inferred.', 'Detailed directional plots and event tables follow; each plot uses its own acquisition distance origin.']
        if y<125:finish();page+=1;header(pdf,context,'Bidirectional report notes');y=648
        for note in notes:
            for line in textwrap.wrap(note,99):pdf.text(42,y,line,8);y-=11
            y-=6
        finish()
    trace_report(source,output,traces=traces,pdf=pdf,page=page)
    return pairs
