import json
import zipfile

from backend.app.resolve_handoff import ResolveHandoffStore
from backend.app.resolve_textplus_timeline import _apply_broll_metadata, prepare_broll_media_files
from backend.app.media_pack_export import create_media_pack


def test_unicode_notes_are_not_rewritten_and_missing_readback_is_safe():
    class Item:
        def __init__(self): self.metadata={'Description':'Mia nota','Comments':'Città','Keywords':'viaggio'}
        def GetMetadata(self): return dict(self.metadata)
        def SetMetadata(self, values): self.metadata.update(values); return True
    item=Item()
    assert not _apply_broll_metadata(item, {'beat_id':'beat_1'})
    assert item.metadata['Comments']=='Città'
    class Unreadable:
        def SetMetadata(self, values): raise AssertionError('must not write without reading existing metadata')
    assert not _apply_broll_metadata(Unreadable(), {})


def test_resolve_metadata_preserves_user_notes_and_records_context():
    class Item:
        def __init__(self): self.metadata={'Description':'Nota mia','Comments':'Appunto mio','Keywords':'viaggio'}
        def GetMetadata(self): return dict(self.metadata)
        def SetMetadata(self, values): self.metadata.update(values); return True
    item=Item()
    row={'title':'Passaporto','provider':'pexels','asset_id':'beat_1--pexels:42','beat_id':'beat_1',
         'source_page':'https://example.com/video','original_text':'Controlla il passaporto',
         'record_start_frame':30,'record_end_frame':90,'source_start_frame':15,'source_end_frame':75,'rambla_fps':30}
    assert _apply_broll_metadata(item,row)
    assert item.metadata['Description']=='Nota mia' and item.metadata['Comments'].startswith('Appunto mio')
    assert 'viaggio' in item.metadata['Keywords'] and 'RAMBLA' in item.metadata['Keywords']
    assert 'Controlla il passaporto' in item.metadata['Comments']
    first=item.metadata['Comments']
    assert _apply_broll_metadata(item,row) and item.metadata['Comments']==first


def test_selected_media_are_grouped_by_video_image_and_generic(tmp_path):
    files=[]
    for name in ['video.mp4','image.png','generic.mp4']:
        source=tmp_path/name;source.write_bytes(name.encode());files.append(source)
    rows=[{'media_path':str(files[0]),'title':'A','kind':'video'},
          {'media_path':str(files[1]),'title':'B','kind':'image'},
          {'media_path':str(files[2]),'title':'C','role':'generic'}]
    prepared=prepare_broll_media_files(rows,tmp_path/'staging','project',organize=True)
    assert [__import__('pathlib').Path(row['media_path']).parent.name for row in prepared]==['VIDEO','IMMAGINI','GENERICHE']
    assert [__import__('pathlib').Path(row['media_path']).read_bytes() for row in prepared]==[p.read_bytes() for p in files]


def test_handoff_writes_a_portable_context_manifest_without_secrets(tmp_path):
    root=tmp_path/'projects'/'p';root.mkdir(parents=True)
    run=root/'run';run.mkdir()
    (run/'semantic-chunks.json').write_text(json.dumps([{'id':'c1','text':'Ciao mondo','start':0,'end':2}]),encoding='utf-8')
    media=root/'clip.mp4';media.write_bytes(b'video')
    payload={'project_id':'p','project_name':'Prova','fps':30,'duration_seconds':2,
             'api_key':'SECRET','broll_clips':[{'asset_id':'pexels:1','media_path':str(media),
             'beat_id':'b1','original_text':'Ciao mondo','record_start_frame':0,'record_end_frame':60,
             'source_start_frame':30,'source_end_frame':90}]}
    package=ResolveHandoffStore(root.parent).prepare(root,payload)
    manifest=json.loads((root/'resolve-outbox'/package['package_id']/'omnicut.json').read_text(encoding='utf-8'))
    assert manifest['schema']=='rambla-omnicut-handoff-1' and manifest['project']['id']=='p'
    assert manifest['media'][0]['record_in_frame']==0 and manifest['media'][0]['source_in_frame']==30
    assert manifest['media'][0]['original_text']=='Ciao mondo'
    assert 'SECRET' not in json.dumps(manifest)


def test_zip_contains_portable_omnicut_index_with_archive_paths(tmp_path):
    root=tmp_path/'project';root.mkdir();media=root/'clip.mp4';media.write_bytes(b'video')
    timeline={'fps':30,'duration_frames':60,'clips':[{'asset_id':'pexels:1','beat_id':'b1','title':'Mare',
              'original_text':'Andiamo al mare','media_path':str(media),'track_index':2,'duration_frames':60,
              'record_start_frame':0,'record_end_frame':60,'source_start_frame':30,'source_end_frame':90}]}
    archive=tmp_path/'out.zip'
    create_media_pack(archive,project_id='p',project_name='Test',project_root=root,timeline=timeline)
    with zipfile.ZipFile(archive) as z:
        manifest=json.loads(z.read('04_OMNICUT/progetto.json'))
        row=manifest['media'][0]
        assert row['media_path'] in z.namelist() and row['original_text']=='Andiamo al mare'
        assert row['record_out_frame']==60 and row['source_in_frame']==30
        assert str(root) not in json.dumps(manifest)
