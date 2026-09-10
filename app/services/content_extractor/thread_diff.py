"""Fuzzy prefix alignment retaining original spelling in the new reply."""
from dataclasses import dataclass
from difflib import SequenceMatcher
import re
import unicodedata
from app.core.config import ExtractionSettings


def normalized(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.casefold().replace("đ", "d"))
                   if unicodedata.category(c) != "Mn")


@dataclass(frozen=True)
class ThreadDiffResult:
    new_text: str
    confidence: float
    warnings: tuple[str, ...] = ()


def extract_new_thread_text(previous_text: str, current_text: str,
                            settings: ExtractionSettings | None = None) -> ThreadDiffResult:
    settings = settings or ExtractionSettings()
    tokens = list(re.finditer(r"\S+", current_text))
    previous = re.findall(r"\S+", previous_text)
    if not previous or not tokens:
        return ThreadDiffResult("", 0, ("Previous/current thread body is missing. Review the new reply.",))
    norm = lambda words: " ".join(normalized(w).strip(".,!?;:()\"'") for w in words)
    reference = norm(previous)
    tolerance = max(1, round(len(previous) * settings.diff_length_tolerance))
    lower = max(1, len(previous) - tolerance)
    upper = min(len(tokens), len(previous) + tolerance)
    choices = []
    for count in range(lower, upper + 1):
        prefix = norm([match.group() for match in tokens[:count]])
        score = SequenceMatcher(None, reference, prefix, autojunk=False).ratio()
        choices.append((score, -abs(count - len(previous)), count))
    if not choices:
        return ThreadDiffResult("", 0, ("Thread overlap not found. Review the new reply.",))
    score, _, count = max(choices)
    # Very short context is too ambiguous for approximate matching.
    required = 1.0 if len(previous) < settings.diff_min_context_tokens else settings.thread_diff_similarity_threshold
    if score < required:
        return ThreadDiffResult("", score * .5, ("Thread overlap is uncertain; repeated question was withheld.",))
    new_text = current_text[tokens[count - 1].end():].strip()
    if not new_text:
        return ThreadDiffResult("", .5, ("No new reply detected; previous text will not be repeated.",))
    warnings = () if score >= settings.diff_strong_similarity else ("Thread prefix matched approximately; check the new reply.",)
    return ThreadDiffResult(new_text, score, warnings)
