# Remote Laboratory - PLC Data Acquisition System

## Remote Laboratory

The **Remote Laboratory** project provides a system for **collecting**, **storing**, and **managing** Siemens PLC signals through Snap7.

Data is recorded in files (`.txt`/`.csv`) and in a database (MySQL or SQLite), with support for:

- Plant/experiment management
- Professor pattern (ground truth) management
- Automatic correction by comparing collected sequences with expected patterns
- Chatbot assistance (terminal and web)

---

## Features

- Communication with Siemens PLCs (S7 family) via Snap7.
- State-change collection with `.txt` and `.csv` output.
- Persistence in `dadoscoletados2` and `dadoscoletados_summary`.
- Configurable database backend (`mysql` or `sqlite`).
- Flask UI for experiment and ground truth management.
- REST API for external integrations.
- LangChain chatbot integrated with the local API.
- Automatic sequence correction with didactic formatted output.

---

## Project Structure

```text
REMOTE-LABORATORY/
├── collecting_profinet.py              # Main Profinet collector
├── remote-laboratory.py                # Process orchestrator
├── requirements.txt
├── src/
│   └── db_dao.py                       # Database access (MySQL/SQLite)
├── lab-manager/
│   ├── main.py                         # Flask app (UI + API)
│   ├── readfiles.py                    # CSV reading utility
│   └── templates/
├── chatbot/
│   ├── main.py
│   ├── tools.py
│   └── settings.py
├── collector/
│   └── collecting_data_opcua_old.py    # Legacy OPC UA script
├── data/
│   ├── database-scripts/
│   └── remote_lab.sqlite3
└── collected-data/
```

---

## Requirements

- Python 3.9+
- SQLite 3 (bundled with Python) **or** MySQL 8+
- Python dependencies listed in `requirements.txt`

Install dependencies with:

```bash
pip install -r requirements.txt
```

---

## Configuration

Main environment variables:

```bash
# Database (default: mysql)
export DB_BACKEND=mysql
export MYSQL_HOST=localhost
export MYSQL_DATABASE=cae_dr
export MYSQL_USER=root
export MYSQL_PASSWORD=secret

# or SQLite
export DB_BACKEND=sqlite
export SQLITE_DB_PATH=data/remote_lab.sqlite3

# Flask / AI
export FLASK_SECRET_KEY=dev
export OPENAI_API_KEY="your-key"
# optional
export AI_KEY_SECRET="secret-for-encryption"
export CHATBOT_API_BASE="http://localhost:5000/api"
export CHATBOT_MODEL="gpt-4o-mini"
```

---

## How It Works

1. The collector connects to the PLC using the plant IP/rack/slot configuration.
2. It reads the configured DB byte and interprets the monitored bits.
3. It detects state changes and records step, value, and timestamp.
4. It persists the data to files and database.
5. It consolidates the experiment pulse train in `dadoscoletados_summary`.

---

## Usage

### Option 1: helper runner (recommended)

```bash
python remote-laboratory.py
```

Flags:

```bash
python remote-laboratory.py --collector
python remote-laboratory.py --terminal-chatbot
```

### Option 2: run modules separately

```bash
python lab-manager/main.py
python collecting_profinet.py
python -m chatbot.main
```

---

## Web Managers (Flask)

With Flask running at `http://localhost:5000`:

- `/` - Experiment Manager (`plant_config`)
- `/ground-truth` - Professor Pattern Manager
- `/dados-coletados` - Collected data listing/import + automatic correction
- `/chatbot` - Web chatbot
- `/settings/ai-key` - AI key settings

---

## REST API

Base URL: `http://localhost:5000/api`

Experiments:

- `POST /api/experiments`
- `GET /api/experiments/<id>`
- `PUT /api/experiments/<id>`
- `DELETE /api/experiments/<id>`

Ground truth:

- `GET /api/ground-truth`
- `POST /api/ground-truth`
- `GET /api/ground-truth/<id>`
- `PUT /api/ground-truth/<id>`
- `DELETE /api/ground-truth/<id>`

---

## Notes

- The collector creates output files inside a date-based folder in the current directory.
- `RemoteLaboratoryDAO` falls back to SQLite at `data/remote_lab.sqlite3` when needed.
- `collector/collecting_data_opcua_old.py` is legacy and not part of the main current flow.

---

## Credits & Attribution

- Original project: [Remote Laboratory – PLC Data Acquisition System](https://github.com/RodSalg/remote-laboratory)
- UFG capstone/team: Rodrigo Ferraz Azevedo, Guido Machado, Marcelo Marcomini
- Code by Rodrigo Ferraz Azevedo.

---

## Changelog

> Versioning created from commit history to simplify future maintenance.

### v0.6.0 (2026-02-02)

- Automatic correction migrated to a deterministic Python flow.
- REST API routes restored/normalized.
- `human_prompt` refined for PLC auto-correction output format (2026-01-31).

### v0.5.0 (2025-12-18)

- Added total time to automatic correction output.
- Added floating chatbot drawer across all pages with page context awareness.
- Refined auto-correction prompt and chatbot tools structure.
- Added processing feedback in the auto-correction form.
- Improved chatbot with professor-style guidance and starter prompts.
- Added media assets to README.

### v0.4.0 (2025-12-01)

- Standardized app port to `5000`.
- Added `.env` loading for AI key.
- Integrated web chatbot into `lab-manager`.
- Renamed Flask entrypoint and added helper runner script.
- Added encrypted AI key storage.
- Updated chatbot to LangChain 1.0 APIs.
- Added chatbot API availability warning and improved key setup documentation.

### v0.3.0 (2025-11-27)

- Added CSV utility (`lab-manager/readfiles.py`) and updated base documentation.
- Added plant configuration CRUD in web UI + CSV import.
- Added SQLite backend support, including collected-data schema.
- Reorganized project tree and consolidated `lab-manager`.
- Added REST API for experiments and ground truth with endpoint documentation.
- Added LangChain chatbot prototype.
- Added collected-data listing in the web interface.
- Added professor-pattern import with experiment selection and CSV steps support.
- Added automatic correction flow comparing collected data with professor patterns.
- Centralized documentation/dependencies and updated `requirements.txt`.

### v0.2.0 (2025-07-07)

- Evolved OPC UA/Profinet acquisition scripts.
- Updated folder organization and README.
- Switched to using the latest experiment ID instead of a fixed value.
- Cleaned old data and added new datasets.
- Added plant switching menu with automatic configuration (`get_plant_config`/`list_plant_configs`).
- Refactored SQL scripts and added groundwork for `ground_truth_patterns`.
- Adjusted experiment execution time limit.

### v0.1.0 (2025-03-19)

- Initial project commit on GitHub.
