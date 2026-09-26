"""Moodle REST API client for fetching courses, assignments, and deadlines."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import requests
from rich.console import Console

from .credentials import get_credentials, get_token, store_token

console = Console()


@dataclass
class Assignment:
    """Represents a Moodle assignment."""

    id: int
    course_id: int
    course_name: str
    name: str
    description: str
    due_date: datetime | None
    allow_submissions_from: datetime | None
    cut_off_date: datetime | None
    max_attempts: int
    submission_types: list[str] = field(default_factory=list)
    submitted: bool = False
    graded: bool = False

    @property
    def is_overdue(self) -> bool:
        if self.due_date is None:
            return False
        return datetime.now(timezone.utc) > self.due_date

    @property
    def days_remaining(self) -> float | None:
        if self.due_date is None:
            return None
        delta = self.due_date - datetime.now(timezone.utc)
        return delta.total_seconds() / 86400

    @property
    def urgency(self) -> str:
        days = self.days_remaining
        if days is None:
            return "unknown"
        if days < 0:
            return "overdue"
        if days < 1:
            return "critical"
        if days < 3:
            return "urgent"
        if days < 7:
            return "upcoming"
        return "relaxed"


class MoodleAPIError(Exception):
    """Raised when Moodle API returns an error."""

    def __init__(self, message: str, error_code: str | None = None):
        self.error_code = error_code
        super().__init__(message)


class MoodleClient:
    """Client for interacting with Moodle's REST Web Services API."""

    def __init__(self, moodle_url: str | None = None, token: str | None = None):
        self._token = token or get_token()
        creds = get_credentials()
        self._base_url = moodle_url or creds.get("moodle_url", "")
        if not self._base_url:
            raise MoodleAPIError("Moodle URL not configured. Run setup first.")
        self._rest_url = f"{self._base_url}/webservice/rest/server.php"
        self._login_url = f"{self._base_url}/login/token.php"
        self._session = requests.Session()
        self._session.headers.update({"Accept": "application/json"})
        self._user_id: int | None = None

    def authenticate(self) -> str:
        """Authenticate with Moodle and obtain an API token.

        Uses stored credentials to request a token via the mobile app
        service endpoint. The token is then stored securely in the keyring.

        Returns:
            The API token string.

        Raises:
            MoodleAPIError: If authentication fails.
        """
        creds = get_credentials()
        if not creds["username"] or not creds["password"]:
            raise MoodleAPIError("Credentials not configured. Run setup first.")

        console.print("[dim]Authenticating with Moodle...[/dim]")

        try:
            response = self._session.post(
                self._login_url,
                data={
                    "username": creds["username"],
                    "password": creds["password"],
                    "service": "moodle_mobile_app",
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            raise MoodleAPIError(f"Connection failed: {e}") from e

        if "token" not in data:
            error_msg = data.get("error", "Unknown authentication error")
            raise MoodleAPIError(f"Authentication failed: {error_msg}")

        self._token = data["token"]
        store_token(self._token)
        console.print("[green]✓ Authenticated successfully[/green]")
        return self._token

    def _call(self, function: str, **params: Any) -> Any:
        """Make an authenticated call to the Moodle REST API.

        Args:
            function: The Moodle web service function name.
            **params: Additional parameters for the API call.

        Returns:
            The parsed JSON response.

        Raises:
            MoodleAPIError: If the token is missing or the API returns an error.
        """
        if not self._token:
            self.authenticate()

        request_params = {
            "wstoken": self._token,
            "wsfunction": function,
            "moodlewsrestformat": "json",
            **params,
        }

        try:
            response = self._session.post(
                self._rest_url, data=request_params, timeout=30
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            raise MoodleAPIError(f"API call failed: {e}") from e

        if isinstance(data, dict) and "exception" in data:
            raise MoodleAPIError(
                data.get("message", "Unknown API error"),
                data.get("errorcode"),
            )

        return data

    def get_site_info(self) -> dict[str, Any]:
        """Get site info and the current user's ID."""
        data = self._call("core_webservice_get_site_info")
        self._user_id = data.get("userid")
        return data

    def get_user_id(self) -> int:
        """Return the current user's Moodle ID."""
        if self._user_id is None:
            self.get_site_info()
        assert self._user_id is not None
        return self._user_id

    def get_enrolled_courses(self) -> list[dict[str, Any]]:
        """Fetch all courses the user is enrolled in.

        Returns:
            List of course dictionaries with id, fullname, shortname, etc.
        """
        user_id = self.get_user_id()
        return self._call("core_enrol_get_users_courses", userid=user_id)

    def get_assignments(
        self, course_ids: list[int] | None = None
    ) -> list[Assignment]:
        """Fetch assignments from enrolled courses.

        Args:
            course_ids: Optional list of course IDs to filter.
                        If None, fetches from all enrolled courses.

        Returns:
            List of Assignment objects.
        """
        params: dict[str, Any] = {}
        if course_ids:
            for i, cid in enumerate(course_ids):
                params[f"courseids[{i}]"] = cid

        data = self._call("mod_assign_get_assignments", **params)
        assignments: list[Assignment] = []

        for course in data.get("courses", []):
            course_id = course["id"]
            course_name = course.get("fullname", f"Course {course_id}")

            for a in course.get("assignments", []):
                due_ts = a.get("duedate", 0)
                allow_from_ts = a.get("allowsubmissionsfromdate", 0)
                cutoff_ts = a.get("cutoffdate", 0)

                assignment = Assignment(
                    id=a["id"],
                    course_id=course_id,
                    course_name=course_name,
                    name=a.get("name", "Untitled"),
                    description=_strip_html(a.get("intro", "")),
                    due_date=(
                        datetime.fromtimestamp(due_ts, tz=timezone.utc)
                        if due_ts
                        else None
                    ),
                    allow_submissions_from=(
                        datetime.fromtimestamp(allow_from_ts, tz=timezone.utc)
                        if allow_from_ts
                        else None
                    ),
                    cut_off_date=(
                        datetime.fromtimestamp(cutoff_ts, tz=timezone.utc)
                        if cutoff_ts
                        else None
                    ),
                    max_attempts=a.get("maxattempts", -1),
                    submission_types=a.get("configs", []),
                )
                assignments.append(assignment)

        return assignments

    def get_upcoming_assignments(
        self, days_ahead: int = 30
    ) -> list[Assignment]:
        """Get assignments due within the next N days.

        Args:
            days_ahead: Number of days to look ahead (default 30).

        Returns:
            List of upcoming Assignment objects, sorted by due date.
        """
        now = datetime.now(timezone.utc)
        all_assignments = self.get_assignments()

        upcoming = [
            a
            for a in all_assignments
            if a.due_date is not None
            and a.due_date > now
            and (a.days_remaining is not None and a.days_remaining <= days_ahead)
        ]

        return sorted(upcoming, key=lambda a: a.due_date or now)

    def get_calendar_events(
        self, days_ahead: int = 30
    ) -> list[dict[str, Any]]:
        """Fetch upcoming calendar events.

        Args:
            days_ahead: Number of days to look ahead.

        Returns:
            List of calendar event dictionaries.
        """
        now = int(time.time())
        end = now + (days_ahead * 86400)

        try:
            data = self._call(
                "core_calendar_get_calendar_events",
                **{
                    "events[timestart]": now,
                    "events[timeend]": end,
                    "options[userevents]": 1,
                    "options[siteevents]": 1,
                    "options[timestart]": now,
                    "options[timeend]": end,
                },
            )
            return data.get("events", [])
        except MoodleAPIError:
            # Fallback: some Moodle versions use a different endpoint
            try:
                data = self._call("core_calendar_get_calendar_upcoming_view")
                return data.get("events", [])
            except MoodleAPIError:
                console.print(
                    "[yellow]⚠ Calendar events not available[/yellow]"
                )
                return []

    def get_submission_status(
        self, assignment_id: int
    ) -> dict[str, Any]:
        """Check the submission status for a specific assignment.

        Args:
            assignment_id: The Moodle assignment ID.

        Returns:
            Submission status dictionary.
        """
        return self._call(
            "mod_assign_get_submission_status", assignid=assignment_id
        )

    def get_assignment_upload_url(self, assignment_id: int) -> str:
        """Generate the browser URL for uploading to an assignment.

        Args:
            assignment_id: The Moodle assignment ID.

        Returns:
            URL string to open in a browser.
        """
        return (
            f"{self._base_url}/mod/assign/view.php"
            f"?id={assignment_id}&action=editsubmission"
        )


def _strip_html(html: str) -> str:
    """Remove HTML tags from a string (basic implementation)."""
    import re

    clean = re.sub(r"<[^>]+>", "", html)
    clean = re.sub(r"&nbsp;", " ", clean)
    clean = re.sub(r"&amp;", "&", clean)
    clean = re.sub(r"&lt;", "<", clean)
    clean = re.sub(r"&gt;", ">", clean)
    clean = re.sub(r"&#\d+;", "", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean
