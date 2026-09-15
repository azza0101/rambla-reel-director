import json
from pathlib import Path
from backend.app.visual_planner import ConcreteVisualPlanner, apply_visual_plan_to_outline


def test_generated_shots_supply_video_queries_in_shot_order():
    shots = [dict(shot_id=str(i),description=q,image_queries=[q,q+' closeup'],video_queries=[q,q+' footage']) for i,q in enumerate(['passengers boarding airplane','tourist bus luggage','passengers boarding ferry'])]
    response = dict(editorial_function='contrast',core_meaning='The journey has several physical costs',subtext='The claim needs scrutiny',visual_mode='sequence',shots=shots,avoid=['generic beach'])
    chunks=json.loads((Path(__file__).parents[1]/'fixtures/visual_planner/kura.json').read_text(encoding='utf-8'))[:1]
    artifact={'chunks':{chunks[0]['id']:{**response,'planner_provider':'Qwen3.5-4B'}}}
    outline=apply_visual_plan_to_outline({'beats':[{'id':chunks[0]['id'],'intent':'old','broll_queries':['abstract contradiction']}]},artifact)
    assert outline['beats'][0]['broll_queries'][:3] == [s['description'] for s in shots]
    assert 'abstract contradiction' not in outline['beats'][0]['broll_queries']
    assert artifact['chunks'][chunks[0]['id']]['planner_provider']=='Qwen3.5-4B'
