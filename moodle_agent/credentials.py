"""Secure credential management using OS keyring (Windows Credential Manager)."""
import getpass
import keyring
from rich.console import Console
from rich.prompt import Prompt

from moodle_agent.config import SERVICE_NAME

console = Console()


def store_credentials(moodle_url: str, username: str, password: str) -> None:
    """Store Moodle credentials securely in the OS keyring."""
    keyring.set_password(SERVICE_NAME, "moodle_url", moodle_url)
    keyring.set_password(SERVICE_NAME, "username", username)
    keyring.set_password(SERVICE_NAME, "password", password)
    console.print("[green]✓ Credentials stored securely in Windows Credential Manager[/green]")


def store_token(token: str) -> None:
    """Store Moodle API token securely."""
    keyring.set_password(SERVICE_NAME, "api_token", token)
    console.print("[green]✓ API token stored securely[/green]")


def store_gemini_key(api_key: str) -> None:
    """Store Gemini API key securely."""
    keyring.set_password(SERVICE_NAME, "gemini_api_key", api_key)
    console.print("[green]✓ Gemini API key stored securely[/green]")


def get_credentials() -> dict[str, str | None]:
    """Retrieve stored Moodle credentials."""
    return {
        "moodle_url": keyring.get_password(SERVICE_NAME, "moodle_url"),
        "username": keyring.get_password(SERVICE_NAME, "username"),
        "password": keyring.get_password(SERVICE_NAME, "password"),
    }


def get_token() -> str | None:
    """Retrieve stored Moodle API token."""
    return keyring.get_password(SERVICE_NAME, "api_token")


def get_gemini_key() -> str | None:
    """Retrieve stored Gemini API key."""
    return keyring.get_password(SERVICE_NAME, "gemini_api_key")


def clear_credentials() -> None:
    """Remove all stored credentials from the keyring."""
    for key in ["moodle_url", "username", "password", "api_token", "gemini_api_key"]:
        try:
            keyring.delete_password(SERVICE_NAME, key)
        except keyring.errors.PasswordDeleteError:
            pass
    console.print("[yellow]✓ All credentials cleared[/yellow]")


def interactive_setup() -> None:
    """Interactive credential setup wizard."""
    console.print("\n[bold cyan]═══ Moodle Assignment Agent - Setup ═══[/bold cyan]\n")
    console.print("Your credentials will be stored securely in Windows Credential Manager.")
    console.print("[dim]No passwords are stored in files or environment variables.[/dim]\n")

    moodle_url = Prompt.ask("Moodle URL (e.g. https://moodle.school.edu)")
    moodle_url = moodle_url.rstrip("/")

    username = Prompt.ask("Moodle username")
    password = getpass.getpass("Moodle password (hidden): ")

    store_credentials(moodle_url, username, password)

    console.print("\n[dim]Gemini API key is needed for AI-generated study materials.[/dim]")
    gemini_key = getpass.getpass("Gemini API key (hidden, press Enter to skip): ")
    if gemini_key.strip():
        store_gemini_key(gemini_key.strip())
    else:
        console.print("[yellow]⚠ Gemini API key skipped. AI features will be disabled.[/yellow]")

    console.print("\n[green bold]✓ Setup complete![/green bold]")


def has_credentials() -> bool:
    """Check if credentials are already configured."""
    creds = get_credentials()
    return all(v is not None for v in creds.values())
