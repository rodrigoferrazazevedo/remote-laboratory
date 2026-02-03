import ast
import csv
import io
import json
import re
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from flask import (
    Blueprint,
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from dotenv import load_dotenv
import httpx
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    messages_from_dict,
    messages_to_dict,
)

BOT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BOT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Carrega variáveis do .env, se existir, antes de qualquer leitura de ambiente.
load_dotenv(PROJECT_ROOT / ".env")

from chatbot.main import build_agent  # noqa: E402  (import after sys.path tweak)
from chatbot.settings import settings as chatbot_settings  # noqa: E402
from chatbot.tools import APIClient, build_tools  # noqa: E402
from src.db_dao import RemoteLaboratoryDAO  # noqa: E402  (import after sys.path tweak)


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev")
api = Blueprint("api", __name__, url_prefix="/api")


def _get_dao() -> RemoteLaboratoryDAO:
    return RemoteLaboratoryDAO()


def _resolve_openai_key(dao: RemoteLaboratoryDAO) -> str:
    settings = dao.get_ai_key_settings() or {}
    source = settings.get("source") or "system_variable"
    env_key = os.environ.get("OPENAI_API_KEY") or chatbot_settings.openai_api_key

    if source == "manual":
        manual_key, invalid = dao.load_manual_ai_key()
        if manual_key:
            return manual_key
        if invalid:
            print("Aviso: AI Key manual corrompida. Limparei o registro para permitir novo cadastro.")
            dao.clear_ai_key_settings()
        raise RuntimeError("Nenhuma AI Key manual salva. Cadastre-a na tela de Configurações.")

    if env_key:
        return env_key

    # Fallback: se não houver env mas existir manual cadastrada, usa-a.
    manual_key = dao.get_manual_ai_key()
    if manual_key:
        return manual_key

    raise RuntimeError(
        "Defina a variável de ambiente OPENAI_API_KEY ou cadastre a AI Key manualmente na tela de Configurações."
    )


def _build_chat_agent():
    dao = _get_dao()
    api_key = _resolve_openai_key(dao)
    os.environ.setdefault("OPENAI_API_KEY", api_key)
    client = APIClient()
    try:
        client.list_experiments()
    except httpx.HTTPError as exc:
        raise RuntimeError(
            f"API indisponível em {client.base_url}. "
            "Garanta que o Flask esteja rodando e que o banco esteja acessível. "
            f"Detalhe: {exc}"
        ) from exc
    tools = build_tools(client)
    return build_agent(tools, api_key)


def _parse_history(payload: List[Dict[str, Any]]) -> List[BaseMessage]:
    if not payload:
        return []
    return list(messages_from_dict(payload))


def _serialize_messages(messages: List[BaseMessage]) -> List[Dict[str, Any]]:
    return messages_to_dict(messages)


def _last_ai_message(messages: List[BaseMessage]) -> str:
    last_ai = next((m for m in reversed(messages) if isinstance(m, AIMessage)), None)
    if not last_ai:
        return ""
    content = last_ai.content
    if isinstance(content, (dict, list)):
        return json.dumps(content, ensure_ascii=False)
    return str(content)


def _ai_key_form_state(dao: RemoteLaboratoryDAO) -> Dict[str, Any]:
    settings = dao.get_ai_key_settings() or {}
    return {
        "source": settings.get("source") or "system_variable",
        "has_manual": bool(settings.get("encrypted_key")),
    }


def _collect_form_data() -> Dict[str, str]:
    fields = [
        "experiment_name",
        "ip_profinet",
        "rack_profinet",
        "slot_profinet",
        "db_number_profinet",
        "num_of_inputs",
        "num_of_outputs",
    ]
    return {field: (request.form.get(field) or "").strip() for field in fields}


def _validate_form_data(form_data: Dict[str, str]) -> Tuple[Dict[str, int], List[str]]:
    errors: List[str] = []
    numeric_values: Dict[str, int] = {}

    if not form_data["experiment_name"]:
        errors.append("O nome do experimento é obrigatório.")

    if not form_data["ip_profinet"]:
        errors.append("O IP do Profinet é obrigatório.")

    numeric_fields = [
        "rack_profinet",
        "slot_profinet",
        "db_number_profinet",
        "num_of_inputs",
        "num_of_outputs",
    ]

    for field in numeric_fields:
        raw_value = form_data[field]
        if not raw_value:
            errors.append(f"O campo {field} é obrigatório.")
            continue
        try:
            numeric_values[field] = int(raw_value)
        except ValueError:
            errors.append(f"O campo {field} precisa ser numérico.")

    return numeric_values, errors


