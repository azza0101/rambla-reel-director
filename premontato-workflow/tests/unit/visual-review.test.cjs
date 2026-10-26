const test=require('node:test');
const assert=require('node:assert/strict');
const {Session,prepareReviewTimeline}=require('../../plugin/session');
test('visual confirmation is validated atomically and invalidated on reselection',async()=>{
 const s=new Session('unused','unused');
 s.state.media=[{media_id:'m',duration_frames:100}];
 s.state.analysis={parsedBeats:[{character:'LUCA',kind:'dialogue'}],shots:[],visualReview:{intervals:[{segment_id:'s',media_id:'m',start_frame:0,end_frame:100,shot_size:'close',visible_subjects:[]}],confirmed:false},plan:null};
 await assert.rejects(s.confirmVisualReview({confirmed:true,intervals:[{segment_id:'s',shot_size:'close',visible_subjects:['IMPOSTORE']}]}),/personaggio/i);
 assert.equal(s.state.analysis.visualReview.confirmed,false);
 await s.confirmVisualReview({confirmed:true,intervals:[{segment_id:'s',shot_size:'wide',visible_subjects:['LUCA']} ]});
 assert.equal(s.state.analysis.visualReview.confirmed,true);
 assert.equal(s.state.analysis.shots[0].shot_size,'wide');
 s.setMedia([],{projectId:'p',timelineId:'t'});assert.equal(s.state.analysis,null);
});
test('timeline refuses pending visual review even with dialogue confirmation',()=>{
 assert.throws(()=>prepareReviewTimeline({decisions:[{beat_id:'a'}],visual_review_required:true},true),/inquadrature/i);
});
