"""Compare locally captured real captions against original Lua, without changing Resolve."""
import importlib.util
import json
import subprocess
from pathlib import Path
from lupa import LuaRuntime
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('oracle',root/'tests/generate_oracle.py')
oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
qa=root.parent/'_qa';live=json.loads((qa/'live-snapshot.json').read_text('utf-8'))
t=live['timeline'];start=t['start'];end=t['finish']
cases=[]
for original in [True,False]:
 for context in [True,False]:
  for mode in ['SINGLE','MULTI']:
   marks=[{'a':0,'b':end-start}] if mode=='SINGLE' else [{'a':100,'b':min(2000,end-start)},{'a':1500,'b':min(3000,end-start)}]
   case={**live,'mode':mode,'marks':marks,'original':original,'context':context}
   lua=LuaRuntime();lua.globals().case=oracle.lua_value(lua,case);lua.execute(oracle.HARNESS);lua.execute(oracle.SOURCE.read_text('utf-8'))
   assert lua.globals().output,lua.globals().lastPrint
   case['ranges']=[{'a':start+r['a'],'b':start+r['b']} for r in marks];case['expected']=lua.globals().output;cases.append(case)
(qa/'live-oracle.json').write_text(json.dumps(cases,ensure_ascii=False),'utf-8')
js="const fs=require('fs'),assert=require('assert/strict'),{renderSrt}=require('./rambla-srt/plugin/core');for(const c of JSON.parse(fs.readFileSync('_qa/live-oracle.json')))assert.equal(renderSrt(c.timeline,c.captions,c.ranges,c),c.expected);console.log('8 live-caption parity cases PASS');"
subprocess.run(['node','-e',js],cwd=root.parent,check=True)
(qa/'live-result.json').write_text(json.dumps({'captions':len(live['captions']),'cases':8,'byteParity':True,'resolveMutations':0,'rangeSource':'local test intervals; live timeline had no IN/OUT'},indent=2),'utf-8')
