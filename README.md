# Moodle Assignment Agent 🎓🤖

An intelligent, secure personal agent for tracking, managing, and preparing Moodle assignments with Google Gemini AI.

---

## Overview

Managing assignments across multiple courses on Moodle can be overwhelming. Deadlines change, descriptions are buried within course modules, and students frequently lack a centralized view of what needs attention.

**Moodle Assignment Agent** bridges this gap:
- **Synchronizes** your enrolled courses, assignment briefs, attachments, and due dates via Moodle REST Web Services.
- **Maintains** an offline-capable local SQLite database for fast querying and status tracking.
- **Notifies** you through desktop alerts before assignments are due.
- **Empowers** your study sessions with Google Gemini 2.5 Flash AI, generating structured assignment breakdowns, research questions, study outlines, and draft templates.
- **Protects** your privacy by storing passwords and API keys in the Windows Credential Manager (`keyring`), ensuring no plaintext credentials ever hit the disk or version control.

---

## Architecture

```text
               +--------------------------------------------------+
               |               User Terminal / CLI                |
               |          (moodle-agent cli / rich TUI)           |
               +-------------------------+------------------------+
                                         |
                       +-----------------+-----------------+
                       |                                   |
         +-------------v-------------+       +-------------v-------------+
         |     Credentials Engine    |       |   Scheduler / Background  |
         |  (Windows Keyring / DPAPI)|       |   (schedule & plyer alerts)
         +-------------+-------------+       +-------------+-------------+
                       |                                   |
                       +-----------------+-----------------+
                                         |
                               +---------v---------+
                               |    Core Engine    |
                               +----+----+----+----+
                                    |    |    |
        +---------------------------+    |    +---------------------------+
        |                                |                                |
+-------v-------+                +-------v-------+                +-------v-------+
|  Moodle Sync  |                |  Local Store  |                |   Gemini AI   |
|    Service    |                | (SQLite DB &  |                |  Integration  |
|  (REST API)   |                |  Draft Files) |                | (2.5 Flash)   |
+-------+-------+                +-------+-------+                +-------+-------+
        |                                |                                |
        v                                v                                v
 Moodle Instance                 ~/.moodle_agent/                 Google AI Studio
 (Courses, Assigns,              (moodle_agent.db,                (Breakdown, Outlines,
  Submissions)                    drafts/, uploads/)               Research Guides)
```

---

## Key Features

- 🔐 **Zero-Plaintext Security**: Integrates directly with Windows Credential Manager via Python `keyring`. No `.env` files or hardcoded credentials.
- 🔄 **Automated Moodle Synchronization**: Pulls enrolled courses, assignments, submission statuses, and grading information using Moodle's REST API.
- 🧠 **Gemini 2.5 Flash Study Partner**: Uses Google's next-generation `google-genai` SDK to unpack assignment instructions, clarify grading criteria, and draft starter outlines.
- 📊 **Rich Terminal Interface**: Built with `rich` for colored terminal tables, progress spinners, Markdown rendering, and prompt wizards.
- 🔔 **Desktop Notifications**: Background watch mode notifies you at configurable intervals (e.g. 48h, 24h, 6h before due date) via native Windows notifications (`plyer`).
- 📁 **Organized Local Workspace**: Stores databases and structured drafts under `~/.moodle_agent/` so your working directories remain clean.

---

## Prerequisites

