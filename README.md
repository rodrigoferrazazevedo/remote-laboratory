# Remote Laboratory - PLC Data Acquisition System

## Overview

> ⚠️ **UFG TCC adaptation:** This repository extends the public work available at [github.com/RodSalg/remote-laboratory](https://github.com/RodSalg/remote-laboratory).  
> The entire codebase, folder naming and original scripts remain credited to the authors of that project; the changes documented here are exclusive to the capstone requirements at Universidade Federal de Goiás (UFG).

---

## Adaptations for the TCC project

- `lab-manager/readfiles.py`: CLI helper that scans every `.csv` located in the project root and prints each file as a formatted text table (normalizes column sizes, pads spacing, and keeps headers aligned). Run `python lab-manager/readfiles.py` to inspect collected datasets directly from the terminal.

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
├── lab-manager/              # Flask UI + REST API for experiment/pattern management
│    ├── plant_config_app.py
│    ├── templates/
│    └── readfiles.py
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
- SQLite 3 (já incluso no Python) **ou** um servidor MySQL 8.0+
- Python libraries:
  - `snap7`
  - `mysql-connector-python` (somente necessário quando `DB_BACKEND=mysql`)

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
python collecting_profinet.py
```

> (You can adapt this command if using another acquisition script.)

---

### Configuration

Inside the code (`collecting_profinet.py`), you can modify:

- `plc_ip` → PLC IP address (e.g., `"192.168.0.10"`)
- `rack`, `slot` → PLC hardware configuration
- `db_number`, `byte_index` → Memory address to read
- `timeout` → Experiment duration (in seconds)

---

### Database Schema

You need to run the SQL scripts inside the `database-scripts/` folder to create the necessary tables:

- `dadoscoletados2`: stores individual pulse data
- `dadoscoletados_summary`: stores full pulse train patterns
- `ground_truth_patterns`: referência dos padrões do professor para cada experimento (alimentados pela nova UI de gerenciamento)

---

### Database backend selection

`RemoteLaboratoryDAO` agora aceita tanto **MySQL** quanto **SQLite**. A escolha é feita através da variável de ambiente `DB_BACKEND`:

```bash
# MySQL (padrão)
export DB_BACKEND=mysql
export MYSQL_HOST=localhost
export MYSQL_DATABASE=cae_dr
export MYSQL_USER=root
export MYSQL_PASSWORD=secret

# ou SQLite
export DB_BACKEND=sqlite
export SQLITE_DB_PATH=/abs/path/para/remote_lab.sqlite3
```

- Quando `DB_BACKEND=mysql` (valor padrão) nada muda em relação ao comportamento antigo; você só precisa garantir que o `mysql-connector-python` está instalado e que o banco `cae_dr` exista.
- Quando `DB_BACKEND=sqlite`, o arquivo informado em `SQLITE_DB_PATH` é criado automaticamente (padrão: `data/remote_lab.sqlite3`) e todas as consultas passam a usar o driver embutido `sqlite3`.
- Certifique-se de apontar `SQLITE_DB_PATH` para um local com permissão de escrita. Se for um caminho inválido, o DAO volta automaticamente para `data/remote_lab.sqlite3`.

Essa configuração vale automaticamente para toda a aplicação Flask (`lab-manager/plant_config_app.py`) e para os scripts que utilizam `RemoteLaboratoryDAO`.

---

### Web managers (Flask)

- **Gerenciador de Experimentos** – disponível em `http://localhost:5000/` – lista/cria/edita/exclui registros da tabela `plant_config`.
- **Gerenciador de Padrões do Professor** – disponível em `http://localhost:5000/ground-truth` – manipula os dados de `ground_truth_patterns`, permitindo cadastrar os padrões vindos do script `patterns_from_professor.sql` diretamente da interface web.

Ambos os módulos compartilham o mesmo backend (MySQL ou SQLite), então qualquer alteração via UI é automaticamente refletida no banco correspondente.

---

### REST API

O mesmo aplicativo (`lab-manager/plant_config_app.py`) expõe um blueprint JSON em `http://localhost:5000/api`. Principais rotas:

- `GET /api/experiments` / `POST /api/experiments` / `GET|PUT|DELETE /api/experiments/<id>` para listar, criar e administrar entradas em `plant_config`.
- `GET /api/ground-truth` / `POST /api/ground-truth` / `GET|PUT|DELETE /api/ground-truth/<id>` para gerenciar `ground_truth_patterns`.

As rotas executam validações básicas e retornam códigos HTTP apropriados, facilitando a integração com chatbots ou qualquer outro cliente.

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

## Chatbot (LangChain)

O diretório `chatbot/` contém um protótipo de agente que utiliza LangChain + GPT para conversar com os endpoints do `lab-manager`. Para usar:

1. Instale as dependências: `pip install -r chatbot/requirements.txt`
2. Garanta que o Flask esteja rodando (`python lab-manager/plant_config_app.py`)
3. Exporte `OPENAI_API_KEY` e rode `python -m chatbot.main`

O agente reconhece comandos como “listar experimentos”, “cadastrar padrão do professor” etc., chamando as ferramentas declaradas em `chatbot/tools.py`.

---

## .gitignore

All unnecessary files (such as cache, virtual environments, local settings, etc.) are already excluded from Git tracking.

---

## License

This project is licensed under the [MIT License](LICENSE).
