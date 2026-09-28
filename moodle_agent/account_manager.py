import json
import keyring
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict
from moodle_agent.config import BASE_DATA_DIR, SERVICE_NAME

ACCOUNTS_FILE = BASE_DATA_DIR / "accounts.json"

@dataclass
class Account:
    username: str
    moodle_url: str
    name: str = ""
    prn: str = ""
    batch: str = ""
    is_active: bool = False

def load_accounts() -> List[Account]:
    if not ACCOUNTS_FILE.exists():
        return []
    try:
        with open(ACCOUNTS_FILE, "r") as f:
            data = json.load(f)
            return [Account(**acc) for acc in data]
    except Exception:
        return []

def save_accounts(accounts: List[Account]):
    with open(ACCOUNTS_FILE, "w") as f:
        json.dump([asdict(acc) for acc in accounts], f, indent=4)

def get_active_account() -> Optional[Account]:
    for acc in load_accounts():
        if acc.is_active:
            return acc
    accounts = load_accounts()
    if accounts:
        accounts[0].is_active = True
        save_accounts(accounts)
        return accounts[0]
    return None

def set_active_account(username: str) -> None:
    accounts = load_accounts()
    for acc in accounts:
        acc.is_active = (acc.username == username)
    save_accounts(accounts)

def add_or_update_account(account: Account, password: str, api_token: str = None):
    accounts = load_accounts()
    if account.is_active:
        for a in accounts:
            a.is_active = False
            
    existing = next((a for a in accounts if a.username == account.username), None)
    if existing:
        accounts.remove(existing)
    accounts.append(account)
    save_accounts(accounts)
    
    keyring.set_password(SERVICE_NAME, f"{account.username}_password", password)
    if api_token:
        keyring.set_password(SERVICE_NAME, f"{account.username}_api_token", api_token)

def delete_account(username: str):
    accounts = [a for a in load_accounts() if a.username != username]
    save_accounts(accounts)
    try:
        keyring.delete_password(SERVICE_NAME, f"{username}_password")
    except: pass
    try:
        keyring.delete_password(SERVICE_NAME, f"{username}_api_token")
    except: pass

def get_password(username: str) -> Optional[str]:
    return keyring.get_password(SERVICE_NAME, f"{username}_password")

def get_api_token(username: str) -> Optional[str]:
    return keyring.get_password(SERVICE_NAME, f"{username}_api_token")

def get_db_path(username: str) -> Path:
    # Use a separate DB per user
    safe_name = "".join(c for c in username if c.isalnum() or c in ('-', '_'))
    return BASE_DATA_DIR / f"tasks_{safe_name}.db"
