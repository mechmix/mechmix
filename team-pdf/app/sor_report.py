"""SOR v2 single-trace PDF reports, using only the Python standard library.

Reader: Markus Juenemann's otdrparser (BSD-2-Clause; see included license).
No pass/fail assessment or proprietary vendor analysis is performed.
"""
import datetime
import io
import math
import pathlib
import textwrap
import otdrparser

class PDF:
    def __init__(self):
        self.pages=[]
        self.commands=[]
    def text(self,x,y,text,size=10,bold=False,color=(.12,.2,.18)):
        text=str(text).encode('cp1252','replace').decode('cp1252')
        text=text.replace('\\','\\\\').replace('(','\\(').replace(')','\\)').replace('\n',' ' ).replace('\r',' ')
        self.commands.append('%.3f %.3f %.3f rg BT /%s %.2f Tf 1 0 0 1 %.2f %.2f Tm (%s) Tj ET' % (*color,'F2' if bold else 'F1',size,x,y,text))
    def line(self,x1,y1,x2,y2,color=(.85,.89,.86),width=.6):
        self.commands.append('%.3f %.3f %.3f RG %.2f w %.2f %.2f m %.2f %.2f l S'%(*color,width,x1,y1,x2,y2))
    def page(self):
        self.pages.append('\n'.join(self.commands).encode('cp1252','replace'));self.commands=[]
    def save(self,path):
        if self.commands:self.page()
        objects=[b'',b'',b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>',b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>']
        kids=[]
        for stream in self.pages:
            pnum=len(objects)+1;cnum=pnum+1;kids.append('%d 0 R'%pnum)
            objects.append(('<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents %d 0 R >>'%cnum).encode())
            objects.append(('<< /Length %d >>\nstream\n'%len(stream)).encode()+stream+b'\nendstream')
        objects[0]=b'<< /Type /Catalog /Pages 2 0 R >>'
        objects[1]=('<< /Type /Pages /Count %d /Kids [%s] >>'%(len(kids),' '.join(kids))).encode()
        out=bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n');offsets=[0]
        for n,obj in enumerate(objects,1):
            offsets.append(len(out));out+=('%d 0 obj\n'%n).encode()+obj+b'\nendobj\n'
        start=len(out);out+=('xref\n0 %d\n0000000000 65535 f \n'%len(offsets)).encode()
        for offset in offsets[1:]:out+=('%010d 00000 n \n'%offset).encode()
        out+=('trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n'%(len(offsets),start)).encode()
        pathlib.Path(path).write_bytes(out)

def read_sor(source):
    raw=pathlib.Path(source).read_bytes()
    if len(raw)>100*1024*1024:raise ValueError('SOR file exceeds 100 MB.')
    try:
        fp=io.BytesIO(raw);mapping=otdrparser.parse_map_block(fp)
        if fp.tell()!=mapping['numbytes'] or mapping['numbytes']+sum(x['numbytes'] for x in mapping['maps'])!=len(raw):
            raise ValueError('Block lengths do not match the file size.')
        names=[x['name'] for x in mapping['maps']]
        if len(set(names))!=len(names):raise ValueError('Duplicate block names are unsupported.')
        data=otdrparser.parse2(io.BytesIO(raw))
        fixed=data['FxdParams'];pts=data['DataPts']
        if fixed['number_of_data_points']!=pts['number_of_data_points']:raise ValueError('Trace point counts disagree.')
        if len(pts['data_points'])<2:raise ValueError('The trace has too few samples.')
        return data
    except (ValueError,IndexError,KeyError,OverflowError) as error:
        raise ValueError('Could not read this SOR file: '+str(error)) from error

def header(pdf,filename,subtitle):
    pdf.text(42,752,'OTDR / FIBER TEST REPORT',10,True,(.16,.4,.3))
    pdf.text(42,720,subtitle,24,True)
    for i,line in enumerate(textwrap.wrap(filename,85)[:2]):pdf.text(42,699-i*13,line,10)
    pdf.line(42,674,570,674)