def _collect_ground_truth_form_data() -> Dict[str, str]:
    return {
        "experiment_name": (request.form.get("experiment_name") or "").strip(),
        "ground_truth": (request.form.get("ground_truth") or "").strip(),
    }


def _validate_ground_truth_form_data(form_data: Dict[str, str]) -> List[str]:
    errors: List[str] = []
    if not form_data["experiment_name"]:
        errors.append("O nome do experimento é obrigatório.")
    if not form_data["ground_truth"]:
        errors.append("O padrão é obrigatório.")
    return errors


def _parse_step_cell(raw_step: str) -> Any:
    """
    Tenta converter o texto do CSV (ex: "[False, True, False]") em lista de bool.
    Caso falhe, devolve o valor original para ser serializado como string.
    """
    if raw_step is None:
        return ""
    try:
        parsed = ast.literal_eval(raw_step)
        return parsed
    except Exception:
        return raw_step


def _safe_int(value: str):
    try:
        return int(value)
    except Exception:
        return None if value == "" else value


def _safe_float(value: str):
    try:
        return float(value)
    except Exception:
        return None


def _truncate_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except Exception:
            return None
    return None


def _format_bits(value: int | None, width: int) -> str:
    if value is None or width <= 0:
        return ""
    return format(value, f"0{width}b")


def _format_correction_output(
    pattern_pairs: List[Tuple[Any, Any]],
    sequence_pairs: List[Tuple[Any, Any]],
    io_names: List[str],
) -> str:
    pattern = pattern_pairs or []
    sequence = sequence_pairs or []
    if sequence and len(sequence) > 1:
        sequence = sequence[:-1]

    pattern_len = len(pattern)
    seq_len = len(sequence)
    if pattern_len == 0 or seq_len == 0:
        reason = []
        if pattern_len == 0:
            reason.append("Padrão vazio")
        if seq_len == 0:
            reason.append("Sequência vazia")
        reason_text = " e ".join(reason)
        return f"não\n\n0\n\n{reason_text}"

    bit_count = len(io_names)
    max_valid_value = (2 ** bit_count - 1) if bit_count > 0 else None

    def _step_ok(expected: Any, actual: Any) -> bool:
        exp_int = _truncate_int(expected)
        act_int = _truncate_int(actual)
        if exp_int is None or act_int is None:
            return False
        return exp_int == act_int

    def _time_ok(expected: Any, actual: Any) -> bool:
        exp_int = _truncate_int(expected)
        act_int = _truncate_int(actual)
        if exp_int is None or act_int is None:
            return False
        return exp_int == act_int

    def _value_invalid(value: Any) -> bool:
        if max_valid_value is None:
            return False
        value_int = _truncate_int(value)
        if value_int is None:
            return True
        return value_int > max_valid_value

    def _format_value_time(value: Any, time_value: Any) -> str:
        return f"{value}/{time_value}"

    def _emoji(step_ok: bool, time_ok: bool) -> str:
        if step_ok and time_ok:
            return "✅✅"
        if step_ok and not time_ok:
            return "✅❌"
        if not step_ok and time_ok:
            return "❌✅"
        return "❌❌"

    complete_occurrences = 0
    total_cycles = seq_len // pattern_len
    for cycle in range(total_cycles):
        matched = True
        for offset in range(pattern_len):
            exp_step, exp_time = pattern[offset]
            act_step, act_time = sequence[cycle * pattern_len + offset]
            if _value_invalid(act_step):
                matched = False
                break
            if not _step_ok(exp_step, act_step) or not _time_ok(exp_time, act_time):
                matched = False
                break
        if matched:
            complete_occurrences += 1

    approved = complete_occurrences >= 2

    if approved:
        return f"sim\n\n{complete_occurrences}"

    lines: List[str] = []
    lines.append("não")
    lines.append("")
    lines.append(str(complete_occurrences))
    lines.append("")
    lines.append("| Padrão do professor até o erro | Sequência do aluno até o erro | Valor incorreto |")

    table_rows: List[Tuple[int, int, Any, Any, bool, bool]] = []
    for index in range(seq_len):
        exp_step, exp_time = pattern[index % pattern_len]
        act_step, act_time = sequence[index]
        step_match = _step_ok(exp_step, act_step)
        time_match = _time_ok(exp_time, act_time)
        table_rows.append((index, index % pattern_len, act_step, act_time, step_match, time_match))

        professor_parts = [_format_value_time(exp_step, exp_time)]
        student_parts = [f"{_format_value_time(act_step, act_time)} {_emoji(step_match, time_match)}"]

        if step_match and time_match:
            incorrect_value = ""
        elif step_match and not time_match:
            incorrect_value = f"{act_time}"
        elif not step_match and time_match:
            incorrect_value = f"{act_step}"
        else:
            incorrect_value = f"{act_step}; {act_time}"
        lines.append(f"| {', '.join(professor_parts)} | {', '.join(student_parts)} | {incorrect_value} |")

    lines.append("")
    for start, mismatch_index, act_step, act_time, step_match, time_match in table_rows:
        exp_step, exp_time = pattern[mismatch_index]
        if step_match and time_match:
            continue
        if not step_match:
            exp_step_int = _truncate_int(exp_step)
            act_step_int = _truncate_int(act_step)
            bits_expected = _format_bits(exp_step_int, bit_count)
            bits_actual = _format_bits(act_step_int, bit_count)
            lines.append(f"Valor incorreto: {act_step}")
            if bits_actual:
                lines.append(f"- Decodificação em bits: {bits_actual}")
            if bits_expected:
                diff_ios = []
                for i in range(bit_count):
                    bit_index = bit_count - 1 - i
                    exp_bit = (exp_step_int >> bit_index) & 1 if exp_step_int is not None else 0
                    act_bit = (act_step_int >> bit_index) & 1 if act_step_int is not None else 0
                    if exp_bit != act_bit:
                        io_name = io_names[i] if i < len(io_names) else f"io_{i}"
                        exp_state = "ligado" if exp_bit else "desligado"
                        act_state = "ligado" if act_bit else "desligado"
                        diff_ios.append(f"{io_name}: {exp_state} → {act_state}")
                if diff_ios:
                    for item in diff_ios:
                        lines.append(f"- {item}")
        if not time_match:
            lines.append(f"Tempo: {act_time} ❌")

    return "\n".join(lines)


