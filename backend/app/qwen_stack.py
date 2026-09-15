"""Optional local Qwen roles; no import or download occurs during capability checks."""

from __future__ import annotations

import importlib
import importlib.util
import json
import math
import os
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .director_engine import ACTIONS, RuleDirector, TextReranker, build_edit_plan


MODEL_NAMES = {
    "asr": "Qwen3-ASR-1.7B",
    "aligner": "Qwen3-ForcedAligner-0.6B",
    "director": "Qwen3.5-4B",
    "embedding": "Qwen3-VL-Embedding-2B",
    "reranker": "Qwen3-VL-Reranker-2B",
    "visual_judge": "Qwen3.5-4B",
}
ROLE_PACKAGE = {
    "asr": "qwen_asr",
    "aligner": "qwen_asr",
    "director": "transformers",
    "embedding": "src.models.qwen3_vl_embedding",
    "reranker": "sentence_transformers",
    "visual_judge": "transformers",
}
RETRIEVAL_INSTRUCTION = "Retrieve images or videos relevant to the user's visual search query."


@dataclass(frozen=True)
class QwenConfig:
    model_root: Path
    director_model: str = "Qwen3.5-4B"
    visual_judge_enabled: bool = False
    embedding_code_root: Path | None = None

    def path(self, role: str) -> Path:
        if role not in MODEL_NAMES:
            raise ValueError("unknown Qwen role")
        root = self.model_root.resolve()
        name = self.director_model if role in {"director", "visual_judge"} else MODEL_NAMES[role]
        if name not in {"Qwen3.5-4B", "Qwen3.5-9B"} and role in {"director", "visual_judge"}:
            raise ValueError("unsupported Director model")
        path = (root / name).resolve()
        if not path.is_relative_to(root):
            raise ValueError("model path escapes configured runtime root")
        return path

    def embedding_source_root(self) -> Path | None:
        value = self.embedding_code_root
        if value is None:
            env = os.environ.get("RAMBLA_QWEN_VL_EMBEDDING_CODE_ROOT")
            value = Path(env) if env else None
        if value is None:
            return None
        root = Path(value).resolve()
        module = root / "src" / "models" / "qwen3_vl_embedding.py"
        return root if module.is_file() else None


def _find_spec(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ModuleNotFoundError, ValueError, AttributeError):
        return False


def _embedding_implementation_available(config: QwenConfig) -> bool:
    return config.embedding_source_root() is not None or _find_spec("src.models.qwen3_vl_embedding")


def capabilities(config: QwenConfig) -> dict[str, dict[str, Any]]:
    result = {}
    for role in MODEL_NAMES:
        path = config.path(role)
        weights = _weights_complete(path)
        package = _embedding_implementation_available(config) if role == "embedding" else _find_spec(ROLE_PACKAGE[role])
        if role == "visual_judge" and not config.visual_judge_enabled:
            reason = "feature flag off"
        elif not weights:
            reason = "local weights missing or incomplete"
        elif not package:
            reason = f"isolated package {ROLE_PACKAGE[role]} missing"
        else:
            reason = "ready for explicit local load"
        result[role] = {
            "available": weights and package and (role != "visual_judge" or config.visual_judge_enabled),
            "reason": reason,
            "model": config.director_model if role in {"director", "visual_judge"} else MODEL_NAMES[role],
            "local_path": str(path),
            "weights_present": weights,
            "package": ROLE_PACKAGE[role],
            "package_present": package,
        }
    return result


def _weights_complete(path: Path) -> bool:
    if not path.is_dir() or not (path / "config.json").is_file():
        return False
    index = path / "model.safetensors.index.json"
    if index.is_file():
        try:
            shards = set(json.loads(index.read_text(encoding="utf-8"))["weight_map"].values())
        except (OSError, ValueError, KeyError, TypeError):
            return False
        return bool(shards) and all(
            (path / name).resolve().is_relative_to(path.resolve())
            and (path / name).is_file()
            and (path / name).stat().st_size > 0
            for name in shards
        )
    single = path / "model.safetensors"
    return single.is_file() and single.stat().st_size > 0


