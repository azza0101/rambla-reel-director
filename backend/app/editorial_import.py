"""Model-neutral editorial contract. No model imports or generative fallback."""
from __future__ import annotations
import hashlib
import json
import math
import re
from pathlib import Path
from .atomic_io import write_json

VERSION = 'rambla-visual-plan-1'
INSTRUCTIONS = '''Analyze the WHOLE reel. Return only JSON matching visual_plan_schema.
Copy project_id and transcript_signature exactly. Cover every chunk once, in order.
Group adjacent chunks into visual beats; do NOT create new B-roll per chunk.
Choose BROLL, KEEP_TALKING_HEAD, or CONTINUE_PREVIOUS_VISUAL (reference the
immediately preceding BROLL/continuation via continuation_from). Only BROLL has shots.
Aim for dense short-form visual coverage: normally keep roughly 90-98% of spoken
duration under BROLL or CONTINUE_PREVIOUS_VISUAL when factual/retrievable visuals exist.
KEEP_TALKING_HEAD is a deliberate exception for intro, CTA, punchline or delivery-critical
moments; prefer continuing a strong previous visual over leaving avoidable visual gaps.
Do not invent filler merely to reach the coverage target.
Current spoken meaning is authoritative. Neighbors only clarify references; never
import future or unrelated objects. Global theme is not a source of shot nouns.
Never turn suspicion into fact or contradict explicit speech, including negations.
Prefer ONE physical, retrievable shot. Use 2-3 only for an explicitly justified
sequence/juxtaposition. No staged composites, invented props, symbolic filler or
forced metaphors. Avoid visual repetition across the reel.
Never default to a person using a laptop, generic hotel room, travel-planning map,
tutorial, infographic, presenter or stock office scene unless that physical object/action
is actually supported by the CURRENT spoken beat. Generic activity is not a substitute
for editorial meaning. For rhetorical questions, investigation, doubt or a spoken
"silence/no answer", prefer the named subject plus a truthful reaction/evasion/silence
visual; never fabricate wrongdoing. Concrete named entities in the current beat outrank
generic props. Put recurring unwanted shortcuts and contradictions in avoid so retrieval
can treat them as hard negatives. For short-form video, prefer simple visible actions
that can plausibly exist as candid vertical phone footage (Shorts/Reels/TikTok style),
without adding facts not present in speech.
Describe visible things and actions; write 1-3 simple concrete English queries per
medium per shot. Use exact start/end seconds and concatenate covered original texts in
order. Do not change transcript text. Do not invent facts or provider URLs.'''


def visual_coverage_ratio(plan):
    """Fraction of spoken beat duration visually covered by BROLL/CONTINUE.

    The imported plan remains authoritative; this is a diagnostic metric only.
    """
    beats = list((plan or {}).get('visual_beats') or [])
    total = 0.0
    visual = 0.0
    for beat in beats:
        try:
            duration = max(0.0, float(beat['end']) - float(beat['start']))
        except (KeyError, TypeError, ValueError):
            continue
        total += duration
        if beat.get('action') in {'BROLL', 'CONTINUE_PREVIOUS_VISUAL'}:
            visual += duration
    return round(visual / total, 6) if total > 0 else 0.0


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def parse_plan(raw):
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result: raise ValueError(f'duplicate JSON field: {key}')
            result[key]=value
        return result
    return json.loads(raw, object_pairs_hook=unique)


def normalized_chunks(run):
    rows = read(run/'semantic-chunks.json')
    return [dict(id=str(c['id']), start=c.get('start',c.get('start_seconds')), end=c.get('end',c.get('end_seconds')), text=c['text'], **({'words':c['words']} if 'words' in c else {})) for c in rows]


def transcript_package(run, project_id, duration):
    chunks = normalized_chunks(run)
    if not chunks:
        raise ValueError('Analyze the reel first: transcript chunks are empty')
    raw = read(run/'transcript-raw.json')
    marker = read(run/'analysis-signature.json') if (run/'analysis-signature.json').exists() else {}
    signature = digest({'chunks':chunks,'analysis_signature':marker.get('analysis_signature')})
    return {'schema_version':'rambla-editorial-input-1','project_id':project_id,
        'duration':duration,'language':raw.get('language','und'),'transcript_signature':signature,
        'chunks':chunks,'full_transcript':' '.join(c['text'].strip() for c in chunks),
        'word_timestamps':[] if (run/'transcript-corrections.json').exists() else [w for s in raw.get('segments',[]) for w in s.get('words',[])],
        'instructions':INSTRUCTIONS,'visual_plan_schema':contract_schema()}