def footer(pdf,page):
    pdf.line(42,42,570,42)
    pdf.text(42,26,'SOR data report | Recorded measurements; no pass/fail assessment',8)
    pdf.text(535,26,str(page),9)

def graph(pdf,points,events,xmax,y,title,xmin=0,axis="Distance from trace origin (km)"):
    x=82;width=474;height=140
    shown=[p for p in points if xmin<=p[0]/1000<=xmax]
    if len(shown)<2:shown=points[:2]
    low=math.floor(min(p[1] for p in shown)/10)*10
    high=math.ceil(max(p[1] for p in shown)/10)*10
    if high==low:high=low+10
    pdf.text(42,y+height+28,title,12,True)
    pdf.text(42,y+height+12,'Relative trace level (dB)',8)
    for n in range(5):
        yy=y+height*n/4;value=low+(high-low)*n/4
        pdf.line(x,yy,x+width,yy);pdf.text(47,yy-3,'%g'%value,8)
    for n in range(6):
        xx=x+width*n/5;pdf.line(xx,y,xx,y+height)
        pdf.text(xx-9,y-14,'%.2f'%(xmin+(xmax-xmin)*n/5),8)
    pdf.text(235,y-29,axis,8)
    # Preserve minima and maxima within each bin so narrow reflective peaks survive.
    buckets={}
    for a,b in shown:
        bin_id=min(1199,int((a/1000-xmin)/(xmax-xmin)*1200));buckets.setdefault(bin_id,[]).append((a,b))
    reduced=[]
    for bucket in buckets.values():
        selected={bucket[0],bucket[-1],min(bucket,key=lambda p:p[1]),max(bucket,key=lambda p:p[1])}
        reduced.extend(sorted(selected))
    path=['q %.2f %.2f %.2f %.2f re W n .13 .43 .32 RG .55 w'%(x,y,width,height)]
    for n,(a,b) in enumerate(reduced):
        path.append('%.2f %.2f %s'%(x+(a/1000-xmin)/(xmax-xmin)*width,y+(b-low)/(high-low)*height,'m' if n==0 else 'l'))
    path.append('S Q');pdf.commands.append('\n'.join(path))
    label_lanes=[]
    for event in events:
        distance=event['distance_of_travel']/1000
        if xmin<=distance<=xmax:
            xx=x+(distance-xmin)/(xmax-xmin)*width;pdf.line(xx,y,xx,y+height,(.75,.4,.16),.7)
            lane=next((n for n,last in enumerate(label_lanes) if xx-last>20),len(label_lanes))
            if lane==len(label_lanes):label_lanes.append(xx)
            else:label_lanes[lane]=xx
            if lane<9:
                pdf.text(min(xx+3,540),y+height-12-lane*11,str(event['event_number']),8,True,(.7,.32,.1))

