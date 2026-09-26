"""Upload package preparation and submission workflow.

Handles creating zip packages from draft files and opening Moodle
submission pages for user review and manual upload.
"""

from __future__ import annotations

import os
import webbrowser
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from .config import DRAFTS_DIR, UPLOADS_DIR
from .moodle_client import MoodleClient
from .task_db import TaskDatabase, TaskRecord, TaskStatus

console = Console()


def prepare_upload_package(
    task: TaskRecord,
    additional_files: list[Path] | None = None,
) -> Path | None:
    """Create a zip package of all draft files for an assignment.

    Args:
        task: The task record containing draft paths.
        additional_files: Extra files to include in the package.

    Returns:
        Path to the zip file, or None if no files to package.
    """
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

    files_to_zip: list[Path] = []

    # Collect draft file
    if task.draft_path:
        draft = Path(task.draft_path)
        if draft.exists():
            files_to_zip.append(draft)

    # Collect study notes
    if task.study_notes_path:
        notes = Path(task.study_notes_path)
        if notes.exists():
            files_to_zip.append(notes)

    # Check for a directory of materials
    safe_name = _sanitize_filename(task.assignment_name)
    materials_dir = DRAFTS_DIR / safe_name
    if materials_dir.is_dir():
        for f in materials_dir.iterdir():
            if f.is_file() and f not in files_to_zip:
                files_to_zip.append(f)

    # Add any additional files
    if additional_files:
        for f in additional_files:
            if f.exists() and f not in files_to_zip:
                files_to_zip.append(f)

    if not files_to_zip:
        console.print("[yellow]⚠ No files found to package[/yellow]")
        return None

    # Create zip
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_name = f"{safe_name}_{timestamp}.zip"
    zip_path = UPLOADS_DIR / zip_name

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in files_to_zip:
            arcname = file_path.name
            zf.write(file_path, arcname)

    file_size = zip_path.stat().st_size
    size_str = _format_size(file_size)

    console.print(f"\n[green]✓ Upload package created: {zip_path}[/green]")
    console.print(f"  Files included: {len(files_to_zip)}")
    console.print(f"  Package size: {size_str}")

    # Show contents
    table = Table(title="Package Contents", show_header=True)
    table.add_column("File", style="cyan")
    table.add_column("Size", justify="right")
    for f in files_to_zip:
        table.add_row(f.name, _format_size(f.stat().st_size))
    console.print(table)

    return zip_path