def _extract_value_time_pairs(sequence: Any) -> List[Tuple[Any, Any]]:
    """
    Normaliza sequências para pares (valor, tempo) usados no prompt de correção.
    Aceita listas/tuplas de dicts ou pares já formatados; mantém None quando não houver tempo.
    """
    pairs: List[Tuple[Any, Any]] = []
    if isinstance(sequence, str):
        raw = sequence.strip().rstrip(".;")
        try:
            parsed = json.loads(raw)
        except Exception:
            try:
                parsed = ast.literal_eval(raw)
            except Exception:
                try:
                    parsed = ast.literal_eval(f"[{raw}]")
                except Exception:
                    tuples = []
                    for match in re.findall(r"\(([^)]+)\)", raw):
                        parts = [p.strip() for p in match.split(",")]
                        if len(parts) < 2:
                            continue
                        try:
                            left = float(parts[0])
                            right = float(parts[1])
                        except Exception:
                            continue
                        tuples.append((left, right))
                    if tuples:
                        return _extract_value_time_pairs(tuples)
                    return pairs
        return _extract_value_time_pairs(parsed)
    if not isinstance(sequence, (list, tuple)):
        return pairs

    for item in sequence:
        if isinstance(item, dict):
            value = item.get("pulse_value", item.get("pulse_train", item.get("value", item.get("step"))))
            time_value = item.get("duration", item.get("timeToChange", item.get("time_to_change")))
            pairs.append((value, time_value))
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            pairs.append((item[0], item[1]))
        elif isinstance(item, (int, float, str)):
            pairs.append((item, None))
        else:
            pairs.append((item, None))
    return pairs


def _resolve_io_names(config: Dict[str, Any], ground_truth_value: Any) -> List[str]:
    """
    Tenta obter os nomes das IOs da configuração, do ground truth ou cria nomes genéricos
    a partir da quantidade de entradas/saídas.
    """
    possible_keys = ("io_names", "io_list", "ios", "IOs")

    for key in possible_keys:
        value = config.get(key) if isinstance(config, dict) else None
        if value:
            return list(value)

    if isinstance(ground_truth_value, dict):
        for key in possible_keys:
            value = ground_truth_value.get(key)
            if value:
                return list(value)

    if isinstance(ground_truth_value, (list, tuple)):
        for item in ground_truth_value:
            if isinstance(item, dict):
                for key in possible_keys:
                    value = item.get(key)
                    if value:
                        return list(value)

    num_bits = (config.get("num_of_inputs") or 0) + (config.get("num_of_outputs") or 0)
    if num_bits:
        return [f"io_{i}" for i in range(num_bits)]

    return []


