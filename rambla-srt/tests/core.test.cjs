const test=require('node:test');const assert=require('node:assert/strict');
const fixtures=require('./oracle.json');
let core;try{core=require('../plugin/core')}catch{}
test('export engine exists',()=>assert.equal(typeof core?.renderSrt,'function'));
for(const c of fixtures)test('V3.1 bytes: '+c.name,()=>{
 assert.ok(core,'export engine missing');
 assert.equal(core.renderSrt(c.timeline,c.captions,c.ranges,{original:c.original,context:c.context}),c.expected);
});
test('rejects missing, inverted and invalid ranges',()=>{
 assert.ok(core);for(const ranges of [[],[{a:2,b:1}],[{a:NaN,b:10}]])assert.throws(()=>core.renderSrt(fixtures[0].timeline,fixtures[0].captions,ranges,{}));
});
test('safe filenames prevent Windows devices and path traversal',()=>{
 assert.ok(core);for(const name of ['../x','CON','NUL.srt','a/b','a\\b','a:ads','x.','x\u0000'])assert.throws(()=>core.fileName(name,'Timeline','SINGLE'));
 assert.equal(core.fileName('','Città','SINGLE'),'Città_RANGE.srt');
});
