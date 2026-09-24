def test_actual_overlay_evidence_demotes_social_frame():
    from backend.app.retrieval_quality import QualityRanker
    class Visual:
        def rank(self, query, rows):
            return [dict(r, embedding_score=(.82 if r['id']=='text' else .20) if 'superimposed' in query else (.70 if query=='airplane window' else .1)) for r in rows]
    rows=[{'id':i,'kind':'video','provider':'tiktok','title':'airplane window','description':'airplane window'} for i in ['text','clean']]
    results={r['id']:r for r in QualityRanker(Visual()).rank('airplane window',rows)}
    assert results['text']['quality_state']=='rejected'
    assert results['clean']['score']>results['text']['score']
    assert any('superimposed' in r for r in results['text']['quality_reasons'])
