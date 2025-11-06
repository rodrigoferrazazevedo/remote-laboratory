import csv
from pathlib import Path
from typing import Iterable, List


def _read_csv(file_path: Path) -> List[List[str]]:
    """Load CSV rows from file handling missing columns."""
    rows: List[List[str]] = []
    with file_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.reader(handle):
            rows.append([cell.strip() for cell in row])
    return rows


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


def print_csv_tables(root_path: Path) -> None:
    """Find CSV files in `root_path` and print their contents as tables."""
    csv_files = sorted(root_path.glob("*.csv"))
    if not csv_files:
        print("Nenhum arquivo CSV encontrado na raiz do projeto.")
        return

    for csv_file in csv_files:
        print(f"\nArquivo: {csv_file.name}")
        try:
            rows = _read_csv(csv_file)
            print(_format_table(rows))
        except Exception as error:  # pragma: no cover - console feedback only.
            print(f"Erro ao ler o arquivo: {error}")


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    print_csv_tables(project_root)


if __name__ == "__main__":
    main()