def create_report(source,output):
    data=read_sor(source);g=data.get('GenParams',{});s=data.get('SupParams',{});f=data['FxdParams'];k=data.get('KeyEvents',{});events=k.get('events',[]);pts=data['DataPts']['data_points']
    pdf=PDF();filename=pathlib.Path(source).name
    header(pdf,filename,'Trace overview')
    pairs=[('CABLE / FIBER',(g.get('cable_id') or 'Not recorded')+' / '+(g.get('fiber_id') or 'Not recorded')),('ROUTE',(g.get('location_a') or '?')+' to '+(g.get('location_b') or '?')),('NOMINAL WAVELENGTH',str(g.get('wavelength','Not recorded'))+' nm'),('SAMPLED SPAN','%.3f km'%(pts[-1][0]/1000))]
    for n,(label,value) in enumerate(pairs):
        xx=42+(n%2)*270;yy=650-(n//2)*48
        pdf.text(xx,yy,label,8,True,(.4,.48,.43))
        for j,line in enumerate(textwrap.wrap(value,38)[:2]):pdf.text(xx,yy-17-j*12,line,11,True)
    full=pts[-1][0]/1000
    graph(pdf,pts,events,full,359,'Full recorded trace')
    last=max([e['distance_of_travel']/1000 for e in events]+[0])
    zoom=min(full,max(.5,last*1.5)) if last else full
    graph(pdf,pts,events,zoom,118,'Event detail')
    pdf.text(42,63,'Event numbers mark stored positions. Distance offsets and launch compensation are not applied.',8)
    footer(pdf,1);pdf.page()
    header(pdf,filename,'Recorded events & settings')
    pdf.text(42,649,'Events stored by the instrument',13,True)
    # Paginate large event tables without clipping or dropping records.
    y=621
    def table_head(y):
        for xx,text in [(42,'#'),(68,'Distance (km)'),(161,'Type / raw code'),(321,'Loss (dB)'),(402,'Refl. (dB)'),(486,'Slope (dB/km)')]:pdf.text(xx,y,text,8,True)
        pdf.line(42,y-8,570,y-8)
    table_head(y);y-=30;page=2
    for event in events:
        if y<300:
            footer(pdf,page);pdf.page();page+=1;header(pdf,filename,'Recorded events (continued)');y=643;table_head(y);y-=30
        pdf.text(42,y,event['event_number'],9)
        pdf.text(68,y,'%.4f'%(event['distance_of_travel']/1000),9)
        pdf.text(161,y,event['event_type_details'].get('event') or 'Unknown',8)
        pdf.text(161,y-13,event['event_type'],8)
        pdf.text(321,y,'%.3f'%event['splice_loss'],9)
        pdf.text(402,y,'%.3f'%event['reflection_loss'],9)
        pdf.text(486,y,'%.3f'%event['slope'],9)
        pdf.line(42,y-22,570,y-22);y-=43
    if not events:pdf.text(42,y,'No KeyEvents block was recorded.',10);y-=30
    y-=15;pdf.text(42,y,'Acquisition settings',13,True);y-=26
    timestamp=datetime.datetime.fromtimestamp(f['date_time'],datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    settings=[('Test timestamp',timestamp),('Supplier / module',(s.get('supplier_name') or '-')+' / '+(s.get('module_name') or '-')),('Module serial',s.get('module_serial_number') or 'Not recorded'),('Operator',g.get('operator') or 'Not recorded'),('Wavelength (fixed block)','%g nm'%f['wavelength']),('Pulse width / sample spacing','%g ns / %.3f m'%(f['pulse_width'],pts[1][0]-pts[0][0])),('Group index / samples','%.5f / %s'%(f['index_of_refraction'],len(pts))),('Stored total loss / stored ORL','%.3f dB / %.3f dB'%(k.get('total_loss',0),k.get('optical_return_loss',0)) if k else 'Not recorded'),('Stored fiber length','%s m'%k.get('fiber_length','Not recorded'))]
    for label,value in settings:
        if y<175:
            footer(pdf,page);pdf.page();page+=1;header(pdf,filename,'Acquisition settings (continued)');y=644
        pdf.text(42,y,label,9,True)
        lines=textwrap.wrap(str(value),61) or ['-']
        for j,line in enumerate(lines):pdf.text(230,y-j*12,line,9)
        y-=max(22,len(lines)*12+5)
    y-=18
    notes=['Report scope: standard SOR v2, single-trace records. Proprietary EXFO blocks are not interpreted.', 'Zeros are reproduced as stored and may represent unset measurements. No compliance or pass/fail result is inferred.', 'Trace levels are relative (dB), not calibrated optical power (dBm). The SOR checksum has not been verified.', 'Positions use the trace origin. Vendor launch/receive compensation and proprietary event classifications are not applied.']
    for note in notes:
        lines=textwrap.wrap(note,99)
        if y-len(lines)*11<57:
            footer(pdf,page);pdf.page();page+=1;header(pdf,filename,'Report notes');y=640
        for line in lines:pdf.text(42,y,line,8);y-=11
        y-=7
    footer(pdf,page);pdf.save(output)
    return data
