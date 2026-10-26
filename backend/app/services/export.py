"""Decision brief export.

Markdown is the source of truth: the PDF is rendered from the same structure,
so the two cannot drift. Neither invents content — a field the board left
empty is omitted rather than filled with a placeholder.
"""

from __future__ import annotations

import re
import unicodedata

from app.agents.registry import REGISTRY, AgentId
from app.models.decision import StrategicDecision


def _name(agent_id: str) -> str:
    try:
        definition = REGISTRY[AgentId(agent_id)]
        return f"{definition.display_name} ({definition.short_title})"
    except (ValueError, KeyError):
        return agent_id


def _plan_section(title: str, items: list[dict] | None) -> list[str]:
    if not items:
        return []
    lines = [f"### {title}", ""]
    for item in items:
        meta = " · ".join(
            str(v)
            for v in (item.get("priority"), item.get("suggested_owner"))
            if v
        )
        lines.append(f"- {item.get('description')}" + (f" _({meta})_" if meta else ""))
    lines.append("")
    return lines


def to_markdown(decision: StrategicDecision, *, question: str | None = None) -> str:
    """Render a decision brief as Markdown."""
    lines: list[str] = [f"# {decision.title}", ""]

    status = decision.status.value
    lines.append(f"**Status:** {status}")
    if question:
        lines.append(f"**Question put to the board:** {question}")
    lines.append(f"**Generated:** {decision.created_at:%Y-%m-%d %H:%M} UTC")
    lines.append("")

    lines += ["## Executive summary", "", decision.executive_summary, ""]
    lines += ["## Problem", "", decision.problem_statement, ""]

    if decision.strategic_options:
        lines += ["## Options considered", ""]
        for option in decision.strategic_options:
            marker = (
                " — **recommended**"
                if option.get("option_id") == decision.recommended_option_id
                else ""
            )
            lines.append(f"### {option.get('title')}{marker}")
            lines.append("")
            lines.append(str(option.get("description", "")))
            lines.append("")
            for label, key in (("Benefits", "benefits"), ("Risks", "risks"), ("Costs", "costs")):
                values = option.get(key) or []
                if values:
                    lines.append(f"**{label}:**")
                    lines += [f"- {v}" for v in values]
                    lines.append("")
            if option.get("evaluation"):
                lines += [f"_{option['evaluation']}_", ""]

    if decision.recommendation_rationale:
        lines += ["## Why this option", "", decision.recommendation_rationale, ""]

    for label, value in (
        ("Financial implications", decision.financial_implications),
        ("Operational implications", decision.operational_implications),
        ("Customer implications", decision.customer_implications),
        ("Competitive implications", decision.competitive_implications),
        ("Legal considerations", decision.legal_considerations),
    ):
        if value:
            lines += [f"## {label}", "", value, ""]

    if decision.dissenting_opinions:
        lines += [
            "## Dissent",
            "",
            "_Positions that did not survive into the recommendation, kept on the record._",
            "",
        ]
        for d in decision.dissenting_opinions:
            lines.append(f"**{_name(str(d.get('agent_id')))}**")
            lines.append("")
            lines.append(str(d.get("position", "")))
            if d.get("reasoning"):
                lines += ["", f"_{d['reasoning']}_"]
            lines.append("")

    if decision.unresolved_questions:
        lines += ["## Still unresolved", ""]
        for q in decision.unresolved_questions:
            lines.append(f"- **{q.get('question')}** — {q.get('why_it_matters', '')}")
        lines.append("")

    if decision.confidence_and_uncertainty:
        lines += ["## Confidence", "", decision.confidence_and_uncertainty, ""]

    plan = decision.action_plan or {}
    plan_lines = (
        _plan_section("First 30 days", plan.get("first_30_days"))
        + _plan_section("Days 30-60", plan.get("days_30_to_60"))
        + _plan_section("Days 60-90", plan.get("days_60_to_90"))
    )
    if plan_lines:
        lines += ["## Action plan", ""] + plan_lines

    if decision.positions:
        lines += ["## Where each executive stood", ""]
        for position in decision.positions:
            flag = " _(dissent)_" if position.is_dissent else ""
            lines.append(f"- **{_name(position.agent_id)}**{flag}: {position.position_summary}")
        lines.append("")

    if decision.decision_notes:
        lines += ["## Your note", "", decision.decision_notes, ""]

    lines += [
        "---",
        "",
        (
            "_Produced by Ghost Board. The board advises; the decision is the "
            "founder's. Legal commentary is not legal advice and creates no "
            "attorney-client relationship._"
        ),
    ]
    return "\n".join(lines)