@contextmanager
def offline_model_environment(model_root: Path):
    """Scope Hugging Face cache/offline settings to a local model invocation."""

    root = model_root.resolve()
    cache = root / ".hf-cache"
    cache.mkdir(parents=True, exist_ok=True)
    values = {"HF_HOME": str(cache), "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}
    previous = {key: os.environ.get(key) for key in values}
    try:
        os.environ.update(values)
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class QwenDirector:
    """Closed structured output over an injected, explicitly local text generator."""

    def __init__(self, generate: Callable[[str], str], model_name: str = "Qwen3.5-4B"):
        self.generate = generate
        self.model_name = model_name
        self.last_status = "NOT_RUN"

    def propose(self, beat: dict[str, Any]) -> dict[str, Any] | None:
        prompt = (
            "Return one JSON object only with exactly action, query, reason, parameters. "
            "action is TALKING_HEAD, BROLL, EDITORIAL_INSERT, PUNCH_IN, STICKER or CAPTION_EMPHASIS. "
            "parameters: TALKING_HEAD {}, BROLL {fit:COVER|CONTAIN}, "
            "EDITORIAL_INSERT {presentation:FULL_FRAME|CARD}, PUNCH_IN {scale:1.02..1.35}, "
            "STICKER {label:nonempty text}, CAPTION_EMPHASIS {keyword:nonempty text}. "
            "For BROLL give a specific semantic visual search query. Avoid unsupported inserts. "
            f"Beat context: {json.dumps(beat, ensure_ascii=False, sort_keys=True)}"
        )
        for attempt in range(2):
            try:
                raw = self.generate(prompt)
            except Exception:
                self.last_status = "PROVIDER_ERROR_FALLBACK"
                return None
            try:
                value = json.loads(raw)
                if not isinstance(value, dict) or set(value) != {"action", "query", "reason", "parameters"}:
                    raise ValueError("exact keys required")
                if (
                    value["action"] not in ACTIONS
                    or not isinstance(value["query"], str)
                    or not isinstance(value["reason"], str)
                    or not isinstance(value["parameters"], dict)
                ):
                    raise ValueError("invalid field types or action")
                if not value["reason"].strip() or (value["action"] == "BROLL" and not value["query"].strip()):
                    raise ValueError("reason and BROLL query must be nonempty")
                _validate_parameters(value["action"], value["parameters"])
                self.last_status = "VALID" if attempt == 0 else "REPAIRED"
                return value
            except (ValueError, TypeError, KeyError):
                prompt += "\nPrevious response was invalid. Return only the required valid JSON object; no markdown."
        self.last_status = "INVALID_OUTPUT_FALLBACK"
        return None


def _validate_parameters(action: str, parameters: dict[str, Any]) -> None:
    shapes = {
        "TALKING_HEAD": set(),
        "BROLL": {"fit"},
        "EDITORIAL_INSERT": {"presentation"},
        "PUNCH_IN": {"scale"},
        "STICKER": {"label"},
        "CAPTION_EMPHASIS": {"keyword"},
    }
    if set(parameters) != shapes[action]:
        raise ValueError("parameters must be closed and action-specific")
    if action == "BROLL" and parameters["fit"] not in {"COVER", "CONTAIN"}:
        raise ValueError("invalid BROLL fit")
    if action == "EDITORIAL_INSERT" and parameters["presentation"] not in {"FULL_FRAME", "CARD"}:
        raise ValueError("invalid insert presentation")
    if action == "PUNCH_IN" and (type(parameters["scale"]) not in {int, float} or not 1.02 <= parameters["scale"] <= 1.35):
        raise ValueError("invalid punch scale")
    if action in {"STICKER", "CAPTION_EMPHASIS"}:
        field = "label" if action == "STICKER" else "keyword"
        if not isinstance(parameters[field], str) or not parameters[field].strip():
            raise ValueError("missing editorial text")


class QwenDecisionAdapter:
    provider_name = "qwen-with-rule-fallback"

    def __init__(self, proposals: dict[str, dict[str, Any]], model_name: str):
        self.proposals = proposals
        self.model_name = model_name
        self.fallback = RuleDirector()
        self.last_provider = "deterministic-rule-v1"

    def decide(self, beat: dict[str, Any], selected: dict[str, Any] | None) -> tuple[str, str, dict[str, Any]]:
        proposal = self.proposals.get(beat["id"])
        if proposal is None or (proposal["action"] in {"BROLL", "EDITORIAL_INSERT", "STICKER"} and selected is None):
            self.last_provider = "deterministic-rule-v1"
            return self.fallback.decide(beat, selected)
        self.last_provider = self.model_name
        return proposal["action"], proposal["reason"], proposal["parameters"]


def prepare_qwen_decisions(
    transcript: dict[str, Any], outline: dict[str, Any], director: QwenDirector
) -> tuple[dict[str, Any], QwenDecisionAdapter]:
    """Enrich queries from actual beat speech before retrieval; never mutate inputs."""

    enriched = {**outline, "beats": []}
    proposals = {}
    for beat in outline["beats"]:
        context = " ".join(
            segment["text"].strip()
            for segment in transcript["segments"]
            if segment["start"] < beat["end_seconds"] and segment["end"] > beat["start_seconds"]
        )
        proposal = director.propose(
            {"id": beat["id"], "intent": beat["intent"], "transcript": context, "original_queries": beat.get("broll_queries", [])}
        )
        row = dict(beat)
        if proposal is not None:
            proposals[beat["id"]] = proposal
            if proposal["query"].strip():
                row["broll_queries"] = [proposal["query"].strip()]
        enriched["beats"].append(row)
    return enriched, QwenDecisionAdapter(proposals, director.model_name)


def compose_qwen_plan(
    transcript: dict[str, Any],
    outline: dict[str, Any],
    assets: list[dict[str, Any]],
    *,
    client_id: str,
    source_frames: int,
    generator: Callable[[str], str] | None = None,
    embedder: Callable[[list[Any]], list[list[float]]] | None = None,
    reranker: Callable[[str, list[dict[str, Any]]], list[float]] | None = None,
    director_model: str = "Qwen3.5-4B",
) -> dict[str, Any]:
    """Compose only configured local model roles; other roles use deterministic rules."""

    if generator is not None:
        enriched, director = prepare_qwen_decisions(transcript, outline, QwenDirector(generator, director_model))
    else:
        enriched, director = outline, RuleDirector()
    ranker = (
        QwenMultimodalRanker(client_id=client_id, embed=embedder, rerank=reranker)
        if embedder
        else QwenMetadataReranker(client_id=client_id, rerank=reranker)
        if reranker
        else None
    )
    return build_edit_plan(
        transcript,
        enriched,
        assets,
        client_id=client_id,
        source_frames=source_frames,
        director=director,
        reranker=ranker,
    )


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("embedding dimensions mismatch")
    norm = math.sqrt(sum(x * x for x in left) * sum(x * x for x in right))
    if norm == 0:
        raise ValueError("zero embedding vector")
    return sum(x * y for x, y in zip(left, right)) / norm


class QwenMultimodalRanker:
    """Client-scoped embedding retrieval followed by top-K reranking."""

    def __init__(
        self,
        *,
        client_id: str,
        embed: Callable[[list[Any]], list[list[float]]],
        rerank: Callable[[str, list[dict[str, Any]]], list[float]] | None,
        top_k: int = 10,
    ):
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        self.client_id, self.embed, self.rerank, self.top_k = client_id, embed, rerank, top_k

    def rank(self, query: str, assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if any(asset.get("client_id") != self.client_id for asset in assets):
            raise ValueError("client asset isolation violation before embedding")
        if not assets:
            return []
        if any(asset.get("kind") == "video" and not asset.get("keyframe_path") for asset in assets):
            raise ValueError("video asset requires an explicit local keyframe_path for multimodal embedding")
        documents = [
            asset.get("keyframe_path") or asset.get("path")
            if asset.get("kind") in {"image", "video"}
            else asset.get("description", "")
            for asset in assets
        ]
        vectors = self.embed([query, *documents])
        if len(vectors) != len(assets) + 1:
            raise ValueError("embedding provider returned wrong vector count")
        rows = []
        for asset, vector in zip(assets, vectors[1:]):
            score = round(_cosine(vectors[0], vector), 4)
            row = {
                "id": asset["id"],
                "client_id": asset["client_id"],
                "path": asset["path"],
                "description": asset.get("description", ""),
                "kind": asset.get("kind", "unknown"),
                "embedding_score": score,
                "reranker_score": None,
                "score": score,
                "reason": "multimodal semantic embedding",
                "providers": {"embedding": "Qwen3-VL-Embedding-2B", "reranker": None},
            }
            for key in (
                "source",
                "source_page",
                "provider_id",
                "creator",
                "rights_state",
                "preview_path",
                "selected_full_download",
                "query",
            ):
                if key in asset:
                    row[key] = asset[key]
            rows.append(row)
        rows.sort(key=lambda row: (-row["embedding_score"], row["id"]))
        if self.rerank is None:
            return rows
        shortlist = rows[: self.top_k]
        scores = self.rerank(query, shortlist)
        if len(scores) != len(shortlist) or any(
            not math.isfinite(float(score)) or not 0 <= float(score) <= 1 for score in scores
        ):
            raise ValueError("reranker returned invalid scores")
        for row, score in zip(shortlist, scores):
            row["reranker_score"] = round(float(score), 4)
            row["score"] = round((row["embedding_score"] + row["reranker_score"]) / 2, 4)
            row["reason"] = "embedding and visual/context rerank"
            row["providers"]["reranker"] = "Qwen3-VL-Reranker-2B"
        return sorted(shortlist, key=lambda row: (-row["score"], row["id"])) + rows[self.top_k :]


class QwenMetadataReranker:
    """Use local metadata retrieval when only the Qwen reranker is installed."""

    def __init__(self, *, client_id: str, rerank: Callable[[str, list[dict[str, Any]]], list[float]], top_k: int = 10):
        self.client_id, self.rerank, self.top_k = client_id, rerank, top_k

    def rank(self, query: str, assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if any(asset.get("client_id") != self.client_id for asset in assets):
            raise ValueError("client asset isolation violation before reranking")
        rows = TextReranker().rank(query, assets)
        shortlist = rows[: self.top_k]
        if not shortlist:
            return rows
        scores = self.rerank(query, shortlist)
        if len(scores) != len(shortlist) or any(
            not math.isfinite(float(score)) or not 0 <= float(score) <= 1 for score in scores
        ):
            raise ValueError("reranker returned invalid scores")
        for row, score in zip(shortlist, scores):
            row["reranker_score"] = round(float(score), 4)
            row["score"] = round((row["score"] + row["reranker_score"]) / 2, 4)
            row["providers"]["reranker"] = "Qwen3-VL-Reranker-2B"
            row["reason"] += "; Qwen metadata rerank"
        return sorted(shortlist, key=lambda row: (-row["score"], row["id"])) + rows[self.top_k :]


class QwenVisualJudge:
    def __init__(self, judge: Callable[[dict[str, Any], dict[str, Any]], bool], *, enabled: bool = False):
        self.judge = judge
        self.enabled = enabled

    def check(self, beat: dict[str, Any], asset: dict[str, Any]) -> bool | None:
        return bool(self.judge(beat, asset)) if self.enabled else None


class ModelUnavailable(RuntimeError):
    pass


class _LocalModel:
    role: str

    def __init__(self, config: QwenConfig):
        self.config = config
        self.model: Any = None
        self.completed_calls = 0

    def _local_path(self) -> Path:
        state = capabilities(self.config)[self.role]
        if not state["available"]:
            raise ModelUnavailable(f"{self.role}: {state['reason']}; path={state['local_path']}")
        return self.config.path(self.role)


class LocalQwenASR(_LocalModel):
    role = "asr"

    def load(self) -> "LocalQwenASR":
        path = self._local_path()
        import torch
        from qwen_asr import Qwen3ASRModel

        kwargs: dict[str, Any] = {
            "dtype": torch.bfloat16,
            "device_map": "cuda:0",
            "max_inference_batch_size": 1,
        }
        if capabilities(self.config)["aligner"]["available"]:
            kwargs["forced_aligner"] = str(self.config.path("aligner"))
            kwargs["forced_aligner_kwargs"] = {"dtype": torch.bfloat16, "device_map": "cuda:0"}
        self.model = Qwen3ASRModel.from_pretrained(str(path), **kwargs)
        return self

    def transcribe(self, audio_path: Path, *, language: str = "Italian") -> Any:
        if self.model is None:
            self.load()
        result = self.model.transcribe(
            audio=str(audio_path),
            language=language,
            return_time_stamps=capabilities(self.config)["aligner"]["available"],
        )
        self.completed_calls += 1
        return result


class LocalQwenDirectorGenerator(_LocalModel):
    role = "director"

    def load(self) -> "LocalQwenDirectorGenerator":
        started = time.perf_counter()
        path = self._local_path()
        import torch
        try:
            from transformers import AutoModelForMultimodalLM, AutoProcessor
            from transformers.models.auto.configuration_auto import CONFIG_MAPPING_NAMES
            if 'qwen3_5' not in CONFIG_MAPPING_NAMES:
                raise ImportError('qwen3_5 not registered')
        except ImportError:
            raise ModelUnavailable('Director requires an explicitly configured local Qwen3.5-compatible Transformers runtime; current runtime lacks qwen3_5 support. No automatic install or template fallback.') from None

        self.processor = AutoProcessor.from_pretrained(str(path), local_files_only=True)
        self.model = AutoModelForMultimodalLM.from_pretrained(
            str(path), local_files_only=True, device_map='cuda:0', dtype=torch.bfloat16,
        )
        self.load_seconds = time.perf_counter()-started
        return self

    def __call__(self, prompt: str) -> str:
        call_started = time.perf_counter()
        if self.model is None:
            self.load()
        messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        inputs = self.processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
            enable_thinking=False,
        ).to(self.model.device)
        output = self.model.generate(**inputs, max_new_tokens=4096, do_sample=False, eos_token_id=self.processor.tokenizer.eos_token_id)
        text = self.processor.decode(
            output[0][inputs["input_ids"].shape[-1] :], skip_special_tokens=True
        )
        elapsed = time.perf_counter() - call_started
        generated_tokens = len(output[0]) - inputs["input_ids"].shape[-1]
        self.last_metrics = {"input_tokens": inputs["input_ids"].shape[-1], "output_tokens": generated_tokens, "seconds": elapsed, "output_tokens_per_second": generated_tokens / max(elapsed, 1e-9)}
        self.completed_calls += 1
        return text


def _load_official_qwen_vl_embedder(path: Path, config: QwenConfig) -> Any:
    source_root = config.embedding_source_root()
    if source_root is not None and str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))
    try:
        module = importlib.import_module("src.models.qwen3_vl_embedding")
        embedder = getattr(module, "Qwen3VLEmbedder")
    except (ImportError, AttributeError) as exc:
        raise ModelUnavailable(
            "embedding: official QwenLM/Qwen3-VL-Embedding implementation is missing; "
            "configure RAMBLA_QWEN_VL_EMBEDDING_CODE_ROOT or embedding_code_root"
        ) from exc
    return embedder(model_name_or_path=str(path))


