"""PDF reports from validated EXFO TRC records; no vendor pass/fail inference."""
import math
import pathlib
import textwrap
from sor_report import PDF,header,graph
from trc_reader import read_trc

def number(value,decimals=3,unit=''):
    if not isinstance(value,(float,int)) or not math.isfinite(value):return 'Not recorded'
    return ('%.*f'%(decimals,value))+unit

def footer(pdf,page):
    pdf.line(42,42,570,42)
    pdf.text(42,26,'TRC data report | Recorded measurements; no pass/fail assessment',8)
    pdf.text(535,26,page,9)

def create_report(source,output):
    traces=read_trc(source);pdf=PDF();filename=pathlib.Path(source).name;page=0
    for index,item in enumerate(traces,1):
        t=item['trace'];f=item['fiber'];events=item['events'];points=item['points'];custom=item['custom'];module=item['module'];job=item['job']
        label=(f.get('Identifier') or custom.get('Fiber ID') or 'Unidentified fiber')+' / '+number(t.get('Wavelength',0)*1e9,0,' nm')
        context=filename+' | Trace %s of %s | %s'%(index,len(traces),label)
        page+=1;header(pdf,context,'TRC trace overview')
        pairs=[('FIBER / WAVELENGTH',label),('MODULE',module.get('ModelName') or 'Not recorded'),('STORED SPAN LENGTH',number(t.get('SpansLength'),3,' m')),('STORED SPAN LOSS / ORL',number(t.get('SpansLoss'))+' / '+number(t.get('TotalOrl'),3,' dB'))]
        for n,(caption,value) in enumerate(pairs):
            x=42+(n%2)*270;y=650-(n//2)*48
            pdf.text(x,y,caption,8,True,(.4,.48,.43))
            for j,line in enumerate(textwrap.wrap(str(value),38)[:2]):pdf.text(x,y-17-j*12,line,11,True)
        marks=[{'distance_of_travel':e['Position'],'event_number':n} for n,e in enumerate(events,1)]
        graph(pdf,points,marks,points[-1][0]/1000,359,'Full recorded trace',xmin=points[0][0]/1000,axis='Stored distance position (km)')
        span_end=max([e['Position']/1000 for e in events if e.get('Status',0)&0x80]+[e['Position']/1000 for e in events]+[0])
        zoom=min(points[-1][0]/1000,max(.5,span_end*1.1))
        graph(pdf,points,marks,zoom,118,'Fiber span detail',xmin=max(0,points[0][0]/1000),axis='Stored distance position (km)')
        pdf.text(42,63,'Stored coordinates are retained, including negative launch positions. Levels are relative dB.',8)
        footer(pdf,page);pdf.page()
        page+=1;header(pdf,context,'Recorded events & sections');y=647
        pdf.text(42,y,'Point events',12,True);y-=25
        def event_header(y):
            for x,label in [(42,'#'),(67,'Position (km)'),(160,'Vendor type / flags'),(320,'Loss (dB)'),(415,'Reflectance (dB)')]:pdf.text(x,y,label,8,True)
            pdf.line(42,y-8,570,y-8)
        event_header(y);y-=28
        for n,e in enumerate(events,1):
            if y<100:
                footer(pdf,page);pdf.page();page+=1;header(pdf,context,'Point events (continued)');y=647;event_header(y);y-=28
            flags=[]
            if e.get('Status',0)&0x40:flags.append('Start')
            if e.get('Status',0)&0x80:flags.append('End')
            kind='Type %s / 0x%02X'%(e.get('Type','?'),e.get('Status',0))
            if flags:kind+=' '+','.join(flags)
            pdf.text(42,y,n,9);pdf.text(67,y,number(e['Position']/1000,4),9);pdf.text(160,y,kind,8);pdf.text(320,y,number(e.get('Loss')),9);pdf.text(415,y,number(e.get('Reflectance')),9)
            pdf.line(42,y-9,570,y-9);y-=23
        y-=20
        if y<200:
            footer(pdf,page);pdf.page();page+=1;header(pdf,context,'Recorded fiber sections');y=647
        pdf.text(42,y,'Fiber sections',12,True);y-=24
        def section_header(y):
            for x,label in [(42,'#'),(67,'Start (km)'),(163,'Length (m)'),(286,'Loss (dB)'),(407,'Calculated dB/km')]:pdf.text(x,y,label,8,True)
            pdf.line(42,y-7,570,y-7)
        section_header(y);y-=26
        for n,e in enumerate(item['segments'],1):
            if y<100:
                footer(pdf,page);pdf.page();page+=1;header(pdf,context,'Fiber sections (continued)');y=647;section_header(y);y-=26
            length=e.get('Length');loss=e.get('Loss');slope=loss/length*1000 if isinstance(length,(float,int)) and length>0 and isinstance(loss,(float,int)) else None
            pdf.text(42,y,n,9);pdf.text(67,y,number(e.get('Position',float('nan'))/1000,4),9);pdf.text(163,y,number(length),9);pdf.text(286,y,number(loss),9);pdf.text(407,y,number(slope),9);y-=18
        pdf.text(42,max(60,y-13),'Section attenuation is calculated from stored loss / length. Unset values remain "Not recorded".',8)
        footer(pdf,page);pdf.page()
        page+=1;header(pdf,context,'Acquisition settings');y=648
        acq=item['acquisition'];exact=acq[0].get('ExactWavelength')*1e9 if acq and acq[0].get('ExactWavelength') else None
        settings=[('File format','EXFO AppReg Format Ex'),('Test date (as stored)',t.get('Date') or 'Not recorded'),('Fiber ID',f.get('Identifier') or custom.get('Fiber ID') or 'Not recorded'),('Cable ID',f.get('Cable') or custom.get('Cable ID') or 'Not recorded'),('Location A / B',(f.get('LocationA') or '-')+' / '+(f.get('LocationB') or '-')),('Module / serial',(module.get('ModelName') or '-')+' / '+(module.get('SerialNumber') or '-')),('Nominal / exact wavelength',number(t.get('Wavelength',0)*1e9,1)+' / '+number(exact,1,' nm')),('Pulse / duration',number(t.get('Pulse',0)*1e9,1,' ns')+' / '+str(t.get('Duration','Not recorded'))+' s'),('Group index',number(item['ior'],6)),('Sample interval / count',number(item['step'],6,' m')+' / '+str(len(points))),('Stored trace origin',number(item['origin'],6,' m')),('Nominal acquisition range',number(t.get('Range'),3,' m')),('Job identifier',job.get('Identifier') or 'Not recorded'),('Job user / customer',(job.get('UserNameA') or '-')+' / '+(job.get('CustomerName') or '-')),('Stored span length / loss',number(t.get('SpansLength'),3,' m')+' / '+number(t.get('SpansLoss'),3,' dB')),('Stored total ORL',number(t.get('TotalOrl'),3,' dB'))]
        for label,value in settings:
            if y<200:
                footer(pdf,page);pdf.page();page+=1;header(pdf,context,'Settings (continued)');y=648
            pdf.text(42,y,label,9,True)
            lines=textwrap.wrap(str(value),57) or ['Not recorded']
            for j,line in enumerate(lines):pdf.text(240,y-12*j,line,9)
            y-=max(24,len(lines)*12+6)
        y-=10
        notes=['Scope: EXFO AppReg Format Ex with a uniform fiber index. Other TRC families are not supported.', 'The plot uses stored RawSamples / ScaleFactor. Distance spacing is derived from SamplingPeriod and group index; the origin is checked against stored event cursor positions.', 'Vendor event type and status codes are reproduced without guessing their full meaning. Start/End flags are shown when present. NaN and missing measurements are not replaced by zero.', 'Dates are reproduced as stored; this file does not specify a timezone. No compliance, pass/fail, or vendor calibration assessment is performed.']
        for note in notes:
            lines=textwrap.wrap(note,99)
            if y-len(lines)*11<58:
                footer(pdf,page);pdf.page();page+=1;header(pdf,context,'Report notes');y=648
            for line in lines:pdf.text(42,y,line,8);y-=11
            y-=7
        footer(pdf,page);pdf.page()
    pdf.save(output)
    return traces