def _parse_collected_csv_upload(file_storage) -> List[Dict[str, Any]]:
    required_cols = {"Passo", "Step", "Valor do Passo", "Duracao (s)", "Timestamp"}
    if not file_storage:
        raise ValueError("Selecione um arquivo CSV para importar.")
    file_storage.stream.seek(0)
    wrapper = io.TextIOWrapper(file_storage.stream, encoding="utf-8", newline="")
    reader = csv.DictReader(wrapper)
    headers = set(reader.fieldnames or [])
    if not required_cols.issubset(headers):
        raise ValueError(f"O CSV precisa conter as colunas: {', '.join(sorted(required_cols))}.")

    parsed_rows: List[Dict[str, Any]] = []
    for row in reader:
        step_value = _parse_step_cell((row.get("Step") or "").strip())
        passo_value = _safe_int((row.get("Passo") or "").strip())
        pulse_value = _safe_int((row.get("Valor do Passo") or "").strip())
        duration_value = _safe_float((row.get("Duracao (s)") or "").strip())
        parsed_rows.append(
            {
                "step": step_value,
                "pulse_train": passo_value,
                "pulse_value": pulse_value,
                "time_to_change": duration_value,
                "duration": duration_value,
                "time_stamp": (row.get("Timestamp") or "").strip(),
            }
        )
    return parsed_rows


def _parse_ground_truth_csv_upload(file_storage) -> List[Dict[str, str]]:
    required_cols = {"experiment_name", "ground_truth"}
    if not file_storage:
        raise ValueError("Selecione um arquivo CSV para importar.")
    file_storage.stream.seek(0)
    wrapper = io.TextIOWrapper(file_storage.stream, encoding="utf-8", newline="")
    reader = csv.DictReader(wrapper)
    headers = {h.strip() for h in (reader.fieldnames or [])}
    if not required_cols.issubset(headers):
        raise ValueError("O CSV precisa conter as colunas: experiment_name, ground_truth.")
    rows: List[Dict[str, str]] = []
    for row in reader:
        exp_name = (row.get("experiment_name") or "").strip()
        ground_truth = (row.get("ground_truth") or "").strip()
        if not exp_name or not ground_truth:
            continue
        rows.append({"experiment_name": exp_name, "ground_truth": ground_truth})
    return rows


@app.route("/settings/ai-key", methods=["GET", "POST"])
def ai_key_settings():
    dao = _get_dao()
    state = _ai_key_form_state(dao)
    form = {"source": state["source"], "manual_key": ""}
    has_manual_key = state["has_manual"]

    if request.method == "POST":
        selected_source = (request.form.get("ai_key_source") or "system_variable").strip()
        manual_key = (request.form.get("manual_key") or "").strip()
        errors: List[str] = []

        if selected_source not in ("system_variable", "manual"):
            errors.append("Selecione uma opção válida para AI Key.")
        if selected_source == "manual" and not manual_key:
            errors.append("Informe a AI Key quando a opção Inserida manualmente estiver selecionada.")

        if not errors:
            try:
                saved = dao.save_ai_key_settings(selected_source, manual_key)
            except Exception as exc:
                flash(f"Erro ao salvar a AI Key: {exc}", "error")
            else:
                if saved:
                    flash("Configuração de AI Key salva com sucesso.", "success")
                    return redirect(url_for("ai_key_settings"))
                flash("Não foi possível salvar a AI Key.", "error")
        for error in errors:
            flash(error, "error")
        form = {"source": selected_source, "manual_key": manual_key}
        has_manual_key = has_manual_key or (selected_source == "manual" and bool(manual_key))

    return render_template(
        "settings/ai_key.html",
        title="Configurações",
        form=form,
        has_manual_key=has_manual_key,
    )


@app.route("/")
def index():
    dao = _get_dao()
    configs = dao.list_full_plant_configs()
    return render_template(
        "plant_config/index.html",
        configs=configs,
        title="Gerenciador de Experimentos",
    )


