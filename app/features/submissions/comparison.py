"""Comparison and normalisation pipeline with asynchronous strategy fan-out."""

from __future__ import annotations

import asyncio
import ast
import hashlib
import math
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

DEFAULT_FLOAT_EPS = 1e-6
LARGE_OUTPUT_THRESHOLD = 2 * 1024 * 1024  # 2MB


class ComparisonMode:
    AUTO = "AUTO"
    STRICT = "STRICT"
    TRIM_EOL = "TRIM_EOL"
    NORMALISE_WHITESPACE = "NORMALISE_WHITESPACE"
    CANONICAL_PY_LITERAL = "CANONICAL_PY_LITERAL"
    FLOAT_EPS = "FLOAT_EPS"
    TOKEN_SET = "TOKEN_SET"
    HASH_SHA256 = "HASH_SHA256"


@dataclass
class CompareConfig:
    float_eps: float = DEFAULT_FLOAT_EPS
    unicode_nf: str = "NFC"
    large_output_threshold: int = LARGE_OUTPUT_THRESHOLD
    token_set_size_limit: int = 512

    def clone(self) -> CompareConfig:
        return CompareConfig(
            float_eps=self.float_eps,
            unicode_nf=self.unicode_nf,
            large_output_threshold=self.large_output_threshold,
            token_set_size_limit=self.token_set_size_limit,
        )


@dataclass
class CompareAttempt:
    mode: str
    passed: Optional[bool]
    normalisations: List[str]
    reason: Optional[str] = None
    duration_ms: Optional[float] = None
    priority: int = 0


@dataclass
class CompareResult:
    passed: bool
    mode_applied: Optional[str]
    normalisations_applied: List[str]
    reason: Optional[str]
    attempts: List[CompareAttempt] = field(default_factory=list)


StrategyHandler = Callable[[str, str, CompareConfig, Dict[str, Any]], Tuple[Optional[bool], List[str], Optional[str]]]


def _unicode_normalise(s: str, form: str = "NFC") -> str:
    try:
        return unicodedata.normalize(form, s)
    except Exception:
        return s


def _strip_eol(s: str) -> str:
    return s.rstrip("\r\n")


def _collapse_whitespace(s: str) -> str:
    out_lines = []
    for ln in s.split("\n"):
        parts = [p for p in ln.split()]
        out_lines.append(" ".join(parts))
    return "\n".join(out_lines)


def _remove_all_whitespace(s: str) -> str:
    return "".join(ch for ch in s if not ch.isspace())


def _literal_parse(s: str):
    try:
        return ast.literal_eval(s)
    except Exception:
        return None


def _is_numeric(val: Any) -> bool:
    return isinstance(val, (int, float)) and not isinstance(val, bool)


def _float_equal(a: float, b: float, eps: float) -> bool:
    if math.isinf(a) or math.isinf(b) or math.isnan(a) or math.isnan(b):
        return a == b
    if abs(a - b) <= eps:
        return True
    if abs(a) > 1:
        return abs(a - b) / abs(a) <= eps
    return False


def _deep_equal(a: Any, b: Any, cfg: CompareConfig) -> bool:
    if type(a) != type(b):  # noqa: E721
        return False
    if _is_numeric(a) and _is_numeric(b):
        return _float_equal(float(a), float(b), cfg.float_eps)
    if isinstance(a, (str, bool)) or a is None:
        return a == b
    if isinstance(a, (list, tuple)):
        if len(a) != len(b):
            return False
        return all(_deep_equal(x, y, cfg) for x, y in zip(a, b))
    if isinstance(a, dict):
        if set(a.keys()) != set(b.keys()):
            return False
        for key in a.keys():
            if not _deep_equal(a[key], b[key], cfg):
                return False
        return True
    if isinstance(a, set):
        return a == b
    return a == b


def _token_set(s: str) -> set[str]:
    return {tok for tok in s.split() if tok}


class ComparatorStrategy:
    def __init__(
        self,
        mode: str,
        handler: StrategyHandler,
        *,
        priority: int = 100,
        include_in_auto: bool = True,
    ) -> None:
        self.mode = mode
        self._handler = handler
        self.priority = priority
        self.include_in_auto = include_in_auto

    async def evaluate(
        self,
        expected: str,
        actual: str,
        cfg: CompareConfig,
        overrides: Dict[str, Any],
    ) -> CompareAttempt:
        start = time.perf_counter()
        outcome, normalisations, reason = await asyncio.to_thread(
            self._handler, expected, actual, cfg, overrides
        )
        duration_ms = (time.perf_counter() - start) * 1000.0
        return CompareAttempt(
            mode=self.mode,
            passed=outcome,
            normalisations=normalisations,
            reason=reason,
            duration_ms=duration_ms,
            priority=self.priority,
        )


