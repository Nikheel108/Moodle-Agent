"""AI-powered study material generator using Google Gemini.

Generates study notes, explanations, practice quizzes, and draft answers
for Moodle assignments.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .config import DRAFTS_DIR, GEMINI_MODEL
from .credentials import get_gemini_key

console = Console()


def _get_client() -> Any:
    """Initialize the Gemini client.

    Returns:
        A configured google.genai.Client instance.

    Raises:
        RuntimeError: If the Gemini API key is not configured.
    """
    api_key = get_gemini_key()
    if not api_key:
        raise RuntimeError(
            "Gemini API key not configured. Run: moodle-agent setup"
        )

    from google import genai

    return genai.Client(api_key=api_key)


def generate_study_notes(
    assignment_name: str,
    course_name: str,
    description: str,
    output_dir: Path | None = None,
) -> Path:
    """Generate comprehensive study notes for an assignment.

    Args:
        assignment_name: The name of the assignment.
        course_name: The name of the course.
        description: The assignment description/instructions.
        output_dir: Directory to save the notes. Defaults to DRAFTS_DIR.

    Returns:
        Path to the generated study notes file.
    """
    client = _get_client()
    output_dir = output_dir or DRAFTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    prompt = f"""You are an expert academic tutor. Create comprehensive study notes for the following assignment.

**Course:** {course_name}
**Assignment:** {assignment_name}
**Description/Instructions:**
{description}

Generate detailed study notes in Markdown format that include:

1. **Topic Overview** – A clear summary of the key concepts involved.
2. **Key Concepts & Definitions** – Important terms and their explanations.
3. **Detailed Explanations** – In-depth coverage of each topic area.
4. **Examples & Illustrations** – Concrete examples to aid understanding.
5. **Common Pitfalls** – Mistakes to avoid.
6. **Summary & Key Takeaways** – Quick revision points.
7. **Recommended Resources** – Suggested reading or reference materials.

Make the notes thorough but well-organized with clear headings and bullet points.
Use Markdown formatting for readability."""

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Generating study notes...", total=None)

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )

    safe_name = _sanitize_filename(assignment_name)
    filepath = output_dir / f"{safe_name}_study_notes.md"
    filepath.write_text(response.text, encoding="utf-8")

    console.print(f"[green]✓ Study notes saved: {filepath}[/green]")
    return filepath


def generate_practice_quiz(
    assignment_name: str,
    course_name: str,
    description: str,
    num_questions: int = 10,
    output_dir: Path | None = None,
) -> Path:
    """Generate a practice quiz with answers.

    Args:
        assignment_name: The name of the assignment.
        course_name: The name of the course.
        description: The assignment description/instructions.
        num_questions: Number of quiz questions to generate.
        output_dir: Directory to save the quiz.

    Returns:
        Path to the generated quiz file.
    """
    client = _get_client()
    output_dir = output_dir or DRAFTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    prompt = f"""You are an expert academic tutor. Create a practice quiz for the following assignment.

**Course:** {course_name}
**Assignment:** {assignment_name}
**Description/Instructions:**
{description}

Generate a practice quiz in Markdown format with exactly {num_questions} questions:

1. Include a mix of question types:
   - Multiple choice (4 options each)
   - Short answer
   - True/False with explanation
   - Application/scenario-based questions

2. For EACH question, provide:
   - The question
   - The correct answer
   - A brief explanation of WHY that answer is correct

3. Format the quiz in two sections:
   **SECTION 1: QUESTIONS** (questions only, for self-testing)
   **SECTION 2: ANSWER KEY** (answers with explanations)

Make questions progressively harder from basic recall to application-level."""

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Generating practice quiz...", total=None)

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )

    safe_name = _sanitize_filename(assignment_name)
    filepath = output_dir / f"{safe_name}_practice_quiz.md"
    filepath.write_text(response.text, encoding="utf-8")

    console.print(f"[green]✓ Practice quiz saved: {filepath}[/green]")
    return filepath


def generate_assignment_draft(
    assignment_name: str,
    course_name: str,
    description: str,
    output_dir: Path | None = None,
) -> Path:
    """Generate a draft response/answer for an assignment.

    This creates a DRAFT that the user must review, edit, and approve
    before submission. It is clearly marked as AI-assisted.

    Args:
        assignment_name: The name of the assignment.
        course_name: The name of the course.
        description: The assignment description/instructions.
        output_dir: Directory to save the draft.

    Returns:
        Path to the generated draft file.
    """
    client = _get_client()
    output_dir = output_dir or DRAFTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    prompt = f"""You are an expert academic assistant. Create a well-structured DRAFT response for the following assignment.

