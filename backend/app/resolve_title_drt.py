"""Experimental DRT rewrite of specifically identified generated titles.

This does not change an open timeline: Resolve must import the resulting DRT
as a new timeline, and callers must verify that all other content survived.
"""
from __future__ import annotations

import io
import re
import uuid
import zipfile
from xml.etree import ElementTree as ET

from .offline_resolve_archive import TITLE_TEMPLATE, _text_blob
from .title_typography import wrap_textplus_text


def _title_clip(start: int, duration: int, text: str) -> bytes:
    element=ET.fromstring(TITLE_TEMPLATE.read_bytes())
    for node in element.iter():
        if 'DbId' in node.attrib: node.set('DbId',str(uuid.uuid4()))
    clip=element.find('Sm2TiVideoClip')
    clip.find('Start').text=str(start)
    clip.find('Duration').text=str(duration)
    blob=clip.find('.//CompositionBA')
    blob.text=_text_blob(blob.text or '',wrap_textplus_text(text),duration)
    return ET.tostring(clip,encoding='utf-8',xml_declaration=False)


def apply_optimized_titles_to_drt(data: bytes, titles: list[dict]) -> bytes:
    with zipfile.ZipFile(io.BytesIO(data)) as source:
        members={n:source.read(n) for n in source.namelist()}
    seq_names=[n for n in members if n.startswith('SeqContainer/') and n.endswith('.xml')]
    if len(seq_names)!=1: raise ValueError('Timeline DRT ambigua')
    key=seq_names[0]; seq=members[key]
    video=re.search(rb'<VideoTrackVec\b[^>]*>.*?</VideoTrackVec>',seq,re.S)
    if not video: raise ValueError('Tracce video DRT non trovate')
    section=video.group(); tracks=list(re.finditer(rb'<Sm2TiTrack\b[^>]*>.*?</Sm2TiTrack>',section,re.S))
    replacements={}
    for row in titles:
        track=int(row['track_index']); start=int(row['start_frame']); end=int(row['end_frame'])
        duration=end-start
        if duration<=0 or duration>125: raise ValueError('Durata titolo fuori dal limite verificato di 125 fotogrammi')
        if track<1 or track>len(tracks): raise ValueError('Traccia titolo non trovata')
        t=tracks[track-1]; body=t.group()
        matches=[]
        for clip in re.finditer(rb'<Sm2TiVideoClip\b[^>]*>.*?</Sm2TiVideoClip>',body,re.S):
            value=clip.group()
            st=re.search(rb'<Start>\s*(-?\d+)\s*</Start>',value)
            dur=re.search(rb'<Duration>\s*(\d+)\s*</Duration>',value)
            if st and dur and int(st.group(1))==start and int(dur.group(1))==duration and b'<CompositionBA>' in value:
                matches.append((t.start()+clip.start(),t.start()+clip.end()))
        if len(matches)!=1 or matches[0] in replacements: raise ValueError('Titolo da sostituire non trovato o ambiguo')
        replacements[matches[0]]=_title_clip(start,duration,str(row.get('text') or ''))
    for (start,end),clip in sorted(replacements.items(),reverse=True):
        section=section[:start]+clip+section[end:]
    members[key]=seq[:video.start()]+section+seq[video.end():]
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
        for name,value in members.items(): z.writestr(name,value)
    return output.getvalue()