def review_and_approve(
    task: TaskRecord,
    db: TaskDatabase,
    client: MoodleClient | None = None,
) -> bool:
    """Interactive review and approval workflow.

    Presents the draft to the user for review and asks for approval
    before proceeding with submission preparation.

    Args:
        task: The task to review.
        db: The task database.
        client: Optional MoodleClient for generating upload URLs.

    Returns:
        True if the user approved, False otherwise.
    """
    console.print("\n")
    console.print(
        Panel(
            f"[bold]{task.assignment_name}[/bold]\n"
            f"Course: {task.course_name}\n"
            f"Due: {task.due_date or 'No due date'}\n"
            f"Status: {task.status.value}",
            title="📋 Assignment Review",
            border_style="cyan",
        )
    )

    # Show available files
    files_info = []
    if task.study_notes_path and Path(task.study_notes_path).exists():
        files_info.append(("Study Notes", task.study_notes_path))
    if task.draft_path and Path(task.draft_path).exists():
        files_info.append(("Draft", task.draft_path))
    if task.upload_package_path and Path(task.upload_package_path).exists():
        files_info.append(("Upload Package", task.upload_package_path))

    # Check materials directory
    safe_name = _sanitize_filename(task.assignment_name)
    materials_dir = DRAFTS_DIR / safe_name
    if materials_dir.is_dir():
        for f in materials_dir.iterdir():
            if f.is_file():
                files_info.append((f.stem.replace("_", " ").title(), str(f)))

    if files_info:
        table = Table(title="📁 Available Files", show_header=True)
        table.add_column("#", style="bold", width=3)
        table.add_column("Type", style="cyan")
        table.add_column("Path", style="dim")
        for i, (ftype, fpath) in enumerate(files_info, 1):
            table.add_row(str(i), ftype, fpath)
        console.print(table)

    # Preview draft content
    if task.draft_path and Path(task.draft_path).exists():
        draft_content = Path(task.draft_path).read_text(encoding="utf-8")
        preview = draft_content[:500] + (
            "..." if len(draft_content) > 500 else ""
        )
        console.print(
            Panel(preview, title="📝 Draft Preview", border_style="yellow")
        )

    # Ask for user action
    console.print("\n[bold]What would you like to do?[/bold]")
    console.print("  [cyan]1[/cyan] ✅ Approve and prepare for upload")
    console.print("  [cyan]2[/cyan] 📂 Open files for editing")
    console.print("  [cyan]3[/cyan] 🌐 Open Moodle submission page")
    console.print("  [cyan]4[/cyan] 🔄 Regenerate materials")
    console.print("  [cyan]5[/cyan] ❌ Skip for now")

    choice = Prompt.ask(
        "Choose an action", choices=["1", "2", "3", "4", "5"], default="5"
    )

    if choice == "1":
        # Approve
        db.update_task_status(task.id, TaskStatus.APPROVED)
        console.print("[green bold]✓ Assignment approved![/green bold]")

        # Prepare upload package
        zip_path = prepare_upload_package(task)
        if zip_path:
            db.update_task_paths(
                task.id, upload_package_path=str(zip_path)
            )

        # Open Moodle page if client available
        if client:
            if Confirm.ask("Open Moodle submission page?"):
                url = client.get_assignment_upload_url(
                    task.moodle_assignment_id
                )
                webbrowser.open(url)
                console.print(f"[dim]Opened: {url}[/dim]")

        console.print(
            "\n[yellow bold]⚠ Remember:[/yellow bold] Review the draft "
            "and make it your own before submitting!"
        )
        return True

    elif choice == "2":
        # Open files
        for _, fpath in files_info:
            os.startfile(fpath)  # type: ignore[attr-defined]
        console.print("[dim]Files opened in default applications[/dim]")
        return False

    elif choice == "3":
        # Open Moodle
        if client:
            url = client.get_assignment_upload_url(
                task.moodle_assignment_id
            )
            webbrowser.open(url)
            console.print(f"[dim]Opened: {url}[/dim]")
        else:
            console.print(
                "[yellow]⚠ Moodle client not available[/yellow]"
            )
        return False

    elif choice == "4":
        console.print("[dim]Regeneration will be handled by the agent.[/dim]")
        db.update_task_status(task.id, TaskStatus.PENDING)
        return False

    else:
        console.print("[dim]Skipped.[/dim]")
        return False


def batch_review(
    db: TaskDatabase,
    client: MoodleClient | None = None,
) -> None:
    """Review all tasks that are awaiting review.

    Args:
        db: The task database.
        client: Optional MoodleClient.
    """
    tasks = db.get_all_tasks(status=TaskStatus.AWAITING_REVIEW)
    if not tasks:
        tasks = db.get_all_tasks(status=TaskStatus.DRAFT_READY)

    if not tasks:
        console.print("[dim]No tasks awaiting review.[/dim]")
        return

    console.print(
        f"\n[bold cyan]📋 {len(tasks)} assignment(s) ready for review[/bold cyan]\n"
    )

    for task in tasks:
        review_and_approve(task, db, client)
        console.print("─" * 60)


def _sanitize_filename(name: str) -> str:
    """Convert a string to a safe filename."""
    import re

    safe = re.sub(r'[<>:"/\\|?*]', "", name)
    safe = re.sub(r"\s+", "_", safe)
    safe = safe.strip("._")
    return safe[:100] if len(safe) > 100 else safe


def _format_size(size_bytes: int) -> str:
    """Format bytes to human-readable size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024  # type: ignore[assignment]
    return f"{size_bytes:.1f} TB"