@app.route("/create", methods=["GET", "POST"])
def create_config():
    form_data = _collect_form_data() if request.method == "POST" else {}
    if request.method == "POST":
        numeric_values, errors = _validate_form_data(form_data)
        if not errors:
            dao = _get_dao()
            created_id = dao.create_plant_config(
                form_data["experiment_name"],
                form_data["ip_profinet"],
                numeric_values.get("rack_profinet"),
                numeric_values.get("slot_profinet"),
                numeric_values.get("db_number_profinet"),
                numeric_values.get("num_of_inputs"),
                numeric_values.get("num_of_outputs"),
            )
            if created_id:
                flash("Configuração criada com sucesso!", "success")
                return redirect(url_for("index"))
            flash("Não foi possível salvar a configuração.", "error")
        for error in errors:
            flash(error, "error")
    return render_template(
        "plant_config/form.html",
        form=form_data,
        title="Nova configuração",
        submit_label="Criar",
        cancel_url=url_for("index"),
    )


@app.route("/edit/<int:config_id>", methods=["GET", "POST"])
def edit_config(config_id: int):
    dao = _get_dao()
    existing = dao.get_plant_config_by_id(config_id)
    if not existing:
        flash("Configuração não encontrada.", "error")
        return redirect(url_for("index"))

    if request.method == "POST":
        form_data = _collect_form_data()
        numeric_values, errors = _validate_form_data(form_data)
        if not errors:
            dao.update_plant_config(
                config_id,
                form_data["experiment_name"],
                form_data["ip_profinet"],
                numeric_values.get("rack_profinet"),
                numeric_values.get("slot_profinet"),
                numeric_values.get("db_number_profinet"),
                numeric_values.get("num_of_inputs"),
                numeric_values.get("num_of_outputs"),
            )
            flash("Configuração atualizada com sucesso!", "success")
            return redirect(url_for("index"))
        for error in errors:
            flash(error, "error")
        form = form_data
    else:
        form = {
            "experiment_name": existing.get("experiment_name", ""),
            "ip_profinet": existing.get("ip_profinet", ""),
            "rack_profinet": str(existing.get("rack_profinet", "")),
            "slot_profinet": str(existing.get("slot_profinet", "")),
            "db_number_profinet": str(existing.get("db_number_profinet", "")),
            "num_of_inputs": str(existing.get("num_of_inputs", "")),
            "num_of_outputs": str(existing.get("num_of_outputs", "")),
        }

    return render_template(
        "plant_config/form.html",
        form=form,
        title="Editar configuração",
        submit_label="Salvar",
        cancel_url=url_for("index"),
    )


@app.route("/delete/<int:config_id>", methods=["POST"])
def delete_config(config_id: int):
    dao = _get_dao()
    removed = dao.delete_plant_config(config_id)
    if removed:
        flash("Configuração removida.", "success")
    else:
        flash("Não foi possível remover a configuração.", "error")
    return redirect(url_for("index"))


@app.route("/ground-truth")
def ground_truth_index():
    dao = _get_dao()
    patterns = dao.list_ground_truth_patterns()
    experiments = dao.list_full_plant_configs()
    return render_template(
        "ground_truth/index.html",
        patterns=patterns,
        experiments=experiments,
        title="Padrões do Professor",
    )


@app.route("/ground-truth/create", methods=["GET", "POST"])
def create_ground_truth():
    form_data = _collect_ground_truth_form_data() if request.method == "POST" else {}
    if request.method == "POST":
        errors = _validate_ground_truth_form_data(form_data)
        if not errors:
            dao = _get_dao()
            created_id = dao.create_ground_truth_pattern(
                form_data["experiment_name"],
                form_data["ground_truth"],
            )
            if created_id:
                flash("Padrão cadastrado com sucesso!", "success")
                return redirect(url_for("ground_truth_index"))
            flash("Não foi possível salvar o padrão.", "error")
        for error in errors:
            flash(error, "error")
    return render_template(
        "ground_truth/form.html",
        form=form_data,
        title="Novo padrão do professor",
        submit_label="Criar",
        cancel_url=url_for("ground_truth_index"),
    )


@app.route("/ground-truth/edit/<int:pattern_id>", methods=["GET", "POST"])
def edit_ground_truth(pattern_id: int):
    dao = _get_dao()
    existing = dao.get_ground_truth_pattern_by_id(pattern_id)
    if not existing:
        flash("Padrão não encontrado.", "error")
        return redirect(url_for("ground_truth_index"))

    if request.method == "POST":
        form_data = _collect_ground_truth_form_data()
        errors = _validate_ground_truth_form_data(form_data)
        if not errors:
            updated = dao.update_ground_truth_pattern(
                pattern_id,
                form_data["experiment_name"],
                form_data["ground_truth"],
            )
            if updated:
                flash("Padrão atualizado com sucesso!", "success")
                return redirect(url_for("ground_truth_index"))
            flash("Não foi possível atualizar o padrão.", "error")
        for error in errors:
            flash(error, "error")
        form = form_data
    else:
        form = {
            "experiment_name": existing.get("experiment_name", ""),
            "ground_truth": existing.get("ground_truth", ""),
        }

    return render_template(
        "ground_truth/form.html",
        form=form,
        title="Editar padrão do professor",
        submit_label="Salvar",
        cancel_url=url_for("ground_truth_index"),
    )


