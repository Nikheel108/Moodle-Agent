"""Desktop and console notification system for assignment reminders."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .task_db import ReminderType, TaskDatabase, TaskRecord, TaskStatus

console = Console()


def send_desktop_notification(title: str, message: str) -> None:
    """Send a desktop notification using plyer.

    Falls back to console output if plyer is not available or fails.

    Args:
        title: Notification title.
        message: Notification body text.
    """
    try:
        import platform
        import os
        
        if os.environ.get("DISABLE_NOTIFICATIONS") == "1":
            return

        if platform.system() == "Windows":
            # plyer's balloontip runs on a background thread and frequently crashes with 
            # Shell_NotifyIconW when the main thread exits too quickly. 
            # Using a lightweight powershell toast is much more robust for Windows 10/11.
            import subprocess
            
            # Escape single quotes for powershell string
            safe_title = title.replace("'", "''")
            safe_msg = message[:200].replace("'", "''")
            
            ps_script = f"""
            [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
            [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
            $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
            $template = "<toast><visual><binding template='ToastText02'><text id='1'>{safe_title}</text><text id='2'>{safe_msg}</text></binding></visual></toast>"
            $xml.LoadXml($template)
            $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
            [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Moodle Agent").Show($toast)
            """
            # CREATE_NO_WINDOW = 0x08000000
            subprocess.Popen(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                creationflags=0x08000000
            )
            return
            
        # Fallback to plyer for Mac/Linux
        from plyer import notification
        notification.notify(
            title=title,
            message=message[:256],
            app_name="Moodle Agent",
            timeout=5,
        )
    except Exception:
        # Fallback: just print to console
        console.print(
            Panel(
                f"[bold]{title}[/bold]\n{message}",
                border_style="yellow",
                title="🔔 Notification",
            )
        )


def setup_reminders_for_task(
    task: TaskRecord, db: TaskDatabase
) -> None:
    """Create automatic reminders for a task based on its due date.

    Schedules reminders at:
    - 7 days before due
    - 3 days before due
    - 1 day before due
    - 6 hours before due
    - At due time (overdue warning)

    Args:
        task: The task to create reminders for.
        db: The task database.
    """
    if not task.due_date:
        return

    due_dt = task.due_datetime
    if due_dt is None:
        return

    now = datetime.now(timezone.utc)

    reminder_schedule = [
        (timedelta(days=7), ReminderType.STUDY_REMINDER, "7 days until due"),
        (timedelta(days=3), ReminderType.DUE_SOON, "3 days until due"),
        (timedelta(days=1), ReminderType.DUE_SOON, "Due tomorrow!"),
        (timedelta(hours=6), ReminderType.DUE_SOON, "Due in 6 hours!"),
        (timedelta(0), ReminderType.OVERDUE, "Assignment is now DUE!"),
    ]

    for delta, rtype, label in reminder_schedule:
        remind_at = due_dt - delta
        if remind_at > now:
            message = (
                f"📚 {task.assignment_name}\n"
                f"Course: {task.course_name}\n"
                f"⏰ {label}"
            )
            db.add_reminder(task.id, rtype, remind_at, message)

    console.print(
        f"[dim]  Set reminders for: {task.assignment_name}[/dim]"
    )


def check_and_send_reminders(db: TaskDatabase) -> int:
    """Check for due reminders and send notifications.

    Args:
        db: The task database.

    Returns:
        Number of reminders sent.
    """
    due_reminders = db.get_due_reminders()
    sent_count = 0

    for reminder in due_reminders:
        title = f"📚 {reminder['assignment_name']}"
        message = reminder["message"]

        send_desktop_notification(title, message)
        db.mark_reminder_sent(reminder["id"])
        sent_count += 1

    return sent_count


def display_task_dashboard(db: TaskDatabase) -> None:
    """Display a rich dashboard of all tracked assignments.

    Args:
        db: The task database.
    """
    tasks = db.get_all_tasks()
    stats = db.get_stats()

    if not tasks:
        console.print(
            Panel(
                "[dim]No assignments tracked yet.\n"
                "Run [bold]moodle-agent sync[/bold] to fetch from Moodle.[/dim]",
                title="📊 Dashboard",
                border_style="blue",
            )
        )
        return

    # Status summary
    status_parts = []
    status_emoji = {
        "pending": "⏳",
        "in_progress": "🔨",
        "study_notes_ready": "📝",
        "draft_ready": "📄",
        "awaiting_review": "👀",
        "approved": "✅",
        "submitted": "🎉",
        "overdue": "🚨",
    }
    for status_val, count in stats.items():
        if status_val == "total" or count == 0:
            continue
        emoji = status_emoji.get(status_val, "•")
        status_parts.append(f"{emoji} {status_val}: {count}")

    summary = f"Total: {stats['total']}  │  " + "  │  ".join(status_parts)
    console.print(
        Panel(summary, title="📊 Assignment Dashboard", border_style="blue")
    )

    # Task table
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("ID", width=4, justify="right")
    table.add_column("Course", max_width=20)
    table.add_column("Assignment", max_width=30)
    table.add_column("Due Date", width=18)
    table.add_column("Remaining", width=12, justify="right")
    table.add_column("Status", width=16)
    table.add_column("Files", width=6, justify="center")

    for task in tasks:
        # Format remaining time
        days = task.days_remaining
        if days is None:
            remaining = "[dim]No date[/dim]"
            remaining_style = "dim"
        elif days < 0:
            remaining = f"[red bold]{abs(days):.0f}d overdue[/red bold]"
            remaining_style = "red"
        elif days < 1:
            hours = days * 24
            remaining = f"[red bold]{hours:.0f}h[/red bold]"
            remaining_style = "red"
        elif days < 3:
            remaining = f"[yellow]{days:.1f}d[/yellow]"
            remaining_style = "yellow"
        else:
            remaining = f"[green]{days:.0f}d[/green]"
            remaining_style = "green"

        # Format status
        status_str = f"{status_emoji.get(task.status.value, '•')} {task.status.value}"

        # Count files
        file_count = sum(
            1
            for p in [
                task.study_notes_path,
                task.draft_path,
                task.upload_package_path,
            ]
            if p
        )

        # Format due date
        due_str = ""
        if task.due_date:
            due_dt = task.due_datetime
            if due_dt:
                due_str = due_dt.strftime("%Y-%m-%d %H:%M")

        table.add_row(
            str(task.id),
            task.course_name[:20],
            task.assignment_name[:30],
            due_str,
            remaining,
            status_str,
            str(file_count) if file_count else "—",
        )

    console.print(table)


def display_task_detail(task: TaskRecord) -> None:
    """Display detailed information for a single task.

    Args:
        task: The task to display.
    """
    from pathlib import Path

    detail_lines = [
        f"[bold]Course:[/bold] {task.course_name}",
        f"[bold]Assignment:[/bold] {task.assignment_name}",
        f"[bold]Moodle ID:[/bold] {task.moodle_assignment_id}",
        f"[bold]Status:[/bold] {task.status.value}",
        f"[bold]Due Date:[/bold] {task.due_date or 'Not set'}",
    ]

    if task.days_remaining is not None:
        if task.days_remaining < 0:
            detail_lines.append(
                f"[bold]Remaining:[/bold] [red]{abs(task.days_remaining):.1f} days overdue[/red]"
            )
        else:
            detail_lines.append(
                f"[bold]Remaining:[/bold] {task.days_remaining:.1f} days"
            )

    detail_lines.append("")
    detail_lines.append("[bold]Description:[/bold]")
    desc = task.description[:500] if task.description else "(No description)"
    detail_lines.append(f"[dim]{desc}[/dim]")

    detail_lines.append("")
    detail_lines.append("[bold]Files:[/bold]")
    for label, path_str in [
        ("Study Notes", task.study_notes_path),
        ("Draft", task.draft_path),
        ("Upload Package", task.upload_package_path),
    ]:
        if path_str:
            exists = "✓" if Path(path_str).exists() else "✗ (missing)"
            detail_lines.append(f"  {label}: {path_str} {exists}")
        else:
            detail_lines.append(f"  {label}: [dim]Not generated[/dim]")

    console.print(
        Panel(
            "\n".join(detail_lines),
            title=f"📋 Task #{task.id}",
            border_style="cyan",
        )
    )
