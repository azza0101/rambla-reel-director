"""Audit existing REAL provider artifacts through the API; no searches or models.

Run with the project UI Python after the two sourcing CLIs. Outputs a local
review report; this is a retrieval regression probe, not product acceptance.
"""
import argparse
import json
from pathlib import Path
import subprocess
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.app.atomic_io import write_json
from backend.app.editorial_import import retrieval_bundle
from backend.app.video_preview import probe_preview


def main():
    from fastapi.testclient import TestClient
    from backend.app.debug_server import create_app
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',type=Path,required=True)
    args=parser.parse_args();run=args.run.resolve();proof=run.parent
    root,*_=retrieval_bundle(run)
    images=json.loads((root/'image-candidates.json').read_text(encoding='utf-8'))
    videos=json.loads((root/'online-candidates.json').read_text(encoding='utf-8'))
    plan=json.loads((run/'visual-plan.json').read_text(encoding='utf-8'))
    source=proof/'fixture-source.mp4'
    if not source.exists():
        duration=max(b['end'] for b in plan['visual_beats'])
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i',f'color=c=gray:s=1280x720:r=25:d={duration}',
            '-c:v','libx264','-pix_fmt','yuv420p',str(source)],check=True)
    projects=proof/'api-projects'
    with TestClient(create_app(project_root=projects,allowed_media_roots=[proof])) as client:
        pid=client.post('/api/curation/projects',json={'name':'Retrieval quality review'}).json()['project_id']
        base=f'/api/curation/projects/{pid}'
        response=client.post(base+'/source/local',json={'path':str(source)});response.raise_for_status()
        project=response.json();target=projects/pid/'run';target.mkdir()
        for name in ('semantic-chunks.json','transcript-raw.json','semantic-beats.json'):
            write_json(target/name,json.loads((run/name).read_text(encoding='utf-8')))
        write_json(target/'analysis-signature.json',{'analysis_signature':project['analysis_signature']})
        package=client.get(base+'/editorial-input').json()
        plan.update(project_id=pid,transcript_signature=package['transcript_signature'])
        client.post(base+'/editorial-plan',json=plan).raise_for_status()
        target_root,*_=retrieval_bundle(target)
        # Copy actual fetched previews into the fixture project's own safe media root.
        media_root=target_root/'review-media';media_root.mkdir(exist_ok=True)
        for row in [c for b in videos for c in b['candidates']]+[c for b in images['chunks'].values() for c in b['candidates']]:
            for key in ('preview_path','poster_path','keyframe_path','path'):
                if row.get(key):
                    original=Path(row[key]).resolve();local=media_root/original.name
                    if original.is_file():shutil.copy2(original,local)
                    row[key]=str(local)
        write_json(target_root/'image-candidates.json',images)
        write_json(target_root/'online-candidates.json',videos)
        payload=client.get(base+'/curation').json();assert not payload['retrieval_warnings']
        report={'scope':'retrieval regression probe; product NOT validated','project_id':pid,
            'generative_calls':0,'asr_rerun':False,'resolve_calls':0,'beats':[]}
        for beat in payload['chunks']:
            assets=beat['assets'];social=[a for a in assets if a['kind']=='video' and a['provider']!='pexels']
            stock=[a for a in assets if a['kind']=='video' and a['provider']=='pexels']
            assert len(social)<=3 and len(stock)<=3
            for a in assets:
                assert a['matched_query'] and a['source_url'] and isinstance(a['score'],(int,float))
                media=client.get(a['preview_url']);media.raise_for_status();assert len(media.content)>1000
                if a['kind']=='video' and a['preview_status']=='ready':
                    assert media.headers['content-type'].startswith('video/')
                    assert a['source_start_seconds'] is not None and a['source_end_seconds']>a['source_start_seconds']
                elif a['kind']=='video':
                    assert not a['selectable']
                    assert client.put(base+'/curation/chunks/'+beat['id']+'/selection',json={'asset_ids':[a['asset_id']],'no_broll':False}).status_code==422
            chosen=[a['asset_id'] for a in assets if a['selectable']][:2]
            if chosen:
                response=client.put(base+'/curation/chunks/'+beat['id']+'/selection',json={'asset_ids':chosen,'no_broll':False})
                response.raise_for_status()
                saved=client.get(base+'/curation').json()['selection_plan']['chunks'][beat['id']]
                assert [a['asset_id'] for a in saved['selected_assets']]==chosen
            report['beats'].append({'id':beat['id'],'text':beat['text'],'assets':assets})
        report['http_media_and_selection']='PASS'
        report['video_seconds']=json.loads((root/'online-sourcing-benchmark.json').read_text())['total_seconds']
        report['image_seconds']=json.loads((root/'image-sourcing-timings.json').read_text())['sourcing_seconds']
        report['image_cross_chunk_duplicate_rate']=images['cross_chunk_duplicate_rate']
        write_json(proof/'review.json',report)
        print(json.dumps({k:v for k,v in report.items() if k!='beats'},indent=2))


if __name__=='__main__':main()
