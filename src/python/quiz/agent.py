from __future__ import annotations

import json
import random
import re
import uuid

from .models import Question, Evaluation
from .retriever import Retriever
from .tracker import Tracker

# Sections that exist exclusively in the cmg_guidelines ChromaDB collection.
# When a quiz targets one of these sections, the retriever skips the
# paramedic_notes collection so questions are drawn from CMG content only.
RANDOM_INJECTION_PROBABILITY = 0.25

CMG_ONLY_SECTIONS = frozenset({
    "Cardiac", "Trauma", "Medical", "Respiratory", "Airway Management",
    "Obstetric", "Neurology", "Behavioural", "Toxicology",
    "Environmental", "Pain Management", "Palliative Care", "HAZMAT",
    "General Care", "Medicine", "Clinical Skill",
})


def build_generation_prompt(skill_level: str = "AP") -> str:
    base = """You are a clinical quiz generator for ACT Ambulance Service paramedics.
Generate one question from the provided source material.

Rules:
- The question must be answerable from the source text alone
- Never fabricate clinical information
- Vary question types: recall, definition, scenario, drug_dose
- Use Australian English (adrenaline, haemorrhage, colour)
- Tone: direct, clinical
- Do NOT repeat or closely rephrase any previously asked questions listed below"""

    if skill_level == "AP":
        base += """
- The user is an Ambulance Paramedic (AP). Do NOT generate questions about Intensive Care Paramedic (ICP) interventions, medications, or procedures. If source material contains ICP-only content, ignore it and only use AP-applicable content."""

    base += """

Each source is labelled [Source 1], [Source 2], etc. You MUST identify which single source the question is drawn from.

Respond with valid JSON only:
{
  "question_text": "...",
  "question_type": "recall|definition|scenario|drug_dose",
  "source_citation": "e.g. ACTAS CMG 14.1",
  "category": "e.g. Cardiac",
  "source_index": 1
}"""
    return base


EVALUATION_SYSTEM_PROMPT = """You are evaluating a paramedic student's answer against clinical source material.

Rules:
- Compare the answer against the source material ONLY — never general knowledge
- Score conservatively: "partial" if anything material is wrong or missing
- Cite the exact source text as source_quote
- Use Australian English
- Tone: supportive expert, straightforward, not chatty

Respond with valid JSON only:
{
  "score": "correct|partial|incorrect",
  "correct_elements": ["..."],
  "missing_or_wrong": ["..."],
  "source_quote": "exact quote from source",
  "feedback_summary": "2-3 sentence clinical feedback"
}"""

DIFFICULTY_INSTRUCTIONS = {
    "easy": "Difficulty adjustment: Ask straightforward recall questions — single-fact definitions, drug names, basic indications. The answer should be 1-2 sentences maximum.",
    "medium": "",
    "hard": "Difficulty adjustment: Ask multi-step scenario questions requiring integration of 2+ clinical concepts. Include patient context (age, vitals, presentation). Expect detailed structured answers covering assessment, treatment rationale, and dose calculations where relevant.",
}


def generate_question(
    mode: str,
    llm,
    retriever: Retriever,
    tracker: Tracker,
    topic: str | None = None,
    guideline_id: str | None = None,
    blacklist: list[str] | None = None,
    difficulty: str = "medium",
    skill_level: str = "AP",
    randomize: bool = True,
    previous_questions: list[str] | None = None,
    used_chunk_contents: list[str] | None = None,
) -> Question:
    query, filters, source_restriction = _resolve_mode(mode, topic, tracker)

    # Restrict to a specific guideline's chunks when requested
    if guideline_id:
        if filters is None:
            filters = {}
        filters["source_file"] = f"{guideline_id}.json"

    # Get recently-used chunks from tracker (persists across sessions/restarts)
    exclude_keys = tracker.get_recent_chunk_keys()

    # Also exclude chunks from the current session
    if used_chunk_contents:
        exclude_keys.update(used_chunk_contents)

    n_to_fetch = 15 if randomize else 5

    # Random injection: only in random mode, 25% of questions pull one corpus-random chunk
    injected_chunk = None
    if mode == "random" and random.random() < RANDOM_INJECTION_PROBABILITY:
        injected_chunk = retriever.get_random_chunk(
            exclude_content_keys=exclude_keys or None,
            skill_level=skill_level,
        )

    if injected_chunk is not None:
        # Pair the injected chunk with 4 semantically-retrieved chunks
        semantic_chunks = retriever.retrieve(
            query=query,
            n=4,
            filters=filters,
            exclude_categories=blacklist,
            skill_level=skill_level,
            exclude_content_keys=exclude_keys or None,
            source_restriction=source_restriction,
            tracker=tracker,
        )
        chunks = [injected_chunk] + semantic_chunks
    else:
        chunks = retriever.retrieve(
            query=query,
            n=n_to_fetch,
            filters=filters,
            exclude_categories=blacklist,
            skill_level=skill_level,
            exclude_content_keys=exclude_keys or None,
            source_restriction=source_restriction,
            tracker=tracker,
        )

        if not chunks:
            # Fallback: try without chunk exclusions to avoid dead end
            chunks = retriever.retrieve(
                query=query,
                n=n_to_fetch,
                filters=filters,
                exclude_categories=blacklist,
                skill_level=skill_level,
                source_restriction=source_restriction,
                tracker=tracker,
            )

        if not chunks:
            raise ValueError("No relevant chunks found for question generation")

        if randomize and len(chunks) > 5:
            chunks = random.sample(chunks, 5)
        else:
            chunks = chunks[:5]

    source_text = "\n\n".join(
        f"[Source {i + 1}: {c.source_type}]\n{c.content}" for i, c in enumerate(chunks)
    )

    user_content = f"Source material:\n\n{source_text}\n\nDifficulty: {difficulty}"

    # Add difficulty-specific instructions if any
    difficulty_instruction = DIFFICULTY_INSTRUCTIONS.get(difficulty, "")
    if difficulty_instruction:
        user_content += f"\n\n{difficulty_instruction}"

    if previous_questions:
        avoid_block = "\n".join(f"- {q}" for q in previous_questions)
        user_content += (
            f"\n\nPreviously asked questions (do NOT repeat these):\n{avoid_block}"
        )

    messages = [
        {"role": "system", "content": build_generation_prompt(skill_level)},
        {"role": "user", "content": user_content},
    ]

    response_text = llm.complete(messages)
    parsed = _parse_json(response_text)

    if not parsed:
        raise ValueError(
            f"Failed to parse LLM response for question: {response_text[:200]}"
        )

    raw_index = parsed.get("source_index", 1)
    primary_chunk_index = max(0, min(raw_index - 1, len(chunks) - 1)) if chunks else 0

    return Question(
        id=str(uuid.uuid4()),
        question_text=parsed.get("question_text", "Error generating question text"),
        question_type=parsed.get("question_type", "recall"),
        source_chunks=chunks,
        source_citation=parsed.get(
            "source_citation", chunks[primary_chunk_index].source_file
        ),
        difficulty=difficulty,
        category=parsed.get(
            "category", chunks[primary_chunk_index].category or "General"
        ),
        primary_chunk_index=primary_chunk_index,
    )


