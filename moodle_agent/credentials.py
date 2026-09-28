import getpass
import keyring
from rich.console import Console
from rich.prompt import Prompt

from moodle_agent.config import SERVICE_NAME
import moodle_agent.account_manager as acc_mgr

console = Console()

def get_credentials() -> dict[str, str | None]:
    """Retrieve stored Moodle credentials for the active account."""
    acc = acc_mgr.get_active_account()
    if not acc:
        return {"moodle_url": None, "username": None, "password": None}
    
    return {
        "moodle_url": acc.moodle_url,
        "username": acc.username,
        "password": acc_mgr.get_password(acc.username),
    }

def get_token() -> str | None:
    """Retrieve stored Moodle API token for the active account."""
    acc = acc_mgr.get_active_account()
    if not acc: return None
    return acc_mgr.get_api_token(acc.username)

def get_gemini_key() -> str | None:
    """Retrieve stored Gemini API key."""
    return keyring.get_password(SERVICE_NAME, "gemini_api_key")

def store_token(token: str) -> None:
    """Store Moodle API token securely for the active account."""
    acc = acc_mgr.get_active_account()
    if acc:
        keyring.set_password(SERVICE_NAME, f"{acc.username}_api_token", token)
        console.print(f"[green]✓ API token stored securely for {acc.username}[/green]")


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

def store_gemini_key(api_key: str) -> None:
    """Store Gemini API key securely."""
    keyring.set_password(SERVICE_NAME, "gemini_api_key", api_key)
    console.print("[green]✓ Gemini API key stored securely[/green]")

def clear_credentials() -> None:
    pass
