from types import SimpleNamespace
from tests.unit.test_cut_pass_routes import tmp_path


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