**Course:** {course_name}
**Assignment:** {assignment_name}
**Description/Instructions:**
{description}

Important guidelines:
1. Create a thorough, well-researched draft response.
2. Use proper academic formatting and citations where appropriate.
3. Include clear section headings and logical flow.
4. Mark any areas that need the student's personal input with [YOUR INPUT NEEDED: description].
5. Include placeholder references as [REF: topic] for the student to replace with actual sources.
6. At the top, include a note: "⚠️ DRAFT – This is an AI-assisted draft. Review, personalize, and verify all content before submission."

The draft should demonstrate understanding of the topic while leaving room for the student's own voice and insights."""

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Generating assignment draft...", total=None)

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )

    safe_name = _sanitize_filename(assignment_name)
    filepath = output_dir / f"{safe_name}_draft.md"
    filepath.write_text(response.text, encoding="utf-8")

    console.print(f"[green]✓ Assignment draft saved: {filepath}[/green]")
    return filepath


def generate_explanation(
    topic: str,
    course_name: str = "",
    detail_level: str = "detailed",
) -> str:
    """Generate an explanation for a specific topic.

    Args:
        topic: The topic to explain.
        course_name: Optional course context.
        detail_level: One of "brief", "detailed", "eli5".

    Returns:
        The explanation text.
    """
    client = _get_client()

    level_instructions = {
        "brief": "Give a concise explanation in 2-3 paragraphs.",
        "detailed": "Give a thorough, detailed explanation with examples.",
        "eli5": "Explain this like I'm 5 years old. Use simple analogies.",
    }

    context = f" in the context of {course_name}" if course_name else ""
    prompt = f"""Explain the following topic{context}:

**Topic:** {topic}

{level_instructions.get(detail_level, level_instructions['detailed'])}

Use clear language and concrete examples. Format with Markdown."""

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Generating explanation...", total=None)

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )

    return response.text


def generate_all_materials(
    assignment_name: str,
    course_name: str,
    description: str,
    output_dir: Path | None = None,
) -> dict[str, Path]:
    """Generate all study materials for an assignment.

    Creates study notes, a practice quiz, and an assignment draft.

    Args:
        assignment_name: The name of the assignment.
        course_name: The name of the course.
        description: The assignment description/instructions.
        output_dir: Directory to save all materials.

    Returns:
        Dictionary mapping material type to file path.
    """
    safe_name = _sanitize_filename(assignment_name)
    output_dir = (output_dir or DRAFTS_DIR) / safe_name
    output_dir.mkdir(parents=True, exist_ok=True)

    console.print(
        f"\n[bold cyan]Generating study materials for:[/bold cyan] {assignment_name}"
    )
    console.print(f"[dim]Output directory: {output_dir}[/dim]\n")

    results: dict[str, Path] = {}

    try:
        results["study_notes"] = generate_study_notes(
            assignment_name, course_name, description, output_dir
        )
    except Exception as e:
        console.print(f"[red]✗ Study notes failed: {e}[/red]")

    try:
        results["practice_quiz"] = generate_practice_quiz(
            assignment_name, course_name, description, output_dir=output_dir
        )
    except Exception as e:
        console.print(f"[red]✗ Practice quiz failed: {e}[/red]")

    try:
        results["draft"] = generate_assignment_draft(
            assignment_name, course_name, description, output_dir
        )
    except Exception as e:
        console.print(f"[red]✗ Draft generation failed: {e}[/red]")

    return results


def _sanitize_filename(name: str) -> str:
    """Convert a string to a safe filename."""
    import re

    safe = re.sub(r'[<>:"/\\|?*]', "", name)
    safe = re.sub(r"\s+", "_", safe)
    safe = safe.strip("._")
    return safe[:100] if len(safe) > 100 else safe
