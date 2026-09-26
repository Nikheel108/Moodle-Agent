"""Configuration module for Moodle Assignment Agent.

Defines constants, data storage paths under the user's home directory,
keyring identifiers, Moodle web service endpoints, and Google Gemini model settings.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

# Keyring service name for Windows Credential Manager
SERVICE_NAME: Final[str] = "moodle-assignment-agent"

# Base directory for all agent data storage, located in the user's home directory
DATA_DIR: Final[Path] = Path.home() / ".moodle_agent"
BASE_DATA_DIR: Final[Path] = DATA_DIR

# Storage paths relative to ~/.moodle_agent/
DATABASE_PATH: Final[Path] = DATA_DIR / "moodle_agent.db"
DRAFTS_DIR: Final[Path] = DATA_DIR / "drafts"
UPLOADS_DIR: Final[Path] = DATA_DIR / "uploads"
LOGS_DIR: Final[Path] = DATA_DIR / "logs"

# Gemini model identifier (using latest 2.5 Flash model)
GEMINI_MODEL: Final[str] = "gemini-2.5-flash"

# Student details (included in every draft header)
STUDENT_NAME: Final[str] = "Nikheel C Khadakabhavi"
STUDENT_PRN: Final[str] = "202401110020"
STUDENT_BATCH: Final[str] = "A2"

STUDENT_HEADER: Final[str] = (
    f"**Name:** {STUDENT_NAME}  \n"
    f"**PRN:** {STUDENT_PRN}  \n"
    f"**Batch:** {STUDENT_BATCH}  \n"
)

# Moodle Web Service Endpoints and defaults
MOODLE_TOKEN_ENDPOINT: Final[str] = "/login/token.php"
MOODLE_WEBSERVICE_ENDPOINT: Final[str] = "/webservice/rest/server.php"
MOODLE_DEFAULT_SERVICE: Final[str] = "moodle_mobile_app"

# Standard Moodle Web Service Function Names
MOODLE_FUNC_GET_SITE_INFO: Final[str] = "core_webservice_get_site_info"
MOODLE_FUNC_GET_COURSES: Final[str] = "core_enrol_get_users_courses"
MOODLE_FUNC_GET_ASSIGNMENTS: Final[str] = "mod_assign_get_assignments"
MOODLE_FUNC_GET_SUBMISSION_STATUS: Final[str] = "mod_assign_get_submission_status"
MOODLE_FUNC_SAVE_SUBMISSION: Final[str] = "mod_assign_save_submission"

# Notification and polling configuration
DEFAULT_POLL_INTERVAL_MINUTES: Final[int] = 60
DEFAULT_DUE_SOON_HOURS: Final[int] = 48


def ensure_directories() -> None:
    """Ensure that all necessary application storage directories exist."""
    for directory in (BASE_DATA_DIR, DRAFTS_DIR, UPLOADS_DIR, LOGS_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def get_token_url(base_url: str) -> str:
    """Construct the full URL for obtaining a Moodle web service token.

    Args:
        base_url: Base URL of the Moodle instance (e.g., https://moodle.example.edu).

    Returns:
        The complete token endpoint URL.
    """
    clean_base = base_url.rstrip("/")
    return f"{clean_base}{MOODLE_TOKEN_ENDPOINT}"


def get_webservice_url(base_url: str) -> str:
    """Construct the full URL for invoking Moodle REST web services.

    Args:
        base_url: Base URL of the Moodle instance (e.g., https://moodle.example.edu).

    Returns:
        The complete REST API endpoint URL.
    """
    clean_base = base_url.rstrip("/")
    return f"{clean_base}{MOODLE_WEBSERVICE_ENDPOINT}"
