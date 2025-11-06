# Remote Laboratory - PLC Data Acquisition System

## Overview

> ⚠️ **UFG TCC adaptation:** This repository extends the public work available at [github.com/RodSalg/remote-laboratory](https://github.com/RodSalg/remote-laboratory).  
> The entire codebase, folder naming and original scripts remain credited to the authors of that project; the changes documented here are exclusive to the capstone requirements at Universidade Federal de Goiás (UFG).

---

## Adaptations for the TCC project

- `bot/readfiles.py`: CLI helper that scans every `.csv` located in the project root and prints each file as a formatted text table (normalizes column sizes, pads spacing, and keeps headers aligned). Run `python bot/readfiles.py` to inspect collected datasets directly from the terminal.

---

## Remote Laboratory

The **Remote Laboratory** project provides a robust and automated system for **collecting**, **saving**, and **organizing** data from a Siemens PLC via the Snap7 communication protocol.  
The collected data is processed in real time, stored both in text/CSV files, and inserted into a structured **MySQL database** for further analysis.

The system is designed to facilitate experiments in mechatronics and automation laboratories, especially for pattern detection based on pulse trains.

This fork customizes configuration, documentation and helper scripts for the UFG capstone without altering the original ownership of the core solution.

---

## Features

- 🛠️ Real-time communication with Siemens PLC (S7 family) using **Snap7**.
- 💄 Local storage of pulse trains in **.txt** and **.csv** formats.
- 🧑‍🧬 Automated calculation of **pulse train steps**.
- 🏛️ Insertions and retrievals from a **MySQL database** (`cae_dr` schema).
- 📈 Support for experiment tracking and pulse pattern management.
- 🧹 Automatic versioning of exported files (avoiding data overwriting).
- 🧹 Easy integration with future modules (e.g., machine learning, pattern recognition).

---

## Project Structure

```
REMOTE-LABORATORY/
├── __pycache__/              # Python cache files (ignored)
├── data/                     # Generated text and CSV files
├── database-scripts/         # SQL scripts (CREATE statements) for database structure
│    ├── cae_dr_dadoscoletados2.sql
│    ├── patterns_from_professor.sql
│    └── summary_pulse_values.sql
├── src/
│    └── db_dao.py             # Database access object (RemoteLaboratoryDAO)
├── collecting_data_opcua_old.py  # [legacy] Script for OPC UA communication
├── collecting_profinet.py        # [legacy] Script for Profinet communication
├── insert_pulse_train_on_database.py  # Utility to insert custom pulse trains
├── LICENSE
├── README.md                  # Project documentation (this file)
├── .gitignore                 # Files and folders excluded from Git
```

---

## Requirements

- Python 3.9+
- MySQL Server (tested with MySQL 8.0)
- Python libraries:
  - `snap7`
  - `mysql-connector-python`

Install dependencies with:

```bash
pip install python-snap7 mysql-connector-python
```

---

## How It Works

1. The system **connects to a PLC** using the IP, rack, and slot configurations.
2. It **reads a byte** from a specified DB block and **interprets it bit-by-bit**.
3. Whenever a change is detected, it:
   - Converts the bit array into an **integer step**.
   - Saves the data into a `.txt` and `.csv` file.
   - Inserts the step and timestamp into the database.
4. After collection ends, the **pulse train** is automatically **saved into a summary table** for future analysis.

---

## Usage

### Run the main script

```bash
python collecting_data_opcua_old.py
```

> (You can adapt this command if using another acquisition script.)

---

### Configuration

Inside the code (`collecting_data_opcua_old.py`), you can modify:

- `plc_ip` → PLC IP address (e.g., `"192.168.0.10"`)
- `rack`, `slot` → PLC hardware configuration
- `db_number`, `byte_index` → Memory address to read
- `timeout` → Experiment duration (in seconds)

---

### Database Schema

You need to run the SQL scripts inside the `database-scripts/` folder to create the necessary tables:

- `dadoscoletados2`: stores individual pulse data
- `dadoscoletados_summary`: stores full pulse train patterns

---

## Notes

- The generated `.txt` and `.csv` files are saved with automatic **version control** (`v1`, `v2`, etc.).
- The database connection parameters (host, database, user, password) are configured inside the `RemoteLaboratoryDAO` class.
- This project is modular and ready for expansion (for example: adding OPC UA or Profinet acquisitions).

---

## Credits & Attribution

- Original project: [Remote Laboratory – PLC Data Acquisition System](https://github.com/RodSalg/remote-laboratory) (rod-salgado and collaborators).  
- UFG capstone adjustments: documentation notes, utility scripts and data structures tailored to the academic context.

---

## Team

- Rodrigo Ferraz Azevedo  
- Guido Machado  
- Marcelo Marcomini

---

## .gitignore

All unnecessary files (such as cache, virtual environments, local settings, etc.) are already excluded from Git tracking.

---

## License

This project is licensed under the [MIT License](LICENSE).
