"""Command-line interface for the Moodle Assignment Agent.

Provides commands for setup, syncing assignments, generating study materials,
managing drafts, and handling the review/approval workflow.
"""

from __future__ import annotations

import argparse
import sys
import time
import webbrowser
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from . import __version__
from .config import DATA_DIR, DRAFTS_DIR, UPLOADS_DIR
from .credentials import (
    clear_credentials,
    get_gemini_key,
    has_credentials,
    interactive_setup,
)
from .moodle_client import MoodleAPIError, MoodleClient
from .notifications import (
    check_and_send_reminders,
    display_task_dashboard,
    display_task_detail,
    send_desktop_notification,
    setup_reminders_for_task,
)
from .study_generator import (
    generate_all_materials,
    generate_explanation,
)
from .task_db import TaskDatabase, TaskStatus
from .upload_manager import batch_review, prepare_upload_package, review_and_approve

import io
import sys

# Force UTF-8 output on Windows to prevent cp1252 encoding errors
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

console = Console()


BANNER = """
 +======================================================+
 |   Moodle Assignment Agent  v{version:<22s} |
 |   -----------------------------------------------    |
 |   Secure - AI-Powered - You Stay in Control          |
 +======================================================+
"""


def main() -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="moodle-agent",
        description="🎓 Moodle Assignment Agent – AI-powered assignment helper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  moodle-agent setup          Configure Moodle credentials securely
  moodle-agent sync           Fetch assignments from Moodle
  moodle-agent list           Show all tracked assignments
  moodle-agent generate 1     Generate study materials for task #1
  moodle-agent generate-all   Generate materials for all pending tasks
  moodle-agent review         Review and approve drafts
  moodle-agent status         Show dashboard overview
  moodle-agent watch          Monitor for new assignments & reminders
  moodle-agent explain "topic"  Get an AI explanation of a topic
        """,
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ── setup ───────────────────────────────────────────────────────────
    subparsers.add_parser("setup", help="Configure Moodle credentials")

    # ── sync ────────────────────────────────────────────────────────────
    sync_parser = subparsers.add_parser(
        "sync", help="Fetch assignments from Moodle"
    )
    sync_parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Days ahead to look for assignments (default: 30)",
    )

    # ── list ────────────────────────────────────────────────────────────
    list_parser = subparsers.add_parser(
        "list", help="List tracked assignments"
    )
    list_parser.add_argument(
        "--status",
        choices=[s.value for s in TaskStatus],
        help="Filter by status",
    )

    # ── status ──────────────────────────────────────────────────────────
    subparsers.add_parser("status", help="Show dashboard overview")

    # ── detail ──────────────────────────────────────────────────────────
    detail_parser = subparsers.add_parser(
        "detail", help="Show details for a specific task"
    )
    detail_parser.add_argument("task_id", type=int, help="Task ID")

    # ── generate ────────────────────────────────────────────────────────
    gen_parser = subparsers.add_parser(
        "generate", help="Generate study materials for a task"
    )
    gen_parser.add_argument("task_id", type=int, help="Task ID")
    gen_parser.add_argument(
        "--type",
        choices=["all", "notes", "quiz", "draft"],
        default="all",
        help="Type of material to generate (default: all)",
    )

    # ── generate-all ────────────────────────────────────────────────────
    subparsers.add_parser(
        "generate-all", help="Generate materials for all pending tasks"
    )

    # ── review ──────────────────────────────────────────────────────────
    review_parser = subparsers.add_parser(
        "review", help="Review and approve drafts"
    )
    review_parser.add_argument(
        "task_id", type=int, nargs="?", help="Specific task ID to review"
    )

    # ── package ─────────────────────────────────────────────────────────
    pkg_parser = subparsers.add_parser(
        "package", help="Create upload package for a task"
    )
    pkg_parser.add_argument("task_id", type=int, help="Task ID")
    pkg_parser.add_argument(
        "--files",
        nargs="*",
        help="Additional files to include",
    )

    # ── explain ─────────────────────────────────────────────────────────
    explain_parser = subparsers.add_parser(
        "explain", help="Get an AI explanation of a topic"
    )
    explain_parser.add_argument("topic", help="Topic to explain")
    explain_parser.add_argument(
        "--level",
        choices=["brief", "detailed", "eli5"],
        default="detailed",
        help="Detail level (default: detailed)",
    )
    explain_parser.add_argument("--course", default="", help="Course context")

    # ── watch ───────────────────────────────────────────────────────────
    watch_parser = subparsers.add_parser(
        "watch", help="Monitor for assignments & send reminders"
    )
    watch_parser.add_argument(
        "--interval",
        type=int,
        default=3600,
        help="Check interval in seconds (default: 3600)",
    )

    # ── open ────────────────────────────────────────────────────────────
    open_parser = subparsers.add_parser(
        "open", help="Open Moodle submission page for a task"
    )
    open_parser.add_argument("task_id", type=int, help="Task ID")

    # ── clear ───────────────────────────────────────────────────────────
    subparsers.add_parser(
        "clear-credentials",
        help="Remove all stored credentials",
    )

    args = parser.parse_args()

    if not args.command:
        console.print(BANNER.format(version=__version__))
        parser.print_help()
        return

    try:
        _dispatch(args)
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted.[/dim]")
        sys.exit(0)
    except MoodleAPIError as e:
        console.print(f"\n[red bold]Moodle Error:[/red bold] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red bold]Error:[/red bold] {e}")
        if "--debug" in sys.argv:
            import traceback

            traceback.print_exc()
        sys.exit(1)


def _dispatch(args: argparse.Namespace) -> None:
    """Dispatch to the appropriate command handler."""
    handlers = {
        "setup": _cmd_setup,
        "sync": _cmd_sync,
        "list": _cmd_list,
        "status": _cmd_status,
        "detail": _cmd_detail,
        "generate": _cmd_generate,
        "generate-all": _cmd_generate_all,
        "review": _cmd_review,
        "package": _cmd_package,
        "explain": _cmd_explain,
        "watch": _cmd_watch,
        "open": _cmd_open,
        "clear-credentials": _cmd_clear_credentials,
    }

    handler = handlers.get(args.command)
    if handler:
        handler(args)
    else:
        console.print(f"[red]Unknown command: {args.command}[/red]")


# ── Command Handlers ────────────────────────────────────────────────────


def _cmd_setup(args: argparse.Namespace) -> None:
    """Configure credentials."""
    console.print(BANNER.format(version=__version__))
    interactive_setup()

    # Test connection
    if Confirm.ask("\nTest Moodle connection?", default=True):
        try:
            client = MoodleClient()
            client.authenticate()
            info = client.get_site_info()
            console.print(
                f"[green]✓ Connected as: {info.get('fullname', 'Unknown')}[/green]"
            )
            console.print(
                f"[dim]  Site: {info.get('sitename', 'Unknown')}[/dim]"
            )
        except MoodleAPIError as e:
            console.print(f"[red]✗ Connection failed: {e}[/red]")
            console.print(
                "[yellow]Check your credentials and Moodle URL.[/yellow]"
            )


def _cmd_sync(args: argparse.Namespace) -> None:
    """Sync assignments from Moodle."""
    _require_credentials()
    db = TaskDatabase()
    client = MoodleClient()

    console.print("[bold]Syncing assignments from Moodle...[/bold]\n")

    # Authenticate
    client.authenticate()

    # Get courses
    courses = client.get_enrolled_courses()
    console.print(f"Found [cyan]{len(courses)}[/cyan] enrolled courses")

    # Get assignments
    assignments = client.get_upcoming_assignments(days_ahead=args.days)
    console.print(
        f"Found [cyan]{len(assignments)}[/cyan] upcoming assignments "
        f"(next {args.days} days)\n"
    )

    new_count = 0
    for a in assignments:
        task_id = db.upsert_task(
            moodle_assignment_id=a.id,
            course_name=a.course_name,
            assignment_name=a.name,
            description=a.description,
            due_date=a.due_date,
        )
        task = db.get_task(task_id)
        if task and task.status == TaskStatus.PENDING:
            setup_reminders_for_task(task, db)
            new_count += 1

    console.print(
        f"\n[green]✓ Synced {len(assignments)} assignments "
        f"({new_count} new)[/green]"
    )

    # Show dashboard
    display_task_dashboard(db)


def _cmd_list(args: argparse.Namespace) -> None:
    """List tracked assignments."""
    db = TaskDatabase()
    status_filter = TaskStatus(args.status) if args.status else None
    tasks = db.get_all_tasks(status=status_filter)

    if not tasks:
        console.print("[dim]No assignments found.[/dim]")
        return

    display_task_dashboard(db)


def _cmd_status(args: argparse.Namespace) -> None:
    """Show dashboard overview."""
    db = TaskDatabase()

    console.print(BANNER.format(version=__version__))

    # Check and send any pending reminders
    sent = check_and_send_reminders(db)
    if sent:
        console.print(f"[yellow]Sent {sent} reminder(s)[/yellow]\n")

    display_task_dashboard(db)


def _cmd_detail(args: argparse.Namespace) -> None:
    """Show task details."""
    db = TaskDatabase()
    task = db.get_task(args.task_id)
    if not task:
        console.print(f"[red]Task #{args.task_id} not found[/red]")
        return
    display_task_detail(task)

    # Show activity log
    log = db.get_activity_log(args.task_id, limit=10)
    if log:
        table = Table(title="Recent Activity", show_header=True)
        table.add_column("Time", style="dim", width=20)
        table.add_column("Action", style="cyan")
        table.add_column("Details")
        for entry in log:
            table.add_row(
                entry["timestamp"][:19], entry["action"], entry["details"]
            )
        console.print(table)


def _cmd_generate(args: argparse.Namespace) -> None:
    """Generate study materials for a task."""
    _require_gemini_key()
    db = TaskDatabase()
    task = db.get_task(args.task_id)
    if not task:
        console.print(f"[red]Task #{args.task_id} not found[/red]")
        return

    console.print(
        Panel(
            f"Generating materials for: [bold]{task.assignment_name}[/bold]",
            border_style="cyan",
        )
    )

    from .study_generator import (
        generate_assignment_draft,
        generate_practice_quiz,
        generate_study_notes,
    )

    safe_name = _sanitize_filename(task.assignment_name)
    output_dir = DRAFTS_DIR / safe_name
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.type in ("all", "notes"):
        try:
            notes_path = generate_study_notes(
                task.assignment_name,
                task.course_name,
                task.description,
                output_dir,
            )
            db.update_task_paths(task.id, study_notes_path=str(notes_path))
            db.update_task_status(task.id, TaskStatus.STUDY_NOTES_READY)
        except Exception as e:
            console.print(f"[red]Study notes failed: {e}[/red]")

    if args.type in ("all", "quiz"):
        try:
            generate_practice_quiz(
                task.assignment_name,
                task.course_name,
                task.description,
                output_dir=output_dir,
            )
        except Exception as e:
            console.print(f"[red]Quiz failed: {e}[/red]")

    if args.type in ("all", "draft"):
        try:
            draft_path = generate_assignment_draft(
                task.assignment_name,
                task.course_name,
                task.description,
                output_dir,
            )
            db.update_task_paths(task.id, draft_path=str(draft_path))
            db.update_task_status(task.id, TaskStatus.DRAFT_READY)
        except Exception as e:
            console.print(f"[red]Draft failed: {e}[/red]")

    db.log_activity(task.id, "generate", f"Generated {args.type} materials")
    db.update_task_status(task.id, TaskStatus.AWAITING_REVIEW)

    console.print(
        f"\n[green bold]✓ Materials ready![/green bold] "
        f"Run [cyan]moodle-agent review {task.id}[/cyan] to review."
    )

    # Notify
    send_desktop_notification(
        "📚 Study Materials Ready",
        f"{task.assignment_name} materials generated. Review when ready!",
    )


def _cmd_generate_all(args: argparse.Namespace) -> None:
    """Generate materials for all pending tasks."""
    _require_gemini_key()
    db = TaskDatabase()
    tasks = db.get_pending_tasks()

    if not tasks:
        console.print("[dim]No pending tasks.[/dim]")
        return

    console.print(
        f"[bold]Generating materials for {len(tasks)} task(s)...[/bold]\n"
    )

    for task in tasks:
        if task.status in (
            TaskStatus.DRAFT_READY,
            TaskStatus.AWAITING_REVIEW,
            TaskStatus.APPROVED,
        ):
            console.print(
                f"[dim]Skipping {task.assignment_name} "
                f"(status: {task.status.value})[/dim]"
            )
            continue

        try:
            results = generate_all_materials(
                task.assignment_name,
                task.course_name,
                task.description,
            )

            if "study_notes" in results:
                db.update_task_paths(
                    task.id, study_notes_path=str(results["study_notes"])
                )
            if "draft" in results:
                db.update_task_paths(
                    task.id, draft_path=str(results["draft"])
                )

            db.update_task_status(task.id, TaskStatus.AWAITING_REVIEW)
            db.log_activity(task.id, "generate_all", "All materials generated")

        except Exception as e:
            console.print(
                f"[red]Failed for {task.assignment_name}: {e}[/red]"
            )

        console.print()

    send_desktop_notification(
        "📚 All Materials Ready",
        f"Study materials generated for {len(tasks)} assignment(s).",
    )
    console.print(
        "\n[green bold]✓ Done![/green bold] "
        "Run [cyan]moodle-agent review[/cyan] to review all drafts."
    )


def _cmd_review(args: argparse.Namespace) -> None:
    """Review and approve drafts."""
    db = TaskDatabase()
    client = None
    try:
        if has_credentials():
            client = MoodleClient()
            client.authenticate()
    except MoodleAPIError:
        console.print(
            "[yellow]⚠ Could not connect to Moodle. "
            "Review will proceed offline.[/yellow]"
        )

    if args.task_id:
        task = db.get_task(args.task_id)
        if not task:
            console.print(f"[red]Task #{args.task_id} not found[/red]")
            return
        review_and_approve(task, db, client)
    else:
        batch_review(db, client)


def _cmd_package(args: argparse.Namespace) -> None:
    """Create upload package."""
    db = TaskDatabase()
    task = db.get_task(args.task_id)
    if not task:
        console.print(f"[red]Task #{args.task_id} not found[/red]")
        return

    additional = [Path(f) for f in args.files] if args.files else None
    zip_path = prepare_upload_package(task, additional)

    if zip_path:
        db.update_task_paths(task.id, upload_package_path=str(zip_path))
        db.log_activity(task.id, "package", f"Created {zip_path.name}")


def _cmd_explain(args: argparse.Namespace) -> None:
    """Get an AI explanation."""
    _require_gemini_key()
    explanation = generate_explanation(
        args.topic, args.course, args.level
    )
    console.print(
        Panel(explanation, title=f"📖 {args.topic}", border_style="green")
    )


def _cmd_watch(args: argparse.Namespace) -> None:
    """Watch mode: periodically sync and check reminders."""
    _require_credentials()
    db = TaskDatabase()
    interval = args.interval

    console.print(
        Panel(
            f"[bold]Watch mode active[/bold]\n"
            f"Checking every {interval}s for new assignments and reminders.\n"
            f"Press Ctrl+C to stop.",
            title="👁️ Watch Mode",
            border_style="green",
        )
    )

    cycle = 0
    while True:
        try:
            cycle += 1
            console.print(
                f"\n[dim]── Cycle {cycle} ──[/dim]"
            )

            # Check reminders
            sent = check_and_send_reminders(db)
            if sent:
                console.print(f"[yellow]Sent {sent} reminder(s)[/yellow]")

            # Sync with Moodle (every 4 cycles to avoid rate limiting)
            if cycle % 4 == 1:
                try:
                    client = MoodleClient()
                    client.authenticate()
                    assignments = client.get_upcoming_assignments()
                    for a in assignments:
                        task_id = db.upsert_task(
                            moodle_assignment_id=a.id,
                            course_name=a.course_name,
                            assignment_name=a.name,
                            description=a.description,
                            due_date=a.due_date,
                        )
                        task = db.get_task(task_id)
                        if task and task.status == TaskStatus.PENDING:
                            setup_reminders_for_task(task, db)

                    console.print(
                        f"[dim]Synced {len(assignments)} assignments[/dim]"
                    )
                except MoodleAPIError as e:
                    console.print(
                        f"[yellow]Sync failed: {e}[/yellow]"
                    )

            # Update overdue status
            for task in db.get_all_tasks():
                if (
                    task.days_remaining is not None
                    and task.days_remaining < 0
                    and task.status
                    not in (TaskStatus.SUBMITTED, TaskStatus.APPROVED)
                ):
                    db.update_task_status(task.id, TaskStatus.OVERDUE)

            time.sleep(interval)

        except KeyboardInterrupt:
            console.print("\n[dim]Watch mode stopped.[/dim]")
            break


def _cmd_open(args: argparse.Namespace) -> None:
    """Open Moodle submission page."""
    _require_credentials()
    db = TaskDatabase()
    task = db.get_task(args.task_id)
    if not task:
        console.print(f"[red]Task #{args.task_id} not found[/red]")
        return

    client = MoodleClient()
    url = client.get_assignment_upload_url(task.moodle_assignment_id)
    webbrowser.open(url)
    console.print(f"[green]Opened: {url}[/green]")


def _cmd_clear_credentials(args: argparse.Namespace) -> None:
    """Clear stored credentials."""
    if Confirm.ask(
        "Are you sure you want to remove all stored credentials?",
        default=False,
    ):
        clear_credentials()


# ── Helpers ─────────────────────────────────────────────────────────────


def _require_credentials() -> None:
    """Ensure credentials are configured."""
    if not has_credentials():
        console.print(
            "[red]Credentials not configured. "
            "Run: moodle-agent setup[/red]"
        )
        sys.exit(1)


def _require_gemini_key() -> None:
    """Ensure Gemini API key is configured."""
    if not get_gemini_key():
        console.print(
            "[red]Gemini API key not configured. "
            "Run: moodle-agent setup[/red]"
        )
        sys.exit(1)


def _sanitize_filename(name: str) -> str:
    """Convert a string to a safe filename."""
    import re

    safe = re.sub(r'[<>:"/\\|?*]', "", name)
    safe = re.sub(r"\s+", "_", safe)
    safe = safe.strip("._")
    return safe[:100] if len(safe) > 100 else safe


if __name__ == "__main__":
    main()
