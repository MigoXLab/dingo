"""Deterministic comparison of tool interactions; no tool-specific exemptions."""

import json
import math
from collections import Counter, OrderedDict
from dataclasses import dataclass
from itertools import groupby
from typing import Any, Optional


DEFAULT_SETTINGS = {
    "threshold": 0.95,
    "min_repeats": 3,
    "result_ngram_size": 5,
    "result_match_mode": "ngram",
}


@dataclass(frozen=True)
class LoopSettings:
    threshold: float = 0.95
    min_repeats: int = 3
    result_ngram_size: int = 5
    result_match_mode: str = "ngram"

    @classmethod
    def from_config(cls, config):
        values = dict(DEFAULT_SETTINGS)
        if config is not None:
            values.update({k: v for k, v in config.model_dump().items()
                           if k in values and v is not None})
        threshold = values["threshold"]
        if (isinstance(threshold, bool) or not isinstance(threshold, (int, float))
                or not math.isfinite(threshold) or not 0 < threshold <= 1):
            raise ValueError("Loop threshold must be finite and in (0, 1].")
        for key, minimum in (("min_repeats", 2), ("result_ngram_size", 1)):
            value = values[key]
            if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
                raise ValueError(f"Loop {key} must be an integer >= {minimum}.")
        if values["result_match_mode"] not in ("ngram", "exact"):
            raise ValueError("Loop result_match_mode must be 'ngram' or 'exact'.")
        return cls(**values)


def canonical_args(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class TraceCall:
    position: int
    source_index: int
    name: str
    action_key: Optional[tuple]
    result: Optional[str]
    segment_id: Any
    call_id: Optional[str]

    @property
    def comparable(self) -> bool:
        return self.action_key is not None and self.result is not None


def extract_calls(items: list) -> list[TraceCall]:
    """Keep invalid/unobserved entries as barriers, never join across them."""
    calls = []
    for position, item in enumerate(items):
        item = item if isinstance(item, dict) else {}
        name = item.get("tool_name") or item.get("name")
        name = name if isinstance(name, str) else ""
        action = None
        for key in ("args", "arguments", "tool_input", "input"):
            if key in item:
                try:
                    action = (name, canonical_args(item[key])) if name else None
                except (TypeError, ValueError):
                    pass
                break
        present = item.get("result_present", "result" in item)
        result = item.get("result")
        if present is not True or not isinstance(result, str):
            result = None
        else:
            result = result.replace("\r\n", "\n")
        source_index = item.get("call_index", position)
        if (isinstance(source_index, bool) or not isinstance(source_index, int)
                or source_index < 0):
            source_index = position
        calls.append(TraceCall(position, source_index, name, action, result,
                               item.get("segment_id", 0), item.get("call_id")))
    return calls


class ResultSimilarity:
    """Per-record feature cache and bounded symmetric pair cache."""

    def __init__(self, settings: LoopSettings, cache_size: int = 4096):
        self.settings = settings
        self.features = {}
        self.pairs = OrderedDict()
        self.cache_size = cache_size

    def _features(self, call: TraceCall):
        if call.position not in self.features:
            text = call.result
            n = self.settings.result_ngram_size
            counts = Counter(text[i:i + n] for i in range(len(text) - n + 1))
            self.features[call.position] = (counts, sum(counts.values()))
        return self.features[call.position]

    def __call__(self, a: TraceCall, b: TraceCall) -> float:
        key = tuple(sorted((a.position, b.position)))
        if key in self.pairs:
            self.pairs.move_to_end(key)
            return self.pairs[key]
        if a.result == b.result:
            score = 1.0
        elif self.settings.result_match_mode == "exact":
            score = 0.0
        elif min(len(a.result), len(b.result)) < self.settings.result_ngram_size:
            score = 0.0
        else:
            ca, na = self._features(a)
            cb, nb = self._features(b)
            if len(ca) > len(cb):
                ca, cb = cb, ca
            intersection = sum(min(count, cb.get(gram, 0))
                               for gram, count in ca.items())
            score = intersection / (na + nb - intersection)
        if self.cache_size > 0:
            self.pairs[key] = score
            if len(self.pairs) > self.cache_size:
                self.pairs.popitem(last=False)
        return score


def find_repetition(calls: list[TraceCall], settings: LoopSettings):
    """Return the earliest fully verified hit and the action-candidate count."""
    compare = ResultSimilarity(settings)
    action_candidates = 0
    for _, grouped in groupby(calls, key=lambda call: call.segment_id):
        segment = list(grouped)
        n = len(segment)
        r = settings.min_repeats
        for start in range(n - r + 1):
            for period in range(1, (n - start) // r + 1):
                pattern = segment[start:start + period]
                if any(call.action_key is None for call in pattern):
                    continue
                if any(segment[start + k].action_key != pattern[k % period].action_key
                       for k in range(period * r)):
                    continue
                action_candidates += 1
                if any(not call.comparable for call in pattern):
                    continue
                # Identical bodies have identical comparisons: retaining one
                # representative per body preserves all-pairs semantics while
                # making long exact-repeat runs linear rather than quadratic.
                groups = [{call.result: call} for call in pattern]
                count = 1
                window_min = 1.0
                while start + (count + 1) * period <= n:
                    round_calls = segment[start + count * period:
                                          start + (count + 1) * period]
                    accepted = True
                    round_min = 1.0
                    for offset, candidate in enumerate(round_calls):
                        if (not candidate.comparable
                                or candidate.action_key != pattern[offset].action_key):
                            accepted = False
                            break
                        for previous in groups[offset].values():
                            score = compare(previous, candidate)
                            if score < settings.threshold:
                                accepted = False
                                break
                            round_min = min(round_min, score)
                        if not accepted:
                            break
                    if not accepted:
                        break
                    for offset, candidate in enumerate(round_calls):
                        groups[offset].setdefault(candidate.result, candidate)
                    count += 1
                    window_min = min(window_min, round_min)
                if count >= r:
                    matched = segment[start:start + count * period]
                    return {
                        "pattern": [call.name for call in pattern],
                        "pattern_length": period,
                        "repeat_count": count,
                        "start_call_index": matched[0].source_index,
                        "end_call_index": matched[-1].source_index,
                        "call_indices": [call.source_index for call in matched],
                        "call_ids": [call.call_id for call in matched],
                        "min_result_similarity": window_min,
                    }, action_candidates
    return None, action_candidates
