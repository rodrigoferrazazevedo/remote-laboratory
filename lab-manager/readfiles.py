import ast
import csv
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.db_dao import RemoteLaboratoryDAO


HEADER_ALIASES: Dict[str, str] = {
    "passo": "step_index",
    "indice": "step_index",
    "step": "pulse_train",
    "valor_do_passo": "pulse_value",
    "valor_passo": "pulse_value",
    "valor": "pulse_value",
    "duracao": "duration",
    "duracao_s": "duration",
    "duracao_segundos": "duration",
    "timestamp": "timestamp",
}


@dataclass(frozen=True)
class ExperimentMetadata:
    name: str
    identifier: int


def _read_csv(file_path: Path) -> List[List[str]]:
    """Load CSV rows from file handling missing columns."""
    rows: List[List[str]] = []
    with file_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.reader(handle):
            rows.append([cell.strip() for cell in row])
    return rows


def _normalize_header(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^0-9a-zA-Z]+", "_", ascii_value).strip("_").lower()
    return HEADER_ALIASES.get(slug, slug)


def _build_header_map(header_row: List[str]) -> Dict[str, int]:
    mapping: Dict[str, int] = {}
    for index, title in enumerate(header_row):
        normalized = _normalize_header(title)
        if normalized:
            mapping.setdefault(normalized, index)
    return mapping


def _get_cell(row: List[str], mapping: Dict[str, int], key: str) -> Optional[str]:
    index = mapping.get(key)
    if index is None or index >= len(row):
        return None
    return row[index]


def _safe_int(value: Optional[str]) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _safe_float(value: Optional[str]) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _serialize_pulse_train(raw_value: Optional[str]) -> Optional[str]:
    if raw_value is None:
        return None
    cleaned = raw_value.strip()
    if not cleaned:
        return None
    try:
        parsed = ast.literal_eval(cleaned)
    except (ValueError, SyntaxError):
        return cleaned
    return json.dumps(parsed)


def _extract_experiment_metadata(file_path: Path) -> ExperimentMetadata:
    stem = file_path.stem
    match = re.search(r"_(\d+)_?$", stem)
    if not match:
        raise ValueError(
            "Não foi possível identificar o número do experimento a partir do nome do arquivo."
        )
    experiment_id = int(match.group(1))
    experiment_name = stem[: match.start()].rstrip("_") or stem
    return ExperimentMetadata(experiment_name, experiment_id)


def _persist_rows(csv_file: Path, rows: List[List[str]], dao: RemoteLaboratoryDAO) -> None:
    if len(rows) <= 1:
        print(f"{csv_file.name}: arquivo sem linhas de dados para salvar no banco.")
        return

    try:
        metadata = _extract_experiment_metadata(csv_file)
    except ValueError as exc:
        print(f"{csv_file.name}: {exc}")
        return

    header_map = _build_header_map(rows[0])
    required_fields = {"step_index", "pulse_train", "pulse_value", "timestamp"}
    missing = [field for field in required_fields if field not in header_map]
    if missing:
        print(
            f"{csv_file.name}: colunas obrigatórias ausentes e o arquivo não foi importado: {', '.join(missing)}"
        )
        return

    has_duration = "duration" in header_map
    inserted = 0
    skipped = 0

    for line_number, row in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in row):
            skipped += 1
            continue

        step_index = _safe_int(_get_cell(row, header_map, "step_index"))
        pulse_value = _safe_int(_get_cell(row, header_map, "pulse_value"))
        timestamp_value = _safe_float(_get_cell(row, header_map, "timestamp"))
        pulse_train = _serialize_pulse_train(_get_cell(row, header_map, "pulse_train"))
        duration_value = (
            _safe_float(_get_cell(row, header_map, "duration")) if has_duration else None
        )

        if None in (step_index, pulse_value, timestamp_value) or pulse_train is None:
            skipped += 1
            continue

        try:
            if has_duration:
                dao.insert_data_with_duration(
                    metadata.identifier,
                    step_index,
                    pulse_train,
                    pulse_value,
                    timestamp_value,
                    metadata.name,
                    duration_value or 0.0,
                )
            else:
                dao.insert_data_into_database(
                    metadata.identifier,
                    step_index,
                    pulse_train,
                    pulse_value,
                    timestamp_value,
                    metadata.name,
                )
            inserted += 1
        except Exception as error:  # pragma: no cover - database side-effect.
            skipped += 1
            print(
                f"{csv_file.name}: erro ao salvar a linha {line_number} no banco de dados: {error}"
            )

    print(
        f"{csv_file.name}: {inserted} linhas inseridas no banco de dados (linhas ignoradas: {skipped})."
    )


def _format_table(rows: Iterable[Iterable[str]]) -> str:
    """Return a simple text table for the provided rows."""
    row_list = [list(row) for row in rows]
    if not row_list:
        return "Tabela vazia."

    column_count = max(len(row) for row in row_list)
    normalized_rows = [
        row + [""] * (column_count - len(row)) for row in row_list
    ]
    column_widths = [
        max(len(row[index]) for row in normalized_rows)
        for index in range(column_count)
    ]

    def render_line(row: List[str]) -> str:
        return " | ".join(
            value.ljust(column_widths[index]) for index, value in enumerate(row)
        )

    header = render_line(normalized_rows[0])
    separator = "-+-".join("-" * width for width in column_widths)
    body = "\n".join(render_line(row) for row in normalized_rows[1:])
    return "\n".join([header, separator, body]) if body else header


def print_csv_tables(root_path: Path, dao: RemoteLaboratoryDAO) -> None:
    """Find CSV files in `root_path`, print them, and persist their rows."""
    csv_files = sorted(root_path.glob("*.csv"))
    if not csv_files:
        print("Nenhum arquivo CSV encontrado na raiz do projeto.")
        return

    for csv_file in csv_files:
        print(f"\nArquivo: {csv_file.name}")
        try:
            rows = _read_csv(csv_file)
            print(_format_table(rows))
            _persist_rows(csv_file, rows, dao)
        except Exception as error:  # pragma: no cover - console feedback only.
            print(f"Erro ao ler o arquivo: {error}")


def main() -> None:
    dao = RemoteLaboratoryDAO()
    print_csv_tables(PROJECT_ROOT, dao)


if __name__ == "__main__":
    main()
