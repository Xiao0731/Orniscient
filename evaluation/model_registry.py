from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Dict, Iterable, Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class ModelSpec:
    alias: str
    provider: str
    model: str
    api_key_env: str
    base_url: str
    enabled: bool = True
    notes: str = ""
    supports_system_prompt: bool = True
    supports_temperature: bool = True
    supports_max_tokens: bool = True

    # Runtime policy metadata for objective evaluation.
    official_default_temperature: Optional[float] = None
    objective_temperature: Optional[float] = None
    omit_temperature_for_objective: bool = False

    # Publicly documented limits. When tier/account/endpoint specific, we keep the
    # most conservative public default here and allow env overrides.
    max_concurrency: Optional[int] = None
    rpm_limit: Optional[int] = None
    tpm_limit: Optional[int] = None
    rate_limit_dynamic: bool = False
    rate_limit_tiered: bool = False


def _normalize_model_name(model_name: str) -> str:
    return model_name.strip().lower()


def _env_prefix(alias: str) -> str:
    return alias.strip().upper().replace("-", "_")


def _parse_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    return float(text)


def _parse_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    return int(text)


def _first_float_env(*names: str) -> Optional[float]:
    for name in names:
        if not name:
            continue
        value = _parse_float(os.getenv(name))
        if value is not None:
            return value
    return None


def _first_int_env(*names: str) -> Optional[int]:
    for name in names:
        if not name:
            continue
        value = _parse_int(os.getenv(name))
        if value is not None:
            return value
    return None


# Judge models are excluded from candidate answering.
JUDGE_MODEL_NAMES = {
    _normalize_model_name("qwen3-max"),
}

MODEL_SPECS: Dict[str, ModelSpec] = {
    "deepseek": ModelSpec(
        alias="deepseek",
        provider="deepseek",
        model="deepseek-chat",
        api_key_env="DEEPSEEK_API_KEY",
        base_url="https://api.deepseek.com",
        notes="DeepSeek-V3.2 non-thinking candidate model.",
        official_default_temperature=1.0,
        objective_temperature=0.0,
        rate_limit_dynamic=True,
    ),
    "qwen": ModelSpec(
        alias="qwen",
        provider="qwen",
        model="qwen3-max",
        api_key_env="QIANWEN_API_KEY",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        notes="Qwen 3 Max flagship model.",
        official_default_temperature=0.7,
        objective_temperature=0.7,
        rpm_limit=600,
        tpm_limit=1_000_000,
    ),
    "qwen3-max": ModelSpec(
        alias="qwen3-max",
        provider="qwen",
        model="qwen3-max",
        api_key_env="QIANWEN_API_KEY",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        notes="Canonical alias for the primary subjective-eval judge.",
        official_default_temperature=0.7,
        objective_temperature=0.7,
        rpm_limit=600,
        tpm_limit=1_000_000,
    ),
    "kimi": ModelSpec(
        alias="kimi",
        provider="kimi",
        model="kimi-k2.5",
        api_key_env="KIMI_API_KEY",
        base_url="https://api.moonshot.cn/v1",
        notes="Long-context Kimi baseline.",
        official_default_temperature=1.0,
        objective_temperature=1.0,
        max_concurrency=1,
        rpm_limit=3,
        tpm_limit=500_000,
        rate_limit_tiered=True,
    ),
    "glm": ModelSpec(
        alias="glm",
        provider="glm",
        model="glm-5",
        api_key_env="GLM_API_KEY",
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        notes="GLM candidate model.",
        official_default_temperature=1.0,
        objective_temperature=1.0,
        rate_limit_dynamic=True,
    ),
    "doubao": ModelSpec(
        alias="doubao",
        provider="doubao",
        model="doubao-seed-2-0-pro-260215",
        api_key_env="DOUBAO_API_KEY",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        notes="Doubao text model on Ark.",
        omit_temperature_for_objective=True,
        rate_limit_dynamic=True,
    ),
    "hunyuan": ModelSpec(
        alias="hunyuan",
        provider="hunyuan",
        model="hunyuan-turbos-latest",
        api_key_env="HUNYU_API_KEY",
        base_url="https://api.hunyuan.cloud.tencent.com/v1",
        notes="Hunyuan flagship text model.",
        official_default_temperature=0.6,
        omit_temperature_for_objective=True,
        max_concurrency=5,
    ),
    "wenxin": ModelSpec(
        alias="wenxin",
        provider="wenxin",
        model="ernie-5.0",
        api_key_env="WENXINYIYAN_API_KEY",
        base_url="https://qianfan.baidubce.com/v2",
        notes="ERNIE text baseline.",
        official_default_temperature=0.95,
        objective_temperature=0.95,
        rate_limit_dynamic=True,
    ),
    "minimax": ModelSpec(
        alias="minimax",
        provider="minimax",
        model="MiniMax-M2.7",
        api_key_env="MINIMAX_API_KEY",
        base_url="https://api.minimaxi.com/v1",
        notes="MiniMax candidate model.",
        official_default_temperature=1.0,
        objective_temperature=1.0,
        rpm_limit=500,
        tpm_limit=20_000_000,
    ),
    "stepfun": ModelSpec(
        alias="stepfun",
        provider="stepfun",
        model="step-3.5-flash",
        api_key_env="STEPFUN_API_KEY",
        base_url="https://api.stepfun.com/v1",
        notes="StepFun OpenAI-compatible text model.",
        official_default_temperature=0.5,
        objective_temperature=0.5,
        max_concurrency=5,
        rpm_limit=10,
        tpm_limit=5_000_000,
        rate_limit_tiered=True,
    ),
    "baichuan": ModelSpec(
        alias="baichuan",
        provider="baichuan",
        model="Baichuan4-Turbo",
        api_key_env="BAICHUAN_API_KEY",
        base_url="https://api.baichuan-ai.com/v1",
        notes="Baichuan general-purpose text model.",
        omit_temperature_for_objective=True,
        rate_limit_dynamic=True,
    ),
}