_MD_MARKUP = re.compile(r"(\*\*|__|_|`)")

# Characters the board's prose produces that even cp1252 cannot hold. Each
# maps to the nearest thing a reader would accept, rather than to "?".
_PDF_TRANSLATION = str.maketrans(
    {
        "−": "-",  # minus sign
        "→": "->",
        "←": "<-",
        "⇒": "=>",
        "≤": "<=",
        "≥": ">=",
        "≈": "~",
        "≠": "!=",
        " ": " ",  # non-breaking space: encodable, but blocks wrapping
        "‑": "-",  # non-breaking hyphen
        " ": " ",
        " ": " ",
    }
)


def _encodable(text: str) -> bool:
    try:
        text.encode("cp1252")
    except UnicodeEncodeError:
        return False
    return True


def _pdf_safe(text: str) -> str:
    """What the built-in fonts can actually print.

    The core fonts are declared WinAnsiEncoding, so their real repertoire is
    cp1252, not latin-1: em dashes, curly quotes, bullets, ellipses and the
    euro sign all render. Encoding to latin-1 first, as this used to, threw
    away characters the PDF could have shown and turned most of the board's
    punctuation into question marks.

    What cp1252 genuinely cannot hold is substituted, then accent-folded one
    character at a time -- so an unencodable U+0101 becomes "a" while an
    encodable U+00E9 is left alone -- and only then given up on.
    """
    out: list[str] = []
    for char in text.translate(_PDF_TRANSLATION):
        if _encodable(char):
            out.append(char)
            continue
        folded = "".join(
            c for c in unicodedata.normalize("NFKD", char) if not unicodedata.combining(c)
        )
        out.append(folded if folded and _encodable(folded) else "?")
    return "".join(out)


def _strip_markdown(text: str) -> str:
    """fpdf has no Markdown renderer; drop the markers rather than print them."""
    return _MD_MARKUP.sub("", text)


def to_pdf(decision: StrategicDecision, *, question: str | None = None) -> bytes:
    """Render the same brief as a PDF.

    Built from the Markdown so the two exports cannot describe the decision
    differently. Core fonts only: bundling a Unicode TTF would be the right
    answer for scripts outside cp1252 (CJK, Cyrillic, Greek), but it is a
    binary dependency this project does not otherwise need. Everything the
    board writes in English survives intact; see `_pdf_safe`.
    """
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    pdf = FPDF(format="A4")
    # fpdf defaults to latin-1, which is narrower than what the core fonts
    # actually support: fpdf declares them WinAnsiEncoding, which is cp1252.
    pdf.core_fonts_encoding = "cp1252"
    # Margins before the first page: set afterwards, fpdf has already fixed
    # the content width and multi_cell(0, ...) ends up with none.
    pdf.set_margins(18, 18, 18)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    for raw in to_markdown(decision, question=question).split("\n"):
        line = _pdf_safe(_strip_markdown(raw).rstrip())

        if line.startswith("# "):
            pdf.set_font("Helvetica", "B", 18)
            pdf.multi_cell(0, 9, line[2:], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(2)
        elif line.startswith("## "):
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 13)
            pdf.multi_cell(0, 7, line[3:], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(1)
        elif line.startswith("### "):
            pdf.set_font("Helvetica", "B", 11)
            pdf.multi_cell(0, 6, line[4:], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        elif line.startswith("---"):
            pdf.ln(3)
        elif line.startswith("- "):
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 5.5, f"  \u2022 {line[2:]}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        elif not line:
            pdf.ln(2.5)
        else:
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 5.5, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # fpdf2 returns a bytearray; callers want immutable bytes.
    return bytes(pdf.output())


def filename_for(decision: StrategicDecision, extension: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", decision.title.lower()).strip("-")[:60] or "decision"
    return f"{slug}.{extension}"


__all__ = ["filename_for", "to_markdown", "to_pdf"]
