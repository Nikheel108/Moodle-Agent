# Universal Assignment Agent 🎓🤖

An intelligent, secure personal agent for tracking, managing, and preparing assignments across learning management systems (Moodle, Canvas, Blackboard) utilizing Google Gemini AI.

![Streamlit UI Banner](https://img.shields.io/badge/UI-Streamlit-FF4B4B?logo=streamlit&logoColor=white) ![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python) ![Gemini AI](https://img.shields.io/badge/AI-Google_Gemini_Flash-4285F4?logo=google) ![License](https://img.shields.io/badge/License-MIT-green)

---

## 🚀 Overview

Managing assignments across multiple courses can be overwhelming. Deadlines change, requirements are buried in PDFs, and students lack a centralized command center.

The **Universal Assignment Agent** bridges this gap:
- **Synchronizes** your enrolled courses, assignment briefs, and due dates via LMS REST Web Services.
- **Maintains** an offline-capable local SQLite database for fast querying and status tracking.
- **Empowers** your study sessions with Google Gemini Flash AI, automatically generating structured assignment breakdowns and draft templates.
- **Exports & Submits** your finalized Markdown drafts as beautifully formatted PDFs directly back to Moodle.
- **Visualizes** everything in a modern, dark-theme Streamlit Dashboard.
- **Protects** your privacy by storing passwords and API keys strictly in the Windows Credential Manager.

---

## ✨ Key Features

- 🖥️ **Modern Web Dashboard**: A sleek, reactive Streamlit interface to filter tasks, preview AI-generated drafts, and monitor course progress.
- 🔄 **Automated Moodle Synchronization**: Pulls enrolled courses, assignments, and submission statuses automatically.
- 🧠 **Gemini AI Study Partner**: Uses Google's `google-genai` SDK to unpack assignment instructions and draft starter outlines based on your Custom Instructions.
- 📄 **Markdown to PDF Engine**: Click "Approve" to instantly convert your drafted `.md` files into professional PDFs using `markdown2` and `pdfkit`/`wkhtmltopdf`.
- 🚀 **One-Click Moodle Submission**: Bypass the LMS web interface—upload and finalize your assignment PDFs natively from the Agent's Action Center.
- 🔐 **Zero-Plaintext Security**: Integrates directly with Windows Credential Manager via Python `keyring`. No `.env` files or hardcoded credentials.

---

## 🛠️ Architecture

The Agent operates as a hybrid CLI + Streamlit Web Application:

1. **Credentials Engine**: Securely interfaces with Windows Keyring (DPAPI).
2. **Core Sync Service**: Periodically talks to Moodle REST APIs (`mod_assign_get_assignments`, `mod_assign_save_submission`).
3. **Local Store (SQLite)**: Caches tasks offline in `~/.moodle_agent/moodle_agent.db`.
4. **Streamlit UI**: Exposes a 5-tab web dashboard for managing the task pipeline.
5. **AI Engine**: Connects to Google AI Studio to generate contextual drafts into `~/.moodle_agent/drafts/`.

---

## 📦 Installation

### 1. Prerequisites
- **Python**: Version `3.10` or higher.
- **wkhtmltopdf**: Required for PDF generation. Ensure it is installed and added to your system `PATH`.
- **Moodle Account**: A valid student/instructor login on a Moodle instance with Web Services enabled.
- **Gemini API Key**: Obtain a free API key from [Google AI Studio](https://aistudio.google.com/).

### 2. Setup

Clone the repository and install the package:

```powershell
git clone https://github.com/Nikheel108/Moodle-Agent.git
cd Moodle-Agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

---

## 🚦 Usage Guide

### 1. Initial Configuration (CLI)

Run the setup wizard to securely configure your LMS URL, credentials, and Gemini API key:

```powershell
moodle-agent setup
```
*(Your credentials will be securely locked in the Windows Credential Manager under `moodle-assignment-agent`.)*

### 2. Launching the Web Dashboard (Recommended)

The easiest way to interact with the agent is via the Streamlit UI:

```powershell
python -m streamlit run moodle_agent/ui.py
```

#### Dashboard Walkthrough:
*   **🏠 Dashboard & Filters:** View interactive course cards with progress bars. Search and filter assignments by urgency.
*   **📈 Workflow Tracking:** Monitor which assignments are Pending, Drafted, Approved, or Submitted.
*   **⚡ Action Center:** The core workspace. Preview AI drafts, override safety locks, approve assignments (converts to PDF), and submit them straight to Moodle.
*   **⚙️ Admin & Controls:** Define global AI rules, configure PDF output themes (fonts/colors), and manage automated background sync frequencies.
*   **📜 History & Logs:** View historical submissions with timestamps and download past PDFs.

### 3. CLI Operations (Advanced)

If you prefer the terminal, the Agent features a rich TUI:

```powershell
# Force a sync with Moodle
moodle-agent sync

# List all upcoming assignments
moodle-agent list --upcoming 7

# Command the AI to generate a draft for a specific assignment ID
moodle-agent generate <id> --type draft

# Clear saved credentials
moodle-agent clear
```

---

## 📁 File Structure

All local application state is cleanly isolated in your user home directory:

```text
%USERPROFILE%\.moodle_agent\
├── moodle_agent.db     # SQLite database
├── drafts\             # Generated AI Markdown drafts
├── uploads\            # Finalized PDFs ready for submission
└── logs\               # Application execution logs
```

---

## 🛡️ Security & Academic Integrity

- **Credential Safety**: No passwords or API keys are stored in source code, `.env` files, or plain text. Everything relies on the OS-level Credential Manager.
- **Academic Integrity**: The AI features are designed to generate **scaffolding, structural outlines, and boilerplate**. Students are solely responsible for verifying, authoring, and finalizing their own submissions in accordance with their institution's academic honesty policies.

---

## 📜 License

This project is licensed under the MIT License.