class ComparatorRegistry:
    def __init__(self) -> None:
        self._strategies: Dict[str, ComparatorStrategy] = {}
        self._auto_order: List[str] = []

    def register(self, strategy: ComparatorStrategy) -> None:
        self._strategies[strategy.mode] = strategy
        if strategy.include_in_auto and strategy.mode not in self._auto_order:
            self._auto_order.append(strategy.mode)

    def for_mode(self, mode: Optional[str]) -> List[ComparatorStrategy]:
        if not mode or mode == ComparisonMode.AUTO:
            return sorted(
                (self._strategies[name] for name in self._auto_order),
                key=lambda strat: strat.priority,
            )
        strat = self._strategies.get(mode)
        return [strat] if strat else []

    def strategy(self, mode: str) -> Optional[ComparatorStrategy]:
        return self._strategies.get(mode)

    def list_modes(self) -> List[str]:
        return [strat.mode for strat in sorted(self._strategies.values(), key=lambda s: s.priority)]


registry = ComparatorRegistry()


def _handle_strict(exp: str, act: str, cfg: CompareConfig, overrides: Dict[str, Any]) -> Tuple[Optional[bool], List[str], Optional[str]]:
    outcome = exp == act
    return (outcome, [], None if outcome else "Mismatch under STRICT")


def _handle_trim_eol(exp: str, act: str, cfg: CompareConfig, overrides: Dict[str, Any]):
    exp2, act2 = _strip_eol(exp), _strip_eol(act)
    if exp2 == act2:
        return True, ["trim_eol"], None
    return None, ["trim_eol"], None


def _handle_whitespace(exp: str, act: str, cfg: CompareConfig, overrides: Dict[str, Any]):
    exp2, act2 = _collapse_whitespace(exp), _collapse_whitespace(act)
    if exp2 == act2:
        return True, ["ws_conservative"], None
    exp3, act3 = _remove_all_whitespace(exp), _remove_all_whitespace(act)
    if exp3 == act3:
        return True, ["ws_aggressive"], None
    return None, ["ws_checked"], None


def _handle_literal(exp: str, act: str, cfg: CompareConfig, overrides: Dict[str, Any]):
    pe, pa = _literal_parse(exp), _literal_parse(act)
    if pe is None or pa is None:
        return None, ["py_literal"], None
    if _deep_equal(pe, pa, cfg):
        return True, ["py_literal"], None
    return False, ["py_literal"], "Literal structures differ"


def _resolve_eps(cfg: CompareConfig, overrides: Dict[str, Any]) -> float:
    if "float_eps" in overrides:
        try:
            return float(overrides["float_eps"])
        except Exception:
            pass
    if isinstance(overrides.get("float"), dict) and "eps" in overrides["float"]:
        try:
            return float(overrides["float"]["eps"])
        except Exception:
            pass
    return cfg.float_eps


def _handle_float_eps(exp: str, act: str, cfg: CompareConfig, overrides: Dict[str, Any]):
    pe, pa = _literal_parse(exp), _literal_parse(act)
    if pe is None or pa is None or not (_is_numeric(pe) and _is_numeric(pa)):
        return None, [], None
    eps = _resolve_eps(cfg, overrides)
    ok = _float_equal(float(pe), float(pa), eps)
    info = [f"float_eps={eps}"]
    if ok:
        return True, info, None
    return False, info, f"Numeric mismatch over eps {eps}"


def _resolve_token_limit(cfg: CompareConfig, overrides: Dict[str, Any]) -> int:
    if "token_set_limit" in overrides:
        try:
            return int(overrides["token_set_limit"])
        except Exception:
            pass
    if isinstance(overrides.get("token"), dict) and "limit" in overrides["token"]:
        try:
            return int(overrides["token"]["limit"])
        except Exception:
            pass
    return cfg.token_set_size_limit


def _handle_token_set(exp: str, act: str, cfg: CompareConfig, overrides: Dict[str, Any]):
    limit = max(0, _resolve_token_limit(cfg, overrides))
    if limit and (len(exp) > limit or len(act) > limit):
        return None, [f"token_limit={limit}"], None
    if _token_set(exp) == _token_set(act):
        return True, ["token_set"], None
    return False, ["token_set"], "Token sets differ"


registry.register(ComparatorStrategy(ComparisonMode.STRICT, _handle_strict, priority=0))
registry.register(ComparatorStrategy(ComparisonMode.TRIM_EOL, _handle_trim_eol, priority=10))
registry.register(ComparatorStrategy(ComparisonMode.NORMALISE_WHITESPACE, _handle_whitespace, priority=20))
registry.register(ComparatorStrategy(ComparisonMode.CANONICAL_PY_LITERAL, _handle_literal, priority=30))
registry.register(ComparatorStrategy(ComparisonMode.FLOAT_EPS, _handle_float_eps, priority=40))
registry.register(ComparatorStrategy(ComparisonMode.TOKEN_SET, _handle_token_set, priority=50))


