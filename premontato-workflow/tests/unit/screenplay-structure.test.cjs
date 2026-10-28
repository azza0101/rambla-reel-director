const test=require('node:test'),assert=require('node:assert/strict');const {applyStructure,prepareLines}=require('../../runtime/premontato/screenplay_structure');test('line labels preserve original words and make action explicit without inventing dialogue',()=>{const p=prepareLines('SCENA 1\nLEI\nArrivo subito.\nLei prende la borsa.\nLEI\nAndiamo!');assert.equal(p.lines.length,3);const t=applyStructure(p,{'L2':'LEI','L3':'A','L5':'LEI'});assert.match(t,/!Lei prende la borsa/);assert.match(t,/Arrivo subito/);assert.throws(()=>applyStructure(p,{'L2':'BOB'}),/struttura/i);});
test('uppercase numbered scene headings survive structure classification',()=>{const p=prepareLines('SCENA 1 CASA\nLEI\nArrivo subito.\nSCENA 2 BOSCO\nLUI\nTi aspetto.');const t=applyStructure(p,{'L2':'LEI','L5':'LUI'});assert.match(t,/SCENA 1 CASA/);assert.match(t,/SCENA 2 BOSCO/);});
test('normalization discards extra context labels but never fills missing lines or guesses roles',()=>{
 const {normalizeStructureLabels}=require('../../runtime/premontato/screenplay_structure');
 const p=prepareLines('SCENA 1\nLEI\nArrivo subito.');
 assert.deepEqual(normalizeStructureLabels(p,{L2:'LEI',L1:'A',L999:'A'}),{L2:'LEI'});
 assert.throws(()=>normalizeStructureLabels(p,{L1:'A'}),/incompleta/i);
 assert.throws(()=>normalizeStructureLabels(p,{L2:'BOB'}),/non valida/i);
 assert.throws(()=>normalizeStructureLabels(p,[]),/non valida/i);
});
