import zipfile
import json
import pytest


class Media:
    def __init__(self, path): self.path = path
    def GetClipProperty(self, key): return str(self.path) if key == 'File Path' else ''
class Item:
    def __init__(self, path): self.media = Media(path)
    def GetMediaPoolItem(self): return self.media
class Timeline:
    def __init__(self, paths): self.paths = paths
    def GetName(self): return 'Test'
    def GetTrackCount(self, kind): return 1 if kind == 'video' else 0
    def GetItemListInTrack(self, kind, index): return [Item(p) for p in self.paths]
    def Export(self, path, *args):
        from pathlib import Path
        Path(path).write_bytes(b'timeline')
        return True
class Resolve:
    EXPORT_DRT = 1
    EXPORT_NONE = 0


def test_package_contains_timeline_and_each_source_once(tmp_path):
    from backend.app.timeline_share_package import export_timeline_package
    source=tmp_path/'video.mov'; source.write_bytes(b'video')
    out=tmp_path/'out.zip'
    export_timeline_package(Resolve(), Timeline([source, source]), out)
    with zipfile.ZipFile(out) as z:
        assert z.read('Timeline.drt') == b'timeline'
        media=[p for p in z.namelist() if p.startswith('Media/')]
        assert len(media)==1 and z.read(media[0])==b'video'
        assert 'LEGGIMI.txt' in z.namelist()


def test_missing_source_fails_instead_of_creating_incomplete_package(tmp_path):
    from backend.app.timeline_share_package import export_timeline_package
    out=tmp_path/'out.zip'
    with pytest.raises(RuntimeError, match='non disponibile'):
        export_timeline_package(Resolve(), Timeline([tmp_path/'missing.mov']), out)
    assert not out.exists()


def test_existing_destination_is_not_overwritten(tmp_path):
    from backend.app.timeline_share_package import export_timeline_package
    out=tmp_path/'out.zip'; out.write_bytes(b'precedente')
    with pytest.raises(RuntimeError, match='esiste già'):
        export_timeline_package(Resolve(), Timeline([]), out)
    assert out.read_bytes()==b'precedente'


def test_user_can_continue_without_missing_media(tmp_path):
    from backend.app.timeline_share_package import export_timeline_package
    source=tmp_path/'video.mov'; source.write_bytes(b'video')
    missing=tmp_path/'offline.mov'; out=tmp_path/'out.zip'; requests=[]
    result=export_timeline_package(Resolve(), Timeline([source,missing,missing]), out,
                                   confirm_missing=lambda paths: requests.append(paths) or True)
    assert requests==[[str(missing)]] and result['missing_count']==1
    with zipfile.ZipFile(out) as z:
        assert json.loads(z.read('manifest.json'))['missing_media']==[str(missing)]
        assert len([name for name in z.namelist() if name.startswith('Media/')])==1


def test_declining_missing_media_cancels_without_creating_archive(tmp_path):
    from backend.app.timeline_share_package import export_timeline_package
    out=tmp_path/'out.zip'
    with pytest.raises(RuntimeError, match='annullata'):
        export_timeline_package(Resolve(), Timeline([tmp_path/'missing.mov']), out,
                                confirm_missing=lambda paths: False)
    assert not out.exists()
