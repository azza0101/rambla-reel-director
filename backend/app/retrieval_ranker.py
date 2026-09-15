"""Optional visual relevance ranking; never an editorial producer."""
import os


class ProviderOrderRanker:
    def rank(self, intent, assets):
        return [dict(row, score=1.0-index*0.001, embedding_score=None,
                     reason='provider order; visual relevance not model-scored',
                     providers={'retrieval':'provider-order'}) for index,row in enumerate(assets)]


def create_retrieval_ranker(client_id, model_root, embedding_code_root=None):
    mode=os.environ.get('RAMBLA_RETRIEVAL_RANKING','provider')
    if mode=='provider': return ProviderOrderRanker()
    if mode!='qwen': raise ValueError('RAMBLA_RETRIEVAL_RANKING must be provider or qwen')
    from .qwen_stack import LocalQwenEmbedder,QwenConfig,QwenMultimodalRanker
    return QwenMultimodalRanker(client_id=client_id,
        embed=LocalQwenEmbedder(QwenConfig(model_root=model_root,embedding_code_root=embedding_code_root)),rerank=None,top_k=16)
