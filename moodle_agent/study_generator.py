"""AI-powered study material generator using Google Gemini.

Generates study notes, explanations, practice quizzes, and draft answers
for Moodle assignments.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .config import DRAFTS_DIR, GEMINI_MODEL, STUDENT_HEADER, STUDENT_NAME, STUDENT_PRN, STUDENT_BATCH
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


import re
from PIL import Image, ImageDraw, ImageFont

def _create_terminal_screenshot(text: str, filepath: Path) -> None:
    try:
        font = ImageFont.truetype("consola.ttf", 18)
    except IOError:
        font = ImageFont.load_default()
    
    lines = text.split('\n')
    dummy_img = Image.new('RGB', (1, 1))
    draw = ImageDraw.Draw(dummy_img)
    
    max_width = 0
    total_height = 0
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        max_width = max(max_width, bbox[2] - bbox[0])
        total_height += (bbox[3] - bbox[1]) + 6
        
    width = max(600, max_width + 40)
    height = max(300, total_height + 70)
    
    img = Image.new('RGB', (width, height), color=(12, 12, 12))
    draw = ImageDraw.Draw(img)
    
    # Draw terminal top bar
    draw.rectangle([0, 0, width, 35], fill=(35, 35, 35))
    draw.ellipse([12, 10, 27, 25], fill=(255, 95, 86))
    draw.ellipse([37, 10, 52, 25], fill=(255, 189, 46))
    draw.ellipse([62, 10, 77, 25], fill=(39, 201, 63))
    draw.text((width // 2 - 40, 8), "cmd.exe", font=font, fill=(180, 180, 180))
    
    y_text = 45
    for line in lines:
        draw.text((20, y_text), line, font=font, fill=(204, 204, 204))
        bbox = draw.textbbox((0, 0), line, font=font)
        y_text += (bbox[3] - bbox[1]) + 6

    img.save(filepath)

def generate_assignment_draft(
    assignment_name: str,
    course_name: str,
    description: str,
    output_dir: Path | None = None,
) -> Path:
    """Generate a draft response/answer for an assignment."""
    from google.genai import types
    client = _get_client()
    output_dir = output_dir or DRAFTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    prompt = f"""You are an expert academic assistant writing a university assignment submission.
Create a COMPLETE, submission-ready assignment response for the following:

**Course:** {course_name}
**Assignment:** {assignment_name}
**Description/Instructions:**
{description}

CRITICAL INSTRUCTIONS:
1. DO NOT output any student details (Name, PRN, Batch, Course) at the top.
2. DO NOT include any conversational filler. Output ONLY the markdown content.
3. If code is required, enclose it in proper markdown fenced code blocks (e.g., ```python ... ```).
4. **IF the assignment requires Python code**: You MUST use your Code Execution tool to physically run the code you wrote. Take the EXACT real output from your execution and place it in the Output section.
5. **OUTPUT SCREENSHOTS**: To simulate a real student attaching a screenshot of their code output, you MUST wrap the exact real output inside a specialized markdown block exactly like this:
```terminal_output
<exact real output from the code>
```
The system will automatically intercept `terminal_output` blocks and convert them into realistic command-line screenshots in the final PDF!
6. For practical/lab assignments, use this exact structure:
   - **Aim/Objective**
   - **Theory/Background**
   - **Implementation Code** (in fenced code blocks)
   - **Output** (MUST use the ```terminal_output block)
   - **Conclusion**
7. Ensure the response is highly professional and accurate."""

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Generating assignment draft (with Code Execution)...", total=None)

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(code_execution=types.ToolCodeExecution)]
            )
        )

    # Process terminal outputs into images
    # Avoid response.text UserWarning when tools are used by extracting text parts manually
    parts = response.candidates[0].content.parts
    final_text = "".join([p.text for p in parts if p.text])
    
    safe_name = _sanitize_filename(assignment_name)
    
    # Find all terminal_output blocks
    pattern = re.compile(r'```terminal_output\n(.*?)\n```', re.DOTALL)
    matches = pattern.findall(final_text)
    
    for i, output_text in enumerate(matches):
        img_filename = f"{safe_name}_output_{i}.png"
        img_filepath = output_dir / img_filename
        _create_terminal_screenshot(output_text.strip(), img_filepath)
        # Replace the block with an image tag pointing to the absolute path for xhtml2pdf
        img_tag = f"\n<br>\n<img src='{img_filepath.as_posix()}' width='600' />\n<br>\n"
        final_text = final_text.replace(f"```terminal_output\n{output_text}\n```", img_tag)

    # Prepend student header to the response
    header = (
        f"# {assignment_name}\n\n"
        f"**Name:** {STUDENT_NAME}  \n"
        f"**PRN:** {STUDENT_PRN}  \n"
        f"**Batch:** {STUDENT_BATCH}  \n"
        f"**Course:** {course_name}  \n\n"
        f"---\n\n"
    )

    filepath = output_dir / f"{safe_name}_draft.md"
    filepath.write_text(header + final_text, encoding="utf-8")

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