@app.route("/ground-truth/delete/<int:pattern_id>", methods=["POST"])
def delete_ground_truth(pattern_id: int):
    dao = _get_dao()
    removed = dao.delete_ground_truth_pattern(pattern_id)
    if removed:
        flash("Padrão removido.", "success")
    else:
        flash("Não foi possível remover o padrão.", "error")
    return redirect(url_for("ground_truth_index"))


@app.post("/ground-truth/import")
def import_ground_truth():
    experiment_id_raw = (request.form.get("experiment_id") or "").strip()
    upload = request.files.get("data_file")

    if not upload or upload.filename == "":
        flash("Selecione um arquivo CSV para importar.", "error")
        return redirect(url_for("ground_truth_index"))

    dao = _get_dao()
    experiments = dao.list_full_plant_configs()

    # Se o usuário selecionou um experimento, interpretamos o CSV no formato de passos.
    if experiment_id_raw:
        try:
            experiment_id = int(experiment_id_raw)
        except (TypeError, ValueError):
            flash("O ID do experimento deve ser um número inteiro.", "error")
            return redirect(url_for("ground_truth_index"))

        config = dao.get_plant_config_by_id(experiment_id)
        if not config:
            flash("Experimento não encontrado.", "error")
            return redirect(url_for("ground_truth_index"))

        try:
            rows = _parse_collected_csv_upload(upload)
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("ground_truth_index"))

        if not rows:
            flash("Nenhum passo encontrado no arquivo.", "error")
            return redirect(url_for("ground_truth_index"))

        ground_truth_payload = json.dumps(rows, ensure_ascii=False)
        saved = dao.upsert_ground_truth_pattern(config["experiment_name"], ground_truth_payload)
        if saved:
            flash(
                f"Padrão importado para '{config['experiment_name']}' com {len(rows)} passo(s).",
                "success",
            )
        else:
            flash("Não foi possível salvar o padrão importado.", "error")
        return redirect(url_for("ground_truth_index"))

    # Caso contrário, esperamos o CSV com colunas experiment_name e ground_truth.
    try:
        rows = _parse_ground_truth_csv_upload(upload)
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("ground_truth_index"))

    if not rows:
        flash("Nenhum padrão encontrado no arquivo.", "error")
        return redirect(url_for("ground_truth_index"))

    allowed = {exp["experiment_name"] for exp in experiments}
    imported, skipped = dao.import_ground_truth_patterns(rows, allowed_experiments=allowed)
    if imported:
        flash(f"Importação concluída: {imported} padrões criados/atualizados.", "success")
    if skipped:
        flash(f"{skipped} padrão(ões) ignorado(s) por não haver experimento correspondente.", "error")
    if not imported and not skipped:
        flash("Nenhum padrão foi importado.", "error")
    return redirect(url_for("ground_truth_index"))


@app.route("/chatbot")
def chatbot_page():
    dao = _get_dao()
    try:
        _resolve_openai_key(dao)
        openai_ready = True
    except Exception:
        openai_ready = False
    return render_template(
        "chatbot/index.html",
        title="Chatbot",
        api_base=chatbot_settings.api_base,
        openai_ready=openai_ready,
    )


@app.route("/chatbot/embed")
def chatbot_embed():
    dao = _get_dao()
    try:
        _resolve_openai_key(dao)
        openai_ready = True
    except Exception:
        openai_ready = False
    return render_template(
        "chatbot/embed.html",
        title="Chatbot",
        api_base=chatbot_settings.api_base,
        openai_ready=openai_ready,
    )