def evaluate_answer(
    question: Question,
    user_answer: str | None,
    elapsed_seconds: float,
    llm,
) -> Evaluation:
    if user_answer is None:
        idx = question.primary_chunk_index
        source = (
            question.source_chunks[idx]
            if idx < len(question.source_chunks)
            else (question.source_chunks[0] if question.source_chunks else None)
        )
        return Evaluation(
            score=None,
            source_quote=source.content if source else "",
            source_citation=question.source_citation,
            feedback_summary=None,
            response_time_seconds=elapsed_seconds,
        )

    source_text = "\n\n".join(c.content for c in question.source_chunks)

    messages = [
        {"role": "system", "content": EVALUATION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Question: {question.question_text}\n\n"
                f"Source material:\n{source_text}\n\n"
                f"Student answer: {user_answer}"
            ),
        },
    ]

    response_text = llm.complete(messages)
    parsed = _parse_json(response_text)

    return Evaluation(
        score=parsed.get("score", "incorrect"),
        correct_elements=parsed.get("correct_elements", []),
        missing_or_wrong=parsed.get("missing_or_wrong", []),
        source_quote=parsed.get("source_quote", ""),
        source_citation=question.source_citation,
        feedback_summary=parsed.get(
            "feedback_summary", "Feedback unavailable due to parsing error."
        ),
        response_time_seconds=elapsed_seconds,
    )


def _parse_json(text: str) -> dict:
    if not text:
        return {}

    # Extract JSON from markdown blocks if present
    match = re.search(r"```(?:json)?\s+(.*?)\s+```", text, re.DOTALL)
    if match:
        text = match.group(1)

    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        # Fallback: try to find anything between curly braces
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except:
                pass
        return {}


def _resolve_mode(
    mode: str, topic: str | None, tracker: Tracker
) -> tuple[str, dict | None, str | None]:
    """Resolve quiz mode into a retrieval query, ChromaDB filters, and source restriction.

    Returns:
        (query, filters, source_restriction)
        source_restriction: None = all sources, "cmg" = CMG collection only.
    """
    if mode == "topic":
        if not topic:
            raise ValueError("Topic mode requires a topic")
        restriction = "cmg" if topic in CMG_ONLY_SECTIONS else None
        return topic, {"section": topic}, restriction
    elif mode == "gap_driven":
        weak = tracker.get_weak_categories(n=1)
        query = weak[0] if weak else random.choice(["Cardiac", "Trauma", "Respiratory"])
        restriction = "cmg" if query in CMG_ONLY_SECTIONS else None
        return query, None, restriction
    elif mode == "random":
        # (query_string, section_or_None) — section drives both the
        # ChromaDB filter and the source-restriction decision.
        _random_options = [
            ("Cardiac", "Cardiac"),
            ("Trauma", "Trauma"),
            ("Respiratory", "Respiratory"),
            ("Paediatrics", "Paediatric"),
            ("Pharmacology", None),
            ("Obstetrics", "Obstetric"),
            ("Mental Health", None),
            ("Infectious Disease", None),
            ("Pathophysiology", None),
            ("Clinical Skills", "Clinical Skill"),
            ("General Paramedicine", None),
            ("Operational Guidelines", None),
            ("Medication Guidelines", "Medicine"),
            ("ECGs", None),
        ]
        query, section = random.choice(_random_options)
        filters: dict | None = {"section": section} if section else None
        restriction = "cmg" if section and section in CMG_ONLY_SECTIONS else None
        return query, filters, restriction
    elif mode == "clinical_guidelines":
        clinical_sections = sorted(
            [
                "Cardiac",
                "Trauma",
                "Medical",
                "Respiratory",
                "Airway Management",
                "Obstetric",
                "Neurology",
                "Behavioural",
                "Toxicology",
                "Environmental",
                "Pain Management",
                "Palliative Care",
                "HAZMAT",
                "General Care",
            ]
        )
        query = random.choice(clinical_sections)
        return query, {"section": query}, "cmg"
    else:
        raise ValueError(f"Unknown mode: {mode}")
