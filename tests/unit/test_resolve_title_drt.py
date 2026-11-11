import io
import zipfile
from xml.etree import ElementTree as ET

import pytest

from backend.app.resolve_title_drt import apply_optimized_titles_to_drt


def make_drt():
    video=b'<Sm2SequenceContainer><VideoTrackVec><Element><Sm2TiTrack><Items><Element><Sm2TiVideoClip DbId="carrier"><Start>25</Start><Duration>50</Duration><CompositionTable><CompositionBA>01</CompositionBA></CompositionTable></Sm2TiVideoClip></Element></Items></Sm2TiTrack></Element><Element><Sm2TiTrack><Items><Element><Sm2TiVideoClip DbId="other"><Start>25</Start><Duration>50</Duration></Sm2TiVideoClip></Element></Items></Sm2TiTrack></Element></VideoTrackVec></Sm2SequenceContainer>'
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w') as z:
        z.writestr('SeqContainer/one.xml',video)
        z.writestr('MediaPool/Master/MpFolder.xml',b'unchanged')
    return buffer.getvalue()


def test_replaces_only_target_title_and_keeps_other_archive_members():
    result=apply_optimized_titles_to_drt(make_drt(),[{'track_index':1,'start_frame':25,'end_frame':75,'text':'National Geographic'}])
    with zipfile.ZipFile(io.BytesIO(result)) as z:
        assert z.read('MediaPool/Master/MpFolder.xml')==b'unchanged'
        root=ET.fromstring(z.read('SeqContainer/one.xml'))
        tracks=root.findall('VideoTrackVec/Element/Sm2TiTrack')
        clip=tracks[0].find('.//Sm2TiVideoClip')
        assert clip.findtext('PrettyType')=='Fusion Title'
        assert (clip.findtext('Start'),clip.findtext('Duration'))==('25','50')
        assert b'KURA_Paper_Text_Optimized' in bytes.fromhex(clip.findtext('.//Sm2TiCompositionTable/FieldsBlob'))
        assert tracks[1].find('.//Sm2TiVideoClip').attrib['DbId']=='other'


def test_fails_closed_for_non_matching_carrier_or_long_title():
    with pytest.raises(ValueError,match='non trovato'):
        apply_optimized_titles_to_drt(make_drt(),[{'track_index':2,'start_frame':25,'end_frame':75,'text':'Ciao'}])
    with pytest.raises(ValueError,match='125'):
        apply_optimized_titles_to_drt(make_drt(),[{'track_index':1,'start_frame':25,'end_frame':200,'text':'Ciao'}])