@app.post("/chatbot/ask")
def chatbot_ask():
    data = request.get_json(silent=True) or {}
    user_input = (data.get("message") or "").strip()
    page_context = data.get("page_context")
    if not user_input:
        return jsonify({"error": "A mensagem não pode ser vazia."}), 400
    history_payload = data.get("history") or []
    try:
        history = _parse_history(history_payload)
    except Exception:
        return jsonify({"error": "Histórico de mensagens inválido."}), 400

    if page_context and isinstance(page_context, dict):
        safe_context = {
            "path": str(page_context.get("path") or ""),
            "title": str(page_context.get("title") or ""),
            "heading": str(page_context.get("heading") or ""),
            "content_preview": str(page_context.get("content_preview") or ""),
        }
        user_input = (
            "Contexto da página atual (para responder sobre o conteúdo exibido):\n"
            + json.dumps(safe_context, ensure_ascii=False)
            + "\n\nPergunta do usuário:\n"
            + user_input
        )

    try:
        agent = _build_chat_agent()
        messages = history + [HumanMessage(content=user_input)]
        result = agent.invoke({"messages": messages})
        reply = _last_ai_message(result["messages"])
        return jsonify({"reply": reply, "history": _serialize_messages(result["messages"])}), 200
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503
    except httpx.HTTPError as exc:
        return jsonify({"error": f"Erro ao acessar a API: {exc}"}), 502
    except Exception as exc:
        return jsonify({"error": f"Erro inesperado: {exc}"}), 500


@app.route("/dados-coletados")
def collected_data():
    dao = _get_dao()
    rows = dao.list_collected_data()
    experiments = dao.list_full_plant_configs()
    return render_template(
        "collected_data/index.html",
        title="Dados coletados",
        rows=rows,
        experiments=experiments,
        correction_result=None,
        correction_error=None,
    )


@app.post("/dados-coletados/import")
def import_collected_data():
    experiment_id_raw = (request.form.get("experiment_id") or "").strip()
    upload = request.files.get("data_file")

    errors: List[str] = []
    try:
        experiment_id = int(experiment_id_raw)
    except (TypeError, ValueError):
        errors.append("O ID do experimento deve ser um número inteiro.")

    if not upload or upload.filename == "":
        errors.append("Selecione um arquivo CSV para importar.")

    if errors:
        for error in errors:
            flash(error, "error")
        return redirect(url_for("collected_data"))

    try:
        rows = _parse_collected_csv_upload(upload)
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("collected_data"))

    dao = _get_dao()
    config = dao.get_plant_config_by_id(experiment_id)
    if not config:
        flash("Experimento não encontrado.", "error")
        return redirect(url_for("collected_data"))
    experiment_name = config.get("experiment_name") or ""

    imported = dao.import_collected_rows(experiment_id, experiment_name, rows)
    if imported:
        flash(f"Importação concluída: {imported} linhas adicionadas.", "success")
    else:
        flash("Nenhum dado foi importado. Verifique o arquivo e tente novamente.", "error")
    return redirect(url_for("collected_data"))


@app.post("/dados-coletados/correcao")
def collected_data_correction():
    experiment_id_raw = (request.form.get("experiment_id") or "").strip()
    try:
        experiment_id = int(experiment_id_raw)
    except (TypeError, ValueError):
        flash("Selecione um experimento válido para correção automática.", "error")
        return redirect(url_for("collected_data"))

    dao = _get_dao()
    config = dao.get_plant_config_by_id(experiment_id)
    if not config:
        flash("Experimento não encontrado.", "error")
        return redirect(url_for("collected_data"))

    ground = dao.get_ground_truth_by_experiment(config["experiment_name"])
    if not ground:
        flash("Nenhum Padrão do Professor cadastrado para este experimento.", "error")
        return redirect(url_for("collected_data"))

    collected_rows = dao.list_collected_data_by_experiment(experiment_id, limit=500)
    if not collected_rows:
        flash("Nenhum dado coletado encontrado para este experimento.", "error")
        return redirect(url_for("collected_data"))

    ground_truth_raw = ground.get("ground_truth") if isinstance(ground, dict) else ground
    try:
        ground_truth_value = json.loads(ground_truth_raw)
    except Exception:
        ground_truth_value = ground_truth_raw

    pattern_pairs = _extract_value_time_pairs(ground_truth_value)
    sequence_pairs = _extract_value_time_pairs(collected_rows)
    io_names = _resolve_io_names(config or {}, ground_truth_value)

    try:
        reply = _format_correction_output(pattern_pairs, sequence_pairs, io_names)
    except Exception as exc:
        flash(f"Erro ao executar a correção automática: {exc}", "error")
        return redirect(url_for("collected_data"))

    rows = dao.list_collected_data()
    experiments = dao.list_full_plant_configs()
    return render_template(
        "collected_data/index.html",
        title="Dados coletados",
        rows=rows,
        experiments=experiments,
        correction_result=reply,
        correction_error=None,
    )


