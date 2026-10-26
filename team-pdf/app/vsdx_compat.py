"""Work around libvisio's Windows signed-long parsing of deleted-shape IDs.
4294967295 and -1 become the same unsigned ID in libvisio. Only a temporary
import copy is rewritten; every other XML byte and package entry is preserved.
"""
import os
import pathlib
import re
import zipfile
from xml.parsers import expat

NS='http://schemas.microsoft.com/office/visio/2012/main'
ID_ATTRIBUTE=re.compile(rb'(?<![\w:.-])ID(\s*=\s*)([\'\"])4294967295\2')

def normalize_xml(data):
    patches=[]
    parser=expat.ParserCreate(namespace_separator='}')
    parser.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    def start(name,attrs):
        if name!=NS+'}Shape' or attrs.get('ID')!='4294967295':return
        begin=parser.CurrentByteIndex;end=begin;quote=None
        while end<len(data):
            byte=data[end]
            if quote:
                if byte==quote:quote=None
            elif byte in [34,39]:quote=byte
            elif byte==62:break
            end+=1
        tag=data[begin:end+1]
        replacement,count=ID_ATTRIBUTE.subn(lambda m:b'ID'+m[1]+m[2]+b'-1'+m[2],tag)
        if count!=1:raise ValueError('Could not safely normalize this Visio shape ID.')
        patches.append((begin,end+1,replacement))
    parser.StartElementHandler=start
    parser.Parse(data,True)
    for begin,end,replacement in reversed(patches):data=data[:begin]+replacement+data[end:]
    return data,len(patches)

def normalize_shape_ids(path):
    path=pathlib.Path(path);changes={};count=0
    with zipfile.ZipFile(path) as archive:
        for entry in archive.infolist():
            if entry.filename.startswith(('visio/pages/','visio/masters/')) and entry.filename.endswith('.xml'):
                data=archive.read(entry)
                if b'4294967295' not in data:continue
                normalized,n=normalize_xml(data)
                if n:changes[entry.filename]=normalized;count+=n
        if not count:return 0
        stage=path.with_name(path.name+'.compat')
        try:
            with zipfile.ZipFile(stage,'w') as output:
                for entry in archive.infolist():output.writestr(entry,changes.get(entry.filename,archive.read(entry)))
        except BaseException:
            stage.unlink(missing_ok=True);raise
    os.replace(stage,path)
    return count
