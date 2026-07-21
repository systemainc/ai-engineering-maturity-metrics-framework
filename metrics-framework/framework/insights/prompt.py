"""
Builds the single prompt sent to an insight provider.

This is the one place that turns framework/metrics/gap_analysis.py's
structured facts into English. The model never sees anything beyond what's
rendered here — no raw Store access, no other metrics, no other scopes.
That's deliberate: it bounds what the model can possibly get wrong to "how
it phrases these specific numbers," not "what it decides is true."
"""
from __future__ import annotations

from typing import Optional

_DIRECTION_WORD = {"higher": "increase", "lower": "reduce"}


def build_prompt(scope_label: str, gap: dict, suggestion_hint: Optional[str] = None) -> str:
    verb = _DIRECTION_WORD.get(gap["direction"], "change")
    hint_line = f"\nA subject-matter hint for this metric, if useful: {suggestion_hint}" if suggestion_hint else ""
    return (
        f"You are writing a short, concrete note for an engineering leader about "
        f"\"{scope_label}\".\n\n"
        f"Data (already computed — do not recalculate, second-guess, or add to it):\n"
        f"- Dimension: {gap['dimension_name']}, currently Level {gap['current_level']} of 4 overall\n"
        f"- The metric holding it back is {gap['metric']}, currently {gap['value']} "
        f"(Level {gap['metric_level']} on its own scale)\n"
        f"- That metric needs to {verb} to {gap['target']} to reach Level {gap['metric_next_level']}\n"
        f"{hint_line}\n\n"
        f"Write exactly 2 sentences: what to focus on, and why it's the highest-leverage "
        f"move available right now given only the data above. Do not invent numbers, "
        f"causes, or context not given above. Do not mention or imply any individual "
        f"person. Plain text, no markdown, no preamble."
    )