@api.post("/experiments")
def api_create_experiment():
    payload = _json_payload()
    required = [
        "experiment_name",
        "ip_profinet",
        "rack_profinet",
        "slot_profinet",
        "db_number_profinet",
        "num_of_inputs",
        "num_of_outputs",
    ]
    _require_fields(payload, required)
    dao = _get_dao()
    created_id = dao.create_plant_config(
        payload["experiment_name"],
        payload["ip_profinet"],
        int(payload["rack_profinet"]),
        int(payload["slot_profinet"]),
        int(payload["db_number_profinet"]),
        int(payload["num_of_inputs"]),
        int(payload["num_of_outputs"]),
    )
    if not created_id:
        abort(400, description="Não foi possível criar o experimento.")
    return jsonify({"id": created_id}), 201


@api.get("/experiments/<int:config_id>")
def api_get_experiment(config_id: int):
    dao = _get_dao()
    config = dao.get_plant_config_by_id(config_id)
    if not config:
        abort(404, description="Experimento não encontrado.")
    return jsonify(config)


@api.put("/experiments/<int:config_id>")
def api_update_experiment(config_id: int):
    payload = _json_payload()
    required = [
        "experiment_name",
        "ip_profinet",
        "rack_profinet",
        "slot_profinet",
        "db_number_profinet",
        "num_of_inputs",
        "num_of_outputs",
    ]
    _require_fields(payload, required)
    dao = _get_dao()
    updated = dao.update_plant_config(
        config_id,
        payload.get("experiment_name"),
        payload.get("ip_profinet"),
        int(payload.get("rack_profinet")),
        int(payload.get("slot_profinet")),
        int(payload.get("db_number_profinet")),
        int(payload.get("num_of_inputs")),
        int(payload.get("num_of_outputs")),
    )
    if not updated:
        abort(400, description="Não foi possível atualizar o experimento.")
    return jsonify({"updated": True})


@api.delete("/experiments/<int:config_id>")
def api_delete_experiment(config_id: int):
    dao = _get_dao()
    removed = dao.delete_plant_config(config_id)
    if not removed:
        abort(404, description="Experimento não encontrado.")
    return jsonify({"deleted": True})


@api.get("/ground-truth")
def api_list_ground_truth():
    dao = _get_dao()
    return jsonify(dao.list_ground_truth_patterns())


@api.post("/ground-truth")
def api_create_ground_truth():
    payload = _json_payload()
    _require_fields(payload, ["experiment_name", "ground_truth"])
    dao = _get_dao()
    created_id = dao.create_ground_truth_pattern(payload["experiment_name"], payload["ground_truth"])
    if not created_id:
        abort(400, description="Não foi possível criar o padrão.")
    return jsonify({"id": created_id}), 201


@api.get("/ground-truth/<int:pattern_id>")
def api_get_ground_truth(pattern_id: int):
    dao = _get_dao()
    pattern = dao.get_ground_truth_pattern_by_id(pattern_id)
    if not pattern:
        abort(404, description="Padrão não encontrado.")
    return jsonify(pattern)


@api.put("/ground-truth/<int:pattern_id>")
def api_update_ground_truth(pattern_id: int):
    payload = _json_payload()
    _require_fields(payload, ["experiment_name", "ground_truth"])
    dao = _get_dao()
    updated = dao.update_ground_truth_pattern(
        pattern_id,
        payload.get("experiment_name"),
        payload.get("ground_truth"),
    )
    if not updated:
        abort(400, description="Não foi possível atualizar o padrão.")
    return jsonify({"updated": True})


def _json_payload():
    data = request.get_json(silent=True)
    if data is None:
        abort(400, description="Payload JSON é obrigatório.")
    return data


def _require_fields(payload: Dict[str, Any], required_fields: List[str]) -> None:
    missing = [field for field in required_fields if field not in payload or payload[field] in (None, "")]
    if missing:
        abort(400, description=f"Campos obrigatórios ausentes: {', '.join(missing)}")


@api.delete("/ground-truth/<int:pattern_id>")
def api_delete_ground_truth(pattern_id: int):
    dao = _get_dao()
    removed = dao.delete_ground_truth_pattern(pattern_id)
    if not removed:
        abort(404, description="Padrão não encontrado.")
    return jsonify({"deleted": True})


app.register_blueprint(api)

if __name__ == "__main__":
    app.run(debug=True, threaded=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