DEFAULT_ENABLED_ALIASES = [
    "deepseek",
    "qwen",
    "kimi",
    "glm",
    "doubao",
    "hunyuan",
    "wenxin",
    "minimax",
    "stepfun",
    "baichuan",
]


def get_api_key(spec: ModelSpec) -> Optional[str]:
    key = os.getenv(spec.api_key_env, "").strip()
    return key or None


def get_spec(alias: str) -> ModelSpec:
    if alias not in MODEL_SPECS:
        raise KeyError(f"Unknown model alias: {alias}")
    return MODEL_SPECS[alias]


def is_judge_model(spec_or_alias: ModelSpec | str) -> bool:
    if isinstance(spec_or_alias, ModelSpec):
        return _normalize_model_name(spec_or_alias.model) in JUDGE_MODEL_NAMES
    if spec_or_alias in MODEL_SPECS:
        return is_judge_model(MODEL_SPECS[spec_or_alias])
    return _normalize_model_name(spec_or_alias) in JUDGE_MODEL_NAMES


def _iter_specs(selected_aliases: Optional[Iterable[str]] = None) -> list[ModelSpec]:
    aliases = list(selected_aliases or DEFAULT_ENABLED_ALIASES)
    specs: list[ModelSpec] = []
    seen_aliases: set[str] = set()
    for alias in aliases:
        if alias in seen_aliases:
            continue
        seen_aliases.add(alias)
        specs.append(get_spec(alias))
    return specs


def enabled_specs(selected_aliases: Optional[list[str]] = None) -> list[ModelSpec]:
    specs: list[ModelSpec] = []
    for spec in _iter_specs(selected_aliases):
        if get_api_key(spec):
            specs.append(spec)
    return specs


def subjective_candidate_specs(selected_aliases: Optional[list[str]] = None) -> list[ModelSpec]:
    specs = enabled_specs(selected_aliases)
    return [spec for spec in specs if not is_judge_model(spec)]


def resolve_objective_temperature(spec: ModelSpec) -> Optional[float]:
    """
    Resolve the temperature used by the objective evaluation script.

    Priority:
    1. <ALIAS>_OBJECTIVE_TEMPERATURE
    2. <ALIAS>_TEMPERATURE
    3. OBJECTIVE_TEMPERATURE
    4. model-specific objective_temperature
    5. official_default_temperature
    6. None (omit the parameter)
    """
    prefix = _env_prefix(spec.alias)
    override = _first_float_env(
        f"{prefix}_OBJECTIVE_TEMPERATURE",
        f"{prefix}_TEMPERATURE",
        "OBJECTIVE_TEMPERATURE",
    )
    if override is not None:
        return override
    if spec.omit_temperature_for_objective:
        return None
    if spec.objective_temperature is not None:
        return spec.objective_temperature
    return spec.official_default_temperature


def resolve_max_workers(spec: ModelSpec, requested_workers: int) -> int:
    """
    Resolve per-model worker count.

    Priority:
    1. min(requested_workers, <ALIAS>_MAX_WORKERS) if the env override exists
    2. min(requested_workers, spec.max_concurrency) if a public/provider cap is known
    3. requested_workers
    """
    prefix = _env_prefix(spec.alias)
    override = _first_int_env(f"{prefix}_MAX_WORKERS")
    cap = override if override is not None else spec.max_concurrency
    if cap is None:
        return max(1, requested_workers)
    return max(1, min(requested_workers, cap))
