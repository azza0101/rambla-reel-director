const test=require('node:test');const assert=require('node:assert/strict');
const fixtures=require('./oracle.json');
let core;try{core=require('../plugin/core')}catch{}
test('export engine exists',()=>assert.equal(typeof core?.renderSrt,'function'));
for(const c of fixtures)test('V3.1 subtitle bytes: '+c.name,()=>{
 assert.ok(core,'export engine missing');
 const output=core.renderSrt(c.timeline,c.captions,c.ranges,{original:c.original,context:c.context});
 assert.equal(output.split('\r\n# RAMBLA_CONTEXT_BEGIN')[0],c.expected.split('\r\n# RAMBLA_CONTEXT_BEGIN')[0]);
});
test('rejects missing, inverted and invalid ranges',()=>{
 assert.ok(core);for(const ranges of [[],[{a:2,b:1}],[{a:NaN,b:10}]])assert.throws(()=>core.renderSrt(fixtures[0].timeline,fixtures[0].captions,ranges,{}));
});
test('safe filenames prevent Windows devices and path traversal',()=>{
 assert.ok(core);for(const name of ['../x','CON','NUL.srt','a/b','a\\b','a:ads','x.','x\u0000'])assert.throws(()=>core.fileName(name,'Timeline','SINGLE'));
 assert.equal(core.fileName('','Città','SINGLE'),'Città_RANGE.srt');
});

test('context is a continuous chronological transcript without generated timecodes or range metadata',()=>{
 const timeline={name:'QA',fps:25,start:90000,startTC:'01:00:00:00'};
 const captions=[{a:90050,b:90075,content:'capire di che si parla.',track:1,idx:2},{a:90000,b:90025,content:'Un testo\nfluido   per',track:1,idx:1}];
 const ranges=[{a:90000,b:90025}];
 for(const original of [true,false]){
  const text=core.renderSrt(timeline,captions,ranges,{context:true,original});
  const footer=text.split('# RAMBLA_CONTEXT_BEGIN')[1];
  assert.match(footer,/# Un testo fluido per capire di che si parla\./);
  assert.doesNotMatch(footer,/\d{2}:\d{2}:\d{2}|SELECTED_RANGES|# RANGE|\[| \/ /);
  assert.equal(text.split('\r\n# RAMBLA_CONTEXT_BEGIN')[0],core.renderSrt(timeline,captions,ranges,{context:false,original}));
 }
});
