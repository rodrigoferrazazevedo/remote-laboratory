import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from flask import Flask, flash, redirect, render_template, request, url_for


BOT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BOT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.db_dao import RemoteLaboratoryDAO  # noqa: E402  (import after sys.path tweak)


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev")


def _get_dao() -> RemoteLaboratoryDAO:
    return RemoteLaboratoryDAO()


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


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
