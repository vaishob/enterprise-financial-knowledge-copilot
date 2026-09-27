import json
import re
from dataclasses import dataclass
from typing import Callable, Protocol

import httpx

from backend.app.core.config import Settings
from backend.app.domain.schemas import Claim, GeneratedClaims
from backend.app.generation.grounding import build_prompt
from backend.app.ingestion.chunking import token_count
from backend.app.retrieval.text import keyword_coverage


@dataclass
class GenerationResult:
    claims: GeneratedClaims
    input_tokens: int
    output_tokens: int
    estimated: bool = False


class Generator(Protocol):
    def generate(self, question: str, context: list[dict]) -> GenerationResult: ...


class LocalExtractiveGenerator:
    """Transparent extractive reference baseline; no neural language model is called."""
    def __init__(self, settings: Settings):
        self.settings = settings

    def generate(self, question: str, context: list[dict]) -> GenerationResult:
        scored = []
        for index, chunk in enumerate(context):
            for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z])", chunk["text"]):
                score = keyword_coverage(question, sentence)
                if score > 0:
                    scored.append((score + 0.07 / (index+1), sentence, chunk["chunk_id"]))
        scored.sort(key=lambda row: -row[0])
        claims: list[Claim] = []
        seen: set[str] = set()
        threshold = max(0.11, scored[0][0] * 0.45) if scored else 1
        for score, sentence, chunk_id in scored:
            if score < threshold or sentence in seen:
                continue
            if token_count(" ".join(claim.text for claim in claims)) + token_count(sentence) > self.settings.max_completion_tokens:
                continue
            seen.add(sentence)
            claims.append(Claim(text=sentence, quote=sentence, chunk_id=chunk_id))
            if len(claims) == 5:
                break
        output = GeneratedClaims(claims=claims, abstain=not claims)
        input_count = token_count(json.dumps(build_prompt(question, context)))
        return GenerationResult(output, input_count, token_count(output.model_dump_json()), estimated=True)


class OpenAIGenerator:
    def __init__(self, settings: Settings):
        self.settings = settings

    def generate(self, question: str, context: list[dict]) -> GenerationResult:
        assert self.settings.llm_api_key is not None
        payload = {"model": self.settings.llm_model, "messages": build_prompt(question, context),
                   "temperature": self.settings.temperature, "max_tokens": self.settings.max_completion_tokens,
                   "response_format": {"type": "json_object"}}
        with httpx.Client(timeout=self.settings.provider_timeout_seconds) as client:
            response = client.post(self.settings.llm_base_url.rstrip("/") + "/chat/completions",
                                   headers={"Authorization": "Bearer " + self.settings.llm_api_key.get_secret_value()},
                                   json=payload)
            response.raise_for_status()
            data = response.json()
        claims = GeneratedClaims.model_validate_json(data["choices"][0]["message"]["content"])
        usage = data.get("usage", {})
        return GenerationResult(claims, usage.get("prompt_tokens", token_count(json.dumps(payload))),
                                usage.get("completion_tokens", token_count(claims.model_dump_json())),
                                estimated=not bool(usage))


class OllamaGenerator:
    def __init__(self, settings: Settings):
        self.settings = settings

    def generate(self, question: str, context: list[dict]) -> GenerationResult:
        payload = {"model": self.settings.llm_model, "messages": build_prompt(question, context),
                   "stream": False, "format": GeneratedClaims.model_json_schema(),
                   "options": {"temperature": self.settings.temperature,
                               "num_predict": self.settings.max_completion_tokens}}
        with httpx.Client(timeout=self.settings.provider_timeout_seconds) as client:
            response = client.post(self.settings.ollama_base_url.rstrip("/") + "/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
        claims = GeneratedClaims.model_validate_json(data["message"]["content"])
        return GenerationResult(claims, data.get("prompt_eval_count", token_count(json.dumps(payload))),
                                data.get("eval_count", token_count(claims.model_dump_json())),
                                estimated="eval_count" not in data)


class BedrockGenerator:
    def __init__(self, settings: Settings):
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:
            raise RuntimeError("Install the aws extra to use Bedrock") from exc
        self.settings = settings
        session = boto3.Session(profile_name=settings.aws_profile, region_name=settings.aws_region)
        self.client = session.client("bedrock-runtime", config=Config(
            read_timeout=settings.provider_timeout_seconds, connect_timeout=10, retries={"max_attempts": 2}))

    def generate(self, question: str, context: list[dict]) -> GenerationResult:
        messages = build_prompt(question, context)
        data = self.client.converse(
            modelId=self.settings.bedrock_model_id,
            system=[{"text": messages[0]["content"]}],
            messages=[{"role": "user", "content": [{"text": messages[1]["content"]}]}],
            inferenceConfig={"maxTokens": self.settings.max_completion_tokens,
                             "temperature": self.settings.temperature},
        )
        content = "".join(block.get("text", "") for block in data["output"]["message"]["content"])
        claims = GeneratedClaims.model_validate_json(content)
        usage = data.get("usage", {})
        return GenerationResult(claims, usage.get("inputTokens", token_count(json.dumps(messages))),
                                usage.get("outputTokens", token_count(content)), estimated=not bool(usage))


def create_generator(settings: Settings) -> Generator:
    providers: dict[str, Callable[[Settings], Generator]] = {"local": LocalExtractiveGenerator, "openai": OpenAIGenerator,
                 "ollama": OllamaGenerator, "bedrock": BedrockGenerator}
    if settings.llm_provider == "local":
        return LocalExtractiveGenerator(settings)
    return providers[settings.llm_provider](settings)
