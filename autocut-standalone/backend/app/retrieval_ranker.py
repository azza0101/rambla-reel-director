"""Optional visual relevance ranking; never an editorial producer."""
import os


class ProviderOrderRanker:
    def rank(self, intent, assets):
        return [dict(row, score=1.0-index*0.001, embedding_score=None,
                     reason='provider order; visual relevance not model-scored',
                     providers={'retrieval':'provider-order'}) for index,row in enumerate(assets)]


def create_retrieval_ranker(client_id, model_root, embedding_code_root=None):
    from .retrieval_quality import QualityRanker
    from .qwen_stack import LocalQwenEmbedder,QwenConfig,QwenMultimodalRanker
    from pathlib import Path
    mode=os.environ.get('RAMBLA_RETRIEVAL_RANKING','auto')
    if mode=='provider': return QualityRanker()
    if mode not in {'qwen','auto'}: raise ValueError('RAMBLA_RETRIEVAL_RANKING must be auto, provider or qwen')
    if mode=='auto' and not (Path(model_root)/'Qwen3-VL-Embedding-2B'/'config.json').is_file(): return QualityRanker()
    return QualityRanker(QwenMultimodalRanker(client_id=client_id,
        embed=LocalQwenEmbedder(QwenConfig(model_root=model_root,embedding_code_root=embedding_code_root)),rerank=None,top_k=16))