def contract_schema():
    string = {'type':'string','minLength':1}
    strings = {'type':'array','items':string}
    ident = {'type':'string','pattern':'^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$'}
    queries = {**strings,'minItems':1,'maxItems':3,'uniqueItems':True}
    def obj(properties, optional=()):
        return {'type':'object','additionalProperties':False,'properties':properties,'required':[k for k in properties if k not in optional]}
    shot = obj({'shot_id':ident,'description':string,'image_queries':queries,'video_queries':queries})
    beat = obj({'id':ident,'start':{'type':'number','minimum':0},'end':{'type':'number','exclusiveMinimum':0},'covered_chunk_ids':{**strings,'minItems':1,'uniqueItems':True},'original_text':string,'action':{'enum':['BROLL','KEEP_TALKING_HEAD','CONTINUE_PREVIOUS_VISUAL']},'editorial_function':string,'core_meaning':string,'subtext':{'type':'string'},'visual_mode':{'enum':['single','sequence','juxtaposition']},'shots':{'type':'array','items':shot,'maxItems':3},'avoid':strings,'continuation_from':ident}, ('continuation_from',))
    beat['allOf']=[
        {'if':{'properties':{'action':{'const':'BROLL'}}},'then':{'properties':{'shots':{'minItems':1}}},'else':{'properties':{'shots':{'maxItems':0}}}},
        {'if':{'properties':{'action':{'const':'CONTINUE_PREVIOUS_VISUAL'}}},'then':{'required':['continuation_from']},'else':{'not':{'required':['continuation_from']}}},
        {'if':{'properties':{'action':{'const':'BROLL'},'visual_mode':{'const':'single'}}},'then':{'properties':{'shots':{'maxItems':1}}}},
        {'if':{'properties':{'action':{'const':'BROLL'},'visual_mode':{'enum':['sequence','juxtaposition']}}},'then':{'properties':{'shots':{'minItems':2}}}}
    ]
    return {'$schema':'https://json-schema.org/draft/2020-12/schema', **obj({'schema_version':{'const':VERSION},'project_id':string,'transcript_signature':string,'global_topic':string,'visual_beats':{'type':'array','minItems':1,'items':beat}})}


def _shape(value, schema, path='$'):
    def fail(message): raise ValueError(f'{path}: {message}')
    if 'const' in schema and value != schema['const']: fail('expected '+schema['const'])
    if 'enum' in schema and value not in schema['enum']: fail('expected one of '+', '.join(schema['enum']))
    kind = schema.get('type')
    if kind == 'object':
        if not isinstance(value,dict): fail('expected object')
        missing=set(schema['required'])-value.keys(); extra=value.keys()-schema['properties'].keys()
        if missing: fail('missing fields: '+', '.join(sorted(missing)))
        if extra: fail('unknown fields: '+', '.join(sorted(extra)))
        for k,v in value.items(): _shape(v,schema['properties'][k],path+'.'+k)
    elif kind == 'array':
        if not isinstance(value,list): fail('expected array')
        if not schema.get('minItems',0)<=len(value)<=schema.get('maxItems',10000): fail('invalid array length')
        if schema.get('uniqueItems') and len({digest(x) for x in value}) != len(value): fail('duplicates not allowed')
        for i,v in enumerate(value): _shape(v,schema['items'],f'{path}[{i}]')
    elif kind == 'string':
        if not isinstance(value,str): fail('expected string')
        if len(value.strip())<schema.get('minLength',0): fail('must not be empty')
        if 'pattern' in schema and not re.fullmatch(schema['pattern'],value): fail('invalid identifier')
    elif kind == 'number':
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value): fail('expected finite number')
        if value<schema.get('minimum',-math.inf) or value<=schema.get('exclusiveMinimum',-math.inf): fail('invalid time')


def validate_import(value, package):
    _shape(value,contract_schema())
    for key in ('project_id','transcript_signature'):
        if value[key] != package[key]: raise ValueError(f'$.{key}: does not match this transcript; export editorial input again')
    expected=package['chunks']; cursor=0; ids=set(); previous=None
    for i,b in enumerate(value['visual_beats']):
        path=f'$.visual_beats[{i}]'
        def fail(message): raise ValueError(path+': '+message)
        if b['id'] in ids: fail('duplicate beat id')
        ids.add(b['id']); covered=expected[cursor:cursor+len(b['covered_chunk_ids'])]
        if [c['id'] for c in covered]!=b['covered_chunk_ids']: fail('covered_chunk_ids must cover adjacent chunks once, in transcript order')
        cursor+=len(covered)
        if not covered or abs(b['start']-covered[0]['start'])>0.001 or abs(b['end']-covered[-1]['end'])>0.001: fail('start/end must match covered chunk boundaries')
        if b['end']<=b['start'] or b['end']>package['duration']+0.001: fail('time range outside reel')
        if previous and b['start']<previous['end']-0.001: fail('overlapping beats')
        if ' '.join(b['original_text'].split())!=' '.join(' '.join(c['text'] for c in covered).split()): fail('original_text must match covered speech')
        if b['action']=='BROLL':
            if not 1<=len(b['shots'])<=3: fail('BROLL requires 1–3 shots')
            if b['visual_mode']=='single' and len(b['shots'])!=1: fail('single mode requires one shot')
            if b['visual_mode']!='single' and len(b['shots'])<2: fail('sequence/juxtaposition requires 2–3 shots')
        elif b['shots']: fail('only BROLL can generate retrieval shots')
        if b['action']=='CONTINUE_PREVIOUS_VISUAL':
            if not previous or previous['action']=='KEEP_TALKING_HEAD' or b.get('continuation_from')!=previous['id']: fail('continuation_from must reference immediately preceding visual beat')
        elif 'continuation_from' in b: fail('continuation_from only allowed for CONTINUE_PREVIOUS_VISUAL')
        shot_ids=set()
        for s in b['shots']:
            if s['shot_id'] in shot_ids: fail('duplicate shot_id')
            shot_ids.add(s['shot_id'])
            for q in s['image_queries']+s['video_queries']:
                if not 2<=len(q.split())<=10: fail('queries must contain 2–10 words')
                if q!=' '.join(q.split()): fail('queries must use single spaces with no leading/trailing whitespace')
            for kind in ('image_queries','video_queries'):
                if len({q.casefold() for q in s[kind]})!=len(s[kind]): fail('duplicate queries differing only by case')
        previous=b
    if cursor!=len(expected): raise ValueError('$.visual_beats: all transcript chunks must be covered')
    return value


