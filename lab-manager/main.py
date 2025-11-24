import json
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
    return render_template(
        "ground_truth/index.html",
        patterns=patterns,
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


@app.post("/chatbot/ask")
def chatbot_ask():
    data = request.get_json(silent=True) or {}
    user_input = (data.get("message") or "").strip()
    if not user_input:
        return jsonify({"error": "A mensagem não pode ser vazia."}), 400
    history_payload = data.get("history") or []
    try:
        history = _parse_history(history_payload)
    except Exception:
        return jsonify({"error": "Histórico de mensagens inválido."}), 400

    try:
        agent = _build_chat_agent()
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        result = agent.invoke({"messages": [*history, HumanMessage(content=user_input)]})
    except httpx.HTTPError as exc:
        return jsonify({"error": f"Erro ao acessar a API: {exc}"}), 502
    except Exception as exc:
        return jsonify({"error": f"Erro ao executar o chatbot: {exc}"}), 500

    messages = result["messages"]
    reply = _last_ai_message(messages)
    return jsonify({"reply": reply, "history": _serialize_messages(messages)})


@api.get("/experiments")
def api_list_experiments():
    dao = _get_dao()
    return jsonify(dao.list_full_plant_configs())


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


@api.delete("/ground-truth/<int:pattern_id>")
def api_delete_ground_truth(pattern_id: int):
    dao = _get_dao()
    removed = dao.delete_ground_truth_pattern(pattern_id)
    if not removed:
        abort(404, description="Padrão não encontrado.")
    return jsonify({"deleted": True})


app.register_blueprint(api)

if __name__ == "__main__":
    app.run(debug=True, threaded=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5001)))


def _json_payload():
    data = request.get_json(silent=True)
    if data is None:
        abort(400, description="Payload JSON é obrigatório.")
    return data


def _require_fields(payload: Dict[str, Any], required_fields: List[str]) -> None:
    missing = [field for field in required_fields if field not in payload or payload[field] in (None, "")]
    if missing:
        abort(400, description=f"Campos obrigatórios ausentes: {', '.join(missing)}")
