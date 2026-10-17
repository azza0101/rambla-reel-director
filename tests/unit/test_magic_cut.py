from types import SimpleNamespace
from tests.unit.test_cut_pass_routes import tmp_path


def test_confirmed_reviewed_boundaries_are_not_paid_for_again(tmp_path):
    import asyncio
    from backend.app.magic_cut import MagicCutAdapter
    from backend.app.magic_models import MagicOptions
    context=SimpleNamespace(run_id='r',source_project_id='original')
    state={'work_project_id':'work','initialized':True,'inherited_origin':{'plan':{}},
           'steps':{'analyze':{'reused_confirmed_cut':True}}}
    calls=[]
    class Engine:
        def current(self,pid):
            return None,None,{'revision':'r','groups':[{'boundaries_reviewed':True}]}
        async def perform(self,action,*args,**kwargs):
            calls.append(action)
            return {'project_id':'child'} if action=='confirm' else {}
    adapter=MagicCutAdapter(None,tmp_path,None,Engine())
    adapter._workspace=lambda _: (tmp_path/'journal.json',state)
    adapter._initialize=lambda *args: None
    asyncio.run(adapter.run(context,MagicOptions(),lambda *args:None))
    assert calls==['residual','review','confirm']
    assert state['steps']['boundaries']['reused_confirmed_boundaries']


def test_final_margin_protects_long_word_low_energy_ending():
    from backend.app.cut_silence import trim_silence_ranges
    words = [{'start':.2,'end':1.1}]
    result = trim_silence_ranges([[0,120,0]], [[1,3]], 30, 'medium', words, end_margin_ms=120)
    assert result[0][1] >= 37  # ceil((1.1 + .12) * 30)
    assert result[-1][1] == 120


def test_shared_cut_analysis_reuses_transcript_and_proposals(tmp_path, monkeypatch):
    from backend.app.cut_analysis_service import analyze_cut_project
    import backend.app.cut_residual as residual
    monkeypatch.setattr(residual, 'review_residual_takes', lambda raw, plan: plan)
    calls = []
    raw = {'timing_basis':'cloud_asr_word_timestamps','segments':[{'words':[{'word':'ciao','start':.1,'end':.5}, {'word':'mondo','start':.7,'end':1.1}]}]}
    project = SimpleNamespace(analysis_signature='v1', source_video=SimpleNamespace(path='source.mp4',duration=2,fps=30))
    def transcribe(*args): calls.append('asr'); return raw
    def propose(*args): calls.append('propose'); return {'groups':[], 'discards':[]}
    def choose(raw, groups): return groups
    for _ in range(2):
        result = analyze_cut_project(project,tmp_path,lambda *args:None,
            transcribe=transcribe,propose=propose,choose=choose,align=lambda p,f,plan,progress:plan)
        assert result['revision']
    assert calls == ['asr','propose']


def test_magic_reserves_budget_instead_of_retranscribing_every_take(tmp_path):
    from backend.app.magic_store import MagicStore
    from backend.app.magic_models import MagicOptions
    from backend.app.magic_usage import provider_scope
    from backend.app.cut_alignment import refine_cut_timing
    from backend.app.cut_pass import build_cut_plan
    from tests.unit.test_cut_pass import transcript
    from pathlib import Path
    raw=transcript([(2,3,'Cura Viaggi')])
    plan=build_cut_plan(raw,duration=5,fps=30,signature='s',groups=[])
    plan['groups']=[{'takes':[[0,1],[0,1]],'selected_take':0}]
    store=MagicStore(tmp_path);row=store.create_or_resume('p','s',MagicOptions(max_cloud_requests=12))
    for index in range(2):
        call=store.begin_call(row['run_id'],'cut','groq_asr',str(index));store.finish_call(row['run_id'],call,result={})
    def forbidden(*a):raise AssertionError('No extra ASR budget for refinement')
    with provider_scope(store,row['run_id'],'cut',lambda:None):
        result,warnings=refine_cut_timing(raw,plan,Path('source'),tmp_path,
            runner=lambda *a,**kw:None,transcriber=forbidden)
    assert result['segments']==raw['segments'] and warnings


def test_magic_cut_isolates_manual_source_and_reuses_confirmed_child(tmp_path):
    import asyncio, json
    from pathlib import Path
    from backend.app.magic_cut import MagicCutAdapter
    from backend.app.magic_store import MagicStore
    from backend.app.magic_models import MagicContext, MagicOptions
    root = tmp_path/'projects'; (root/'original'/'run').mkdir(parents=True)
    manual = root/'original'/'run'/'phrase-intents.json'
    manual.write_text('{"manual":true}')
    source = SimpleNamespace(project_id='original',name='Source',analysis_signature='original-v1',
                             source_video=SimpleNamespace(path=str(tmp_path/'source.mp4')))
    work = SimpleNamespace(project_id='work',analysis_signature='work-v1')
    projects = SimpleNamespace(load=lambda pid: source if pid=='original' else work,
        create=lambda name: work, register_local_video=lambda pid,path: work)
    plan = {'revision':'r1','warnings':[]}
    calls=[]
    class Engine:
        def current(self,pid): assert pid=='work'; return work,Path(),plan
        async def perform(self, action, pid, request=None, report=None):
            calls.append(action)
            if action=='review':
                assert request.end_margin_ms==120 and request.pause_mode=='medium'
            return {'project_id':'child'} if action=='confirm' else {'revision':'r1'}
    store=MagicStore(root)
    row=store.create_or_resume('original','sig',MagicOptions())
    context=MagicContext.model_validate(row)
    adapter=MagicCutAdapter(projects,root,store,Engine())
    async def run():
        for _ in range(2):
            result=await adapter.run(context,MagicOptions(),lambda *args:None)
            assert result['output_project_id']=='child'
    asyncio.run(run())
    assert calls==['analyze','boundaries','review','confirm']
    assert json.loads(manual.read_text())=={'manual':True}