def import_plan(run, plan, package):
    validate_import(plan,package)
    root=run/'editorial'/digest(plan)
    root.mkdir(parents=True,exist_ok=True)
    write_json(root/'imported-plan.json',plan)
    write_json(run/'visual-plan.json',plan)
    marker=run/'transcript-corrections.json'
    if marker.is_file():
        corrections=read(marker); corrections.pop('stale_plan_digest',None);write_json(marker,corrections)
    (run/'editorial-location.json').unlink(missing_ok=True)
    return root


def load_import(run):
    plan=parse_plan((run/'visual-plan.json').read_text(encoding='utf-8'))
    if plan.get('schema_version')!=VERSION: raise ValueError('Import an editorial visual-plan.json before sourcing')
    chunks=normalized_chunks(run)
    duration=max((c['end'] for c in chunks),default=0)
    return validate_import(plan,transcript_package(run,plan['project_id'],duration))


def plan_retrieval_root(run, plan):
    pointer=run/'editorial-location.json'
    if pointer.is_file():
        location=read(pointer)
        if location.get('plan_digest')==digest(plan) and re.fullmatch('[a-f0-9]{64}',str(location.get('directory',''))):
            return run/'editorial'/location['directory']
    return run/'editorial'/digest(plan)


def retrieval_bundle(run):
    plan=load_import(run)
    root=plan_retrieval_root(run,plan); root.mkdir(parents=True,exist_ok=True)
    chunks=[]; internal={'schema_version':'imported-retrieval-1','chunks':{}}; beats=[]
    for b in plan['visual_beats']:
        chunks.append({'id':b['id'],'start':b['start'],'end':b['end'],'text':b['original_text']})
        internal['chunks'][b['id']]={**b,'visual_action':b['action'],'planner_provider':'external-import'}
        beats.append({'id':b['id'],'start_seconds':b['start'],'end_seconds':b['end'],'intent':b['core_meaning'],'broll_queries':[q for s in b['shots'] for q in s['video_queries']], 'visual_plan':b,'external_plan':True})
    return root,chunks,internal,{'beats':beats}


def active_retrieval_root(run):
    try: return retrieval_bundle(run)[0]
    except (OSError,ValueError,KeyError,TypeError): return run


def export_local_producer(result, package):
    """Adapt a completed injected/local experimental producer to the import contract.

    This exports a proposal only. The UI must validate/import it like any other
    producer; incomplete or invalid generation cannot activate sourcing.
    """
    if result.get('status')!='complete': raise ValueError('local producer is incomplete')
    chunks={c['id']:c for c in package['chunks']}; beats=[]
    for b in result['visual_beats']:
        covered=[chunks[cid] for cid in b['covered_chunk_ids']]
        shots=[{k:s[k] for k in ('shot_id','description','image_queries','video_queries')} for s in b['shots']]
        beat={'id':b['visual_beat_id'],'start':covered[0]['start'],'end':covered[-1]['end'],
            'covered_chunk_ids':b['covered_chunk_ids'],'original_text':' '.join(c['text'].strip() for c in covered),
            'action':b['visual_action'],'editorial_function':b['editorial_meaning'],'core_meaning':b['editorial_meaning'],
            'subtext':b.get('subtext',''),'visual_mode':'sequence' if len(shots)>1 else 'single','shots':shots,'avoid':b.get('avoid',[])}
        if beat['action']=='CONTINUE_PREVIOUS_VISUAL': beat['continuation_from']=b['continuity_from']
        beats.append(beat)
    return validate_import({'schema_version':VERSION,'project_id':package['project_id'],
        'transcript_signature':package['transcript_signature'],'global_topic':result.get('narrative',{}).get('global_topic') or ' '.join(b['core_meaning'] for b in beats),
        'visual_beats':beats},package)