1. **Python**: Version `3.10` or higher.
2. **Moodle Account & URL**: Valid student or instructor login on any standard Moodle 3.x / 4.x instance with web services enabled.
3. **Gemini API Key**: Obtain a free API key from [Google AI Studio](https://aistudio.google.com/).

---

## Moodle Web Services Setup Instructions

Moodle exposes its REST API through web services. Depending on your institution's configuration, you can connect via one of the following methods:

### Method A: Mobile App Service (Standard & Recommended)

Most universities and institutions already have **Moodle Mobile Services** enabled. The agent uses this service (`moodle_mobile_app`) by default.

1. When you run `moodle-agent setup`, enter:
   - Your institution's Moodle base URL (e.g., `https://moodle.youruniversity.edu`).
   - Your standard Moodle username.
   - Your Moodle password.
2. The agent communicates with `/login/token.php` to obtain an authentication token and saves it securely in your OS keyring. Your password is never retained in plain text.

### Method B: Manual Security Keys (If Direct Token Login Is Disabled)

If your institution uses Single Sign-On (SSO / SAML / OAuth) or disables direct password login to web services:

1. Log into your Moodle web interface in your browser.
2. Click your user avatar in the top right corner and select **Preferences**.
3. Under **User account**, look for **Security keys** (or **Manage tokens**).
4. Locate the token associated with **Moodle mobile web service** (or your custom external service).
5. Copy the 32-character hexadecimal token.
6. When configuring the agent, provide this API token directly.

### Method C: Institutional / Administrator Configuration (Self-Hosted)

If you are an administrator or configuring a local/test Moodle instance:

1. **Enable Web Services**:
   - Go to `Site administration > Advanced features`.
   - Check **Enable web services** and click **Save changes**.
2. **Enable REST Protocol**:
   - Go to `Site administration > Server > Web services > Manage protocols`.
   - Enable the **REST protocol** eye icon.
3. **Enable Mobile Access**:
   - Go to `Site administration > Mobile app > Mobile settings`.
   - Check **Enable mobile service** and click **Save changes**.
4. **Required API Capabilities**:
   Ensure the authorized service role includes:
   - `core_webservice_get_site_info`
   - `core_enrol_get_users_courses`
   - `mod_assign_get_assignments`
   - `mod_assign_get_submission_status`
   - `mod_assign_save_submission`

---

## Installation

### 1. Clone or Navigate to the Project

```powershell
cd "d:\My personal projects\Agents\Assignment doing Agent"
```

### 2. Create and Activate a Virtual Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install Package in Editable Mode

```powershell
pip install --upgrade pip
pip install -e .
```

---

## Usage Guide

### 1. Interactive Setup

Run the setup wizard to securely configure your Moodle URL, credentials, and Gemini API key:

```powershell
moodle-agent setup
```

The wizard prompts for:
- Moodle Site URL (e.g. `https://moodle.example.edu`)
- Moodle Username and Password (hidden input)
- Google Gemini API Key (hidden input, optional for basic sync, required for AI features)

Credentials are saved into Windows Credential Manager under the service name `moodle-assignment-agent`.

### 2. Verify Configuration & Status

Check the status of stored credentials and database connectivity:

```powershell
moodle-agent status
```

### 3. Sync Assignments

Fetch the latest course enrollments, assignments, and due dates from Moodle:

```powershell
moodle-agent sync
```

### 4. List Deadlines

View all upcoming assignments formatted in a colored table:

```powershell
# Show all upcoming assignments
moodle-agent list

# Filter for assignments due within the next 7 days
moodle-agent list --upcoming 7

# Show completed / submitted assignments
moodle-agent list --all
```

### 5. Generate AI Study Outlines & Drafts

Use Gemini 2.5 Flash to parse assignment requirements and produce a structured draft template:

```powershell
# Generate study scaffold for an assignment by ID
moodle-agent draft <assignment_id>

# Open the generated draft file in your default editor
moodle-agent draft <assignment_id> --open
```

Drafts are saved as Markdown files inside `~/.moodle_agent/drafts/<course_name>/`.

### 6. Background Monitor & Notifications

Run the monitoring daemon to poll for deadline changes and pop native Windows toast alerts:

```powershell
moodle-agent watch --interval 60
```

### 7. Clear Credentials

Remove all stored credentials and API keys from Windows Credential Manager:

```powershell
moodle-agent clear
```

---

## File and Storage Structure

All local application state is isolated in your user home directory:

```text
%USERPROFILE%\.moodle_agent\
├── moodle_agent.db     # SQLite database storing synced assignments and metadata
├── drafts\             # Generated AI drafts and study notes organized by course
├── uploads\            # Prepared submission files and attachments
└── logs\               # Application execution and sync logs
```

---

## Security & Academic Integrity

- **Credential Safety**: No credentials, tokens, or API keys are stored in source code, configuration files, or environment variables. All secrets are delegated to the Windows DPAPI-protected Credential Manager via the Python `keyring` library.
- **Secure Transport**: All network operations to Moodle and Google Gemini are conducted over encrypted HTTPS connections.
- **Academic Integrity**: The AI features powered by Gemini 2.5 Flash are designed to generate **scaffolding, study summaries, research checklists, and structural outlines**. Students are responsible for authoring their own submissions in accordance with their institution's academic honesty policy.

---

## License

This project is licensed under the MIT License.
