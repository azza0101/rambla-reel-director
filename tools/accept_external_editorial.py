"""Opt-in live provider acceptance. Uses a manual fixture, never generative models."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.app.atomic_io import write_json
from backend.app.editorial_import import retrieval_bundle


def main():
    from fastapi.testclient import TestClient
    from backend.app.debug_server import create_app
    proof=ROOT/'.external-plan-proof'; proof.mkdir(exist_ok=True)
    projects=proof/'projects';projects.mkdir(exist_ok=True)
    source=projects/'manual-fixture.mp4'
    if not source.exists():
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=gray:s=1280x720:r=25:d=8','-c:v','libx264','-pix_fmt','yuv420p',str(source)],check=True)
    os.environ['RAMBLA_RETRIEVAL_RANKING']='provider'
    os.environ['RAMBLA_DIRECTOR_MODEL']='UNAVAILABLE-GENERATIVE-MODEL'
    os.environ['RAMBLA_ASR_PYTHON']=sys.executable
    os.environ['RAMBLA_DEBUG_COMMAND_JSON']=json.dumps([sys.executable,'-m','backend.app.debug_run_cli','--video','{video}','--output-dir','{output}'])
    with TestClient(create_app(project_root=projects,allowed_media_roots=[projects])) as client:
        pid=client.post('/api/curation/projects',json={'name':'External manual plan acceptance'}).json()['project_id']
        base=f'/api/curation/projects/{pid}'
        response=client.post(base+'/source/local',json={'path':str(source)});response.raise_for_status()
        project=response.json(); run=projects/pid/'run';run.mkdir()
        fixture=json.loads((ROOT/'tests/fixtures/external-editorial-manual.json').read_text(encoding='utf-8'))
        chunks=fixture['chunks']
        write_json(run/'semantic-chunks.json',chunks)
        write_json(run/'transcript-raw.json',{'language':'en','timeline_fps':25,'segments':chunks})
        write_json(run/'semantic-beats.json',{'beats':[]})
        write_json(run/'analysis-signature.json',{'analysis_signature':project['analysis_signature']})
        assert client.post(base+'/analyze').json()['status']=='reused'
        exported=client.get(base+'/editorial-input');exported.raise_for_status();package=exported.json()
        write_json(proof/'editorial-input.json',package)
        (proof/'clipboard-input.txt').write_text(package['instructions']+'\n\n'+json.dumps(package,ensure_ascii=False,indent=2),encoding='utf-8')
        plan=fixture['plan'];plan.update(project_id=pid,transcript_signature=package['transcript_signature'])
        imported=client.post(base+'/editorial-plan',json=plan);imported.raise_for_status()
        write_json(proof/'visual-plan.json',plan)
        timings={}; runs={}
        for stage in ('videos','images'):
            started=time.perf_counter()
            response=client.post(base+'/source/'+stage);response.raise_for_status()
            rid=response.json()['run_id']
            while True:
                state=client.get('/v1/debug/runs/'+rid).json()
                if state['status'] in {'SUCCEEDED','FAILED','CANCELLED'}: break
                if time.perf_counter()-started>240: raise TimeoutError(stage)
                time.sleep(.25)
            timings[stage]=round(time.perf_counter()-started,3);runs[stage]=state
            write_json(proof/(stage+'-run.json'),state)
            print(stage,state['status'],timings[stage],flush=True)
            if state['status']!='SUCCEEDED': raise RuntimeError(json.dumps(state))
        payload=client.get(base+'/curation').json();write_json(proof/'curation.json',payload)
        root,_,_,_=retrieval_bundle(run)
        images=json.loads((root/'image-candidates.json').read_text(encoding='utf-8'))
        videos=json.loads((root/'online-candidates.json').read_text(encoding='utf-8'))
        assert images['chunks']['vb-1']['queries']==plan['visual_beats'][0]['shots'][0]['image_queries']
        assert videos[0]['queries']==plan['visual_beats'][0]['shots'][0]['video_queries']
        shelf=payload['chunks'][0]['assets']
        counts={kind:sum(a['kind']==kind for a in shelf) for kind in ('video','image')}
        assert all(counts.values()),counts
        for asset in shelf:
            response=client.get(asset['preview_url']);response.raise_for_status()
            assert len(response.content)>1000
            assert asset['source_page'].startswith('https://')
        selected=[a['asset_id'] for a in shelf[:3]]
        save=client.put(base+'/curation/chunks/vb-1/selection',json={'asset_ids':selected,'no_broll':False});save.raise_for_status()
        assert [a['track'] for a in save.json()['selection']['selected_assets']]==['V2','V3','V4'][:len(selected)]
        assert client.get(base+'/curation').json()['selection_plan']['chunks']['vb-1']==save.json()['selection']
        assert json.loads((run/'visual-plan.json').read_text(encoding='utf-8'))==plan
        report={'status':'PASS','project_id':pid,'project_root':str(projects),'manual_transcript_fixture':True,'asr_rerun':False,'generative_calls':0,'ranking':'provider order; no model scores','timings_seconds':timings,'cards':counts,'playable_videos':sum(a['kind']=='video' and a['preview_status']=='ready' for a in shelf),'discovery_videos':sum(a['kind']=='video' and a['preview_status']=='discovery' for a in shelf),'queries_unchanged':True,'plan_unchanged':True,'selection_persisted':True,'preview_http_ok':True,'resolve_calls':0}
        write_json(proof/'acceptance.json',report); print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