class LocalQwenEmbedder(_LocalModel):
    role = "embedding"

    def __init__(self, config: QwenConfig, factory: Callable[[Path], Any] | None = None):
        super().__init__(config)
        self.factory = factory

    def load(self) -> "LocalQwenEmbedder":
        path = self.config.path(self.role)
        if not _weights_complete(path):
            raise ModelUnavailable(f"embedding: local weights missing or incomplete; path={path}")
        if self.factory is not None:
            self.model = self.factory(path)
        else:
            if not _embedding_implementation_available(self.config):
                raise ModelUnavailable(
                    "embedding: official QwenLM/Qwen3-VL-Embedding implementation is missing"
                )
            self.model = _load_official_qwen_vl_embedder(path, self.config)
        return self

    def __call__(self, items: list[Any]) -> list[list[float]]:
        if self.model is None:
            self.load()
        payload: list[dict[str, Any]] = []
        for index, item in enumerate(items):
            if isinstance(item, str) and Path(item).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                payload.append({"image": item})
            else:
                row: dict[str, Any] = {"text": str(item)}
                if index == 0:
                    row["instruction"] = RETRIEVAL_INSTRUCTION
                payload.append(row)
        result = self.model.process(payload)
        if hasattr(result, "detach"):
            vectors = result.detach().float().cpu().tolist()
        elif hasattr(result, "tolist"):
            vectors = result.tolist()
        else:
            vectors = [list(vector) for vector in result]
        self.completed_calls += 1
        return vectors


class LocalQwenReranker(_LocalModel):
    role = "reranker"

    def load(self) -> "LocalQwenReranker":
        path = self._local_path()
        from sentence_transformers import CrossEncoder

        self.model = CrossEncoder(str(path), local_files_only=True)
        return self

    def __call__(self, query: str, rows: list[dict[str, Any]]) -> list[float]:
        if self.model is None:
            self.load()
        import torch

        pairs = [(query, row.get("description", "")) for row in rows]
        scores = [
            float(score)
            for score in self.model.predict(pairs, activation_fn=torch.nn.Sigmoid())
        ]
        self.completed_calls += 1
        return scores