def _apply_overrides(base_cfg: CompareConfig, overrides: Optional[Dict[str, Any]]) -> CompareConfig:
    if not overrides:
        return base_cfg
    cfg = base_cfg.clone()
    if "float_eps" in overrides:
        try:
            cfg.float_eps = float(overrides["float_eps"])
        except Exception:
            pass
    if "unicode_nf" in overrides:
        try:
            cfg.unicode_nf = str(overrides["unicode_nf"])
        except Exception:
            pass
    if "large_output_threshold" in overrides:
        try:
            cfg.large_output_threshold = int(overrides["large_output_threshold"])
        except Exception:
            pass
    if "token_set_limit" in overrides:
        try:
            cfg.token_set_size_limit = int(overrides["token_set_limit"])
        except Exception:
            pass
    return cfg


async def compare(
    expected: str,
    actual: str,
    cfg: Optional[CompareConfig] = None,
    *,
    mode: Optional[str] = None,
    compare_config: Optional[Dict[str, Any]] = None,
) -> CompareResult:
    base_cfg = cfg or CompareConfig()
    effective_cfg = _apply_overrides(base_cfg, compare_config)
    base_norms: List[str] = []

    expected_norm = _unicode_normalise(expected or "", effective_cfg.unicode_nf).replace("\r\n", "\n")
    actual_norm = _unicode_normalise(actual or "", effective_cfg.unicode_nf).replace("\r\n", "\n")
    base_norms.append(f"unicode_{effective_cfg.unicode_nf.lower()}")

    threshold = max(0, effective_cfg.large_output_threshold)
    if threshold and (len(expected_norm) >= threshold or len(actual_norm) >= threshold):
        exp_hash = hashlib.sha256(expected_norm.encode()).hexdigest()
        act_hash = hashlib.sha256(actual_norm.encode()).hexdigest()
        base_norms.append(f"hash_threshold={threshold}")
        if exp_hash == act_hash:
            return CompareResult(True, ComparisonMode.HASH_SHA256, base_norms, None)
        return CompareResult(
            False,
            ComparisonMode.HASH_SHA256,
            base_norms,
            "Hash mismatch for large output",
        )

    if expected_norm == actual_norm:
        return CompareResult(True, ComparisonMode.STRICT, base_norms, None)

    strategies = registry.for_mode(mode)
    if not strategies:
        return CompareResult(False, None, base_norms, "No comparator strategies available")

    overrides = compare_config or {}
    tasks: List[tuple[ComparatorStrategy, asyncio.Task[CompareAttempt]]] = []
    attempts: List[CompareAttempt] = []

    async with asyncio.TaskGroup() as tg:
        for strat in strategies:
            task = tg.create_task(strat.evaluate(expected_norm, actual_norm, effective_cfg, overrides))
            tasks.append((strat, task))

    for strat, task in tasks:
        attempt = task.result()
        attempts.append(attempt)

    attempts.sort(key=lambda att: (att.priority, att.mode))

    success_attempt = next((att for att in attempts if att.passed is True), None)
    failure_attempt = next((att for att in attempts if att.passed is False), None)

    if success_attempt:
        norms = base_norms + success_attempt.normalisations
        return CompareResult(True, success_attempt.mode, norms, None, attempts=attempts)

    if failure_attempt:
        norms = base_norms + failure_attempt.normalisations
        reason = failure_attempt.reason or f"Mismatch under {failure_attempt.mode}"
        return CompareResult(False, failure_attempt.mode, norms, reason, attempts=attempts)

    return CompareResult(False, None, base_norms, "No comparator matched", attempts=attempts)


def maybe_hash_large(expected: str) -> Optional[str]:
    if expected is None:
        return None
    if len(expected) >= LARGE_OUTPUT_THRESHOLD:
        return hashlib.sha256(expected.encode()).hexdigest()
    return None


def supported_modes(include_auto: bool = True) -> List[str]:
    modes = registry.list_modes()
    if include_auto:
        return [ComparisonMode.AUTO, *modes]
    return modes


def resolve_mode(value: Optional[str]) -> str:
    if value is None:
        return ComparisonMode.AUTO
    candidate = str(value).strip().upper()
    if not candidate:
        return ComparisonMode.AUTO
    if candidate == ComparisonMode.AUTO:
        return ComparisonMode.AUTO
    return candidate if registry.strategy(candidate) else ComparisonMode.AUTO


__all__ = [
    "ComparisonMode",
    "CompareConfig",
    "CompareAttempt",
    "CompareResult",
    "compare",
    "maybe_hash_large",
    "supported_modes",
    "resolve_mode",
]
