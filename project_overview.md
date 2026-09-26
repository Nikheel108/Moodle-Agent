# 📚 Moodle Assignment Agent — Project Overview

## Architecture

```mermaid
flowchart TD
    subgraph CLI["CLI Interface (cli.py)"]
        SETUP["moodle-agent setup"]
        SYNC["moodle-agent sync"]
        GEN["moodle-agent generate"]
        REVIEW["moodle-agent review"]
        WATCH["moodle-agent watch"]
        PKG["moodle-agent package"]
    end

    subgraph Security["Secure Credentials (credentials.py)"]
        KEYRING["Windows Credential Manager\n(keyring library)"]
    end

    subgraph Moodle["Moodle Integration (moodle_client.py)"]
        AUTH["Token Authentication"]
        COURSES["Fetch Enrolled Courses"]
        ASSIGNS["Fetch Assignments & Deadlines"]
        CALENDAR["Calendar Events"]
    end

    subgraph Storage["Local Storage (task_db.py)"]
        SQLITE["SQLite Database"]
        TASKS["Tasks Table"]
        REMINDERS["Reminders Table"]
        LOG["Activity Log"]
    end

    subgraph AI["AI Engine (study_generator.py)"]
        NOTES["Study Notes Generator"]
        QUIZ["Practice Quiz Generator"]
        DRAFT["Assignment Draft Generator"]
        EXPLAIN["Topic Explainer"]
    end

    subgraph Delivery["Delivery (upload_manager.py + notifications.py)"]
        ZIP["Zip Package Builder"]
        NOTIFY["Desktop Notifications"]
        DASHBOARD["Rich Dashboard"]
        APPROVE["Review & Approve Workflow"]
    end

    SETUP --> KEYRING
    SYNC --> AUTH --> KEYRING
    AUTH --> COURSES --> ASSIGNS
    ASSIGNS --> SQLITE
    GEN --> AI
    AI --> SQLITE
    REVIEW --> APPROVE
    APPROVE -->|"User approves"| ZIP
    ZIP -->|"Opens browser"| MOODLE_PAGE["Moodle Upload Page"]
    WATCH --> REMINDERS --> NOTIFY
    PKG --> ZIP

    style Security fill:#2d5a2d,stroke:#4caf50,color:#fff
    style AI fill:#1a3a5c,stroke:#2196f3,color:#fff
    style Delivery fill:#5c3a1a,stroke:#ff9800,color:#fff
```

## Module Map

| Module | Purpose | Key Classes/Functions |
|--------|---------|----------------------|
| [`config.py`](file:///d:/My%20personal%20projects/Agents/Assignment%20doing%20Agent/moodle_agent/config.py) | Constants, paths, model config | `DATA_DIR`, `GEMINI_MODEL`, `DATABASE_PATH` |
| [`credentials.py`](file:///d:/My%20personal%20projects/Agents/Assignment%20doing%20Agent/moodle_agent/credentials.py) | Secure credential storage | `store_credentials()`, `get_token()`, `interactive_setup()` |
| [`moodle_client.py`](file:///d:/My%20personal%20projects/Agents/Assignment%20doing%20Agent/moodle_agent/moodle_client.py) | Moodle REST API client | `MoodleClient`, `Assignment` dataclass |
| [`task_db.py`](file:///d:/My%20personal%20projects/Agents/Assignment%20doing%20Agent/moodle_agent/task_db.py) | SQLite task/reminder database | `TaskDatabase`, `TaskRecord`, `TaskStatus` |
| [`study_generator.py`](file:///d:/My%20personal%20projects/Agents/Assignment%20doing%20Agent/moodle_agent/study_generator.py) | AI-powered study materials | `generate_study_notes()`, `generate_practice_quiz()`, `generate_assignment_draft()` |
| [`upload_manager.py`](file:///d:/My%20personal%20projects/Agents/Assignment%20doing%20Agent/moodle_agent/upload_manager.py) | Zip packaging & review workflow | `prepare_upload_package()`, `review_and_approve()` |
| [`notifications.py`](file:///d:/My%20personal%20projects/Agents/Assignment%20doing%20Agent/moodle_agent/notifications.py) | Reminders & dashboard | `send_desktop_notification()`, `display_task_dashboard()` |
| [`cli.py`](file:///d:/My%20personal%20projects/Agents/Assignment%20doing%20Agent/moodle_agent/cli.py) | CLI entry point | `main()`, all `_cmd_*` handlers |

## Security Design

| Concern | Solution |
|---------|----------|
| Password storage | **Windows Credential Manager** via `keyring` — encrypted at OS level |
| API tokens | Stored in keyring, never written to files |
| Gemini API key | Stored in keyring, prompted with hidden input (`getpass`) |
| No auto-submission | All uploads require explicit user approval via interactive review |
| Credential cleanup | `moodle-agent clear-credentials` wipes all stored secrets |

> [!IMPORTANT]
> **No passwords, tokens, or API keys are ever stored in plain text** — not in config files, environment variables, or the database. Everything goes through the OS-level keyring.

## Quick Start

```bash
# 1. Install
cd "d:\My personal projects\Agents\Assignment doing Agent"
pip install -e .

# 2. Configure credentials (stored in Windows Credential Manager)
moodle-agent setup

# 3. Fetch assignments from Moodle
moodle-agent sync

# 4. View your assignment dashboard
moodle-agent status

# 5. Generate study materials for task #1
moodle-agent generate 1

# 6. Review and approve before submission
moodle-agent review

# 7. Start watch mode for continuous monitoring
moodle-agent watch
```

## All Commands

| Command | Description |
|---------|-------------|
| `setup` | Configure Moodle URL, username, password & Gemini API key |
| `sync --days 30` | Fetch upcoming assignments from Moodle |
| `list [--status pending]` | List tracked assignments, optionally filtered |
| `status` | Show full dashboard with urgency indicators |
| `detail <id>` | Show detailed info for a specific task |
| `generate <id> [--type all\|notes\|quiz\|draft]` | Generate AI study materials |
| `generate-all` | Generate materials for all pending tasks |
| `review [id]` | Interactive review and approval workflow |
| `package <id> [--files ...]` | Create zip upload package |
| `explain "topic" [--level detailed]` | Get an AI explanation of any topic |
| `watch --interval 3600` | Monitor mode: auto-sync + reminders |
| `open <id>` | Open Moodle submission page in browser |
| `clear-credentials` | Remove all stored credentials |

## Workflow

```mermaid
flowchart LR
    A["🔐 Setup\n(credentials)"] --> B["🔄 Sync\n(fetch assignments)"]
    B --> C["📊 Status\n(dashboard)"]
    C --> D["🤖 Generate\n(AI materials)"]
    D --> E["👀 Review\n(approve drafts)"]
    E --> F["📦 Package\n(create zip)"]
    F --> G["🌐 Open\n(Moodle page)"]
    G --> H["✅ Submit\n(YOU do this)"]

    style H fill:#ff5722,stroke:#d32f2f,color:#fff
```

> [!CAUTION]
> The agent **never auto-submits** to Moodle. Step 8 (Submit) is always done by **you** in the browser. The agent prepares everything and opens the page — you make the final call.

## Prerequisites

Before using this agent, your Moodle instance needs:

1. **Web Services enabled** — Site Administration → Advanced Features → Enable web services
2. **REST protocol enabled** — Site Administration → Plugins → Web services → Manage protocols
3. **Mobile app service** — Must be enabled (used for token authentication)
4. **User permissions** — Your account needs `mod/assign:view` capability
