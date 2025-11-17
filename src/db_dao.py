import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Optional, Sequence

try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    mysql = None  # type: ignore[assignment]
    MySQLError = Exception  # type: ignore[assignment]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SQLITE_PATH = (PROJECT_ROOT / "data" / "remote_lab.sqlite3").resolve()


class RemoteLaboratoryDAO:
    def __init__(self) -> None:
        self.db_backend = os.environ.get("DB_BACKEND", "mysql").lower()
        if self.db_backend == "mysql" and mysql is None:
            raise ImportError(
                "mysql-connector-python não está instalado. "
                "Instale-o ou defina DB_BACKEND=sqlite."
            )
        self.mysql_config = {
            "host": os.environ.get("MYSQL_HOST", "localhost"),
            "database": os.environ.get("MYSQL_DATABASE", "cae_dr"),
            "user": os.environ.get("MYSQL_USER", "root"),
            "password": os.environ.get("MYSQL_PASSWORD", ""),
        }
        sqlite_path = os.environ.get("SQLITE_DB_PATH")
        self.sqlite_path = self._resolve_sqlite_path(sqlite_path)
        self._db_errors = (MySQLError, sqlite3.Error)
        if self.db_backend == "sqlite":
            self._prepare_sqlite_backend()

    def _resolve_sqlite_path(self, custom_path: Optional[str]) -> Path:
        path = Path(custom_path).expanduser() if custom_path else DEFAULT_SQLITE_PATH
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path

    def _prepare_sqlite_backend(self) -> None:
        try:
            self._ensure_sqlite_dir()
        except OSError as exc:
            print(
                f"Não foi possível criar o diretório para {self.sqlite_path}: {exc}. "
                f"Usando caminho padrão {DEFAULT_SQLITE_PATH}."
            )
            self.sqlite_path = DEFAULT_SQLITE_PATH
            self._ensure_sqlite_dir()
        self._ensure_sqlite_schema()

    def _ensure_sqlite_dir(self) -> None:
        if self.db_backend == "sqlite":
            self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    def _ensure_sqlite_schema(self) -> None:
        """Create minimal tables needed for the Flask UI quando se usa SQLite."""
        conn = sqlite3.connect(self.sqlite_path)
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS plant_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    experiment_name TEXT NOT NULL UNIQUE,
                    ip_profinet TEXT NOT NULL,
                    rack_profinet INTEGER NOT NULL,
                    slot_profinet INTEGER NOT NULL,
                    db_number_profinet INTEGER NOT NULL,
                    num_of_inputs INTEGER NOT NULL,
                    num_of_outputs INTEGER NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def _prepare_query(self, query: str) -> str:
        if self.db_backend == "sqlite":
            return query.replace("%s", "?")
        return query

    def _execute(self, cursor, query: str, params: Optional[Sequence[Any]] = None) -> None:
        query = self._prepare_query(query)
        if params is None:
            cursor.execute(query)
        else:
            cursor.execute(query, params)

    def _dict_row(self, row):
        if row is None:
            return None
        if self.db_backend == "sqlite":
            return dict(row)
        return row

    def _dict_rows(self, rows):
        if rows is None:
            return []
        if self.db_backend == "sqlite":
            return [dict(row) for row in rows]
        return rows

    def get_banco(self):
        try:
            if self.db_backend == "sqlite":
                self._ensure_sqlite_dir()
                conn = sqlite3.connect(self.sqlite_path)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA foreign_keys = ON")
                return conn
            return mysql.connector.connect(**self.mysql_config)
        except self._db_errors as e:
            print("Erro ao acessar o banco de dados:", e)

    def get_verificacao_foto(self) -> int:
        mydb = None
        cursor = None
        try:
            mydb = self.get_banco()
            cursor = mydb.cursor()
            comando = 'SELECT State FROM variablesofsystem WHERE `Function` = "cameraControl"'
            self._execute(cursor, comando)
            result = cursor.fetchone()
            return result[0] if result else None
        except self._db_errors as e:
            print("Erro ao acessar a tabela: \n", e)
        finally:
            if cursor:
                cursor.close()
            if mydb:
                mydb.close()

    def insert_data_into_database(self, experiment_number, step, pulse_train, pulse_value, time_to_change, experiment_name):
        mydb = None
        mycursor = None
        try:
            mydb = self.get_banco()
            mycursor = mydb.cursor()
            step_json = json.dumps(step)
            sql = (
                "INSERT INTO dadoscoletados2 "
                "(experiment_id, step, pulse_train, pulse_value, experimentName, timeToChange) "
                "VALUES (%s, %s, %s, %s, %s, %s)"
            )
            self._execute(
                mycursor,
                sql,
                (experiment_number, step_json, pulse_train, pulse_value, experiment_name, time_to_change),
            )
            mydb.commit()
        except self._db_errors as e:
            print(f"Erro ao tentar inserir os dados no banco de dados: \n {e}")
        finally:
            if mycursor:
                mycursor.close()
            if mydb:
                mydb.close()

    def get_last_experiment_id(self):
        mydb = None
        cursor = None
        try:
            mydb = self.get_banco()
            cursor = mydb.cursor()
            sql = "SELECT MAX(experiment_id) FROM dadoscoletados2"
            self._execute(cursor, sql)
            result = cursor.fetchone()
            return result[0] if result and result[0] is not None else None
        except self._db_errors as e:
            print("Erro ao acessar a tabela:", e)
            return None
        finally:
            if cursor:
                cursor.close()
            if mydb:
                mydb.close()

    def get_pulse_values_by_experiment(self, experiment_id):
        mydb = None
        cursor = None
        try:
            mydb = self.get_banco()
            cursor = mydb.cursor()
            sql = "SELECT pulse_value FROM dadoscoletados2 WHERE experiment_id = %s ORDER BY step ASC"
            self._execute(cursor, sql, (experiment_id,))
            results = cursor.fetchall()
            return [row[0] for row in results] if results else []
        except self._db_errors as e:
            print("Erro ao acessar a tabela:", e)
            return []
        finally:
            if cursor:
                cursor.close()
            if mydb:
                mydb.close()

    def insert_pattern(self, experiment_id, pattern):
        mydb = None
        cursor = None
        try:
            mydb = self.get_banco()
            cursor = mydb.cursor()
            sql = "INSERT INTO dadoscoletados_summary (experiment_id, pattern) VALUES (%s, %s);"
            self._execute(cursor, sql, (experiment_id, pattern))
            mydb.commit()
        except self._db_errors as e:
            print("Erro ao inserir o padrão na tabela:", e)
        finally:
            if cursor:
                cursor.close()
            if mydb:
                mydb.close()

    def get_patterns_by_experiment(self, experiment_id):
        mydb = None
        cursor = None
        try:
            mydb = self.get_banco()
            cursor = mydb.cursor()
            sql = "SELECT pattern FROM dadoscoletados_summary WHERE experiment_id = %s ORDER BY id DESC"
            self._execute(cursor, sql, (experiment_id,))
            results = cursor.fetchall()
            return results[0][0] if results else None
        except self._db_errors as e:
            print("Erro ao acessar a tabela:", e)
            return []
        finally:
            if cursor:
                cursor.close()
            if mydb:
                mydb.close()

    def get_plant_config(self, experiment_name: str):
        mydb = None
        cursor = None
        try:
            mydb = self.get_banco()
            if self.db_backend == "sqlite":
                cursor = mydb.cursor()
            else:
                cursor = mydb.cursor(dictionary=True)
            sql = "SELECT * FROM plant_config WHERE experiment_name = %s"
            self._execute(cursor, sql, (experiment_name,))
            config = cursor.fetchone()
            config = self._dict_row(config)
            if config is None:
                raise ValueError(f"Configuração para experimento '{experiment_name}' não encontrada")
            return config
        except self._db_errors as e:
            print(f"Erro ao buscar configuração do experimento: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
            if mydb:
                mydb.close()

    def list_plant_configs(self):
        mydb = None
        cursor = None
        try:
            mydb = self.get_banco()
            cursor = mydb.cursor()
            self._execute(cursor, "SELECT experiment_name FROM plant_config ORDER BY experiment_name ASC")
            plants = cursor.fetchall()
            return [p[0] for p in plants]
        except self._db_errors as e:
            print(f"Erro ao buscar plantas no banco: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
            if mydb:
                mydb.close()

    def list_full_plant_configs(self):
        mydb = None
        cursor = None
        try:
            mydb = self.get_banco()
            if self.db_backend == "sqlite":
                cursor = mydb.cursor()
            else:
                cursor = mydb.cursor(dictionary=True)
            self._execute(
                cursor,
                """
                SELECT id, experiment_name, ip_profinet, rack_profinet, slot_profinet,
                       db_number_profinet, num_of_inputs, num_of_outputs
                FROM plant_config
                ORDER BY experiment_name ASC
                """
            )
            rows = cursor.fetchall()
            return self._dict_rows(rows)
        except self._db_errors as e:
            print(f"Erro ao buscar as plantas no banco: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
            if mydb:
                mydb.close()

    def get_plant_config_by_id(self, config_id: int):
        mydb = None
        cursor = None
        try:
            mydb = self.get_banco()
            if self.db_backend == "sqlite":
                cursor = mydb.cursor()
            else:
                cursor = mydb.cursor(dictionary=True)
            self._execute(cursor, "SELECT * FROM plant_config WHERE id = %s", (config_id,))
            row = cursor.fetchone()
            return self._dict_row(row)
        except self._db_errors as e:
            print(f"Erro ao buscar a configuração: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
            if mydb:
                mydb.close()

    def create_plant_config(
        self,
        experiment_name,
        ip_profinet,
        rack_profinet,
        slot_profinet,
        db_number_profinet,
        num_inputs,
        num_outputs,
    ):
        mydb = None
        cursor = None
        try:
            mydb = self.get_banco()
            cursor = mydb.cursor()
            self._execute(
                cursor,
                """
                INSERT INTO plant_config
                (experiment_name, ip_profinet, rack_profinet, slot_profinet,
                 db_number_profinet, num_of_inputs, num_of_outputs)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    experiment_name,
                    ip_profinet,
                    rack_profinet,
                    slot_profinet,
                    db_number_profinet,
                    num_inputs,
                    num_outputs,
                ),
            )
            mydb.commit()
            return cursor.lastrowid
        except self._db_errors as e:
            print(f"Erro ao criar a configuração da planta: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
            if mydb:
                mydb.close()

    def update_plant_config(
        self,
        config_id,
        experiment_name,
        ip_profinet,
        rack_profinet,
        slot_profinet,
        db_number_profinet,
        num_inputs,
        num_outputs,
    ):
        mydb = None
        cursor = None
        try:
            mydb = self.get_banco()
            cursor = mydb.cursor()
            self._execute(
                cursor,
                """
                UPDATE plant_config
                SET experiment_name=%s,
                    ip_profinet=%s,
                    rack_profinet=%s,
                    slot_profinet=%s,
                    db_number_profinet=%s,
                    num_of_inputs=%s,
                    num_of_outputs=%s
                WHERE id=%s
                """,
                (
                    experiment_name,
                    ip_profinet,
                    rack_profinet,
                    slot_profinet,
                    db_number_profinet,
                    num_inputs,
                    num_outputs,
                    config_id,
                ),
            )
            mydb.commit()
            return cursor.rowcount
        except self._db_errors as e:
            print(f"Erro ao atualizar a configuração da planta: {e}")
            return 0
        finally:
            if cursor:
                cursor.close()
            if mydb:
                mydb.close()

    def delete_plant_config(self, config_id: int) -> bool:
        mydb = None
        cursor = None
        try:
            mydb = self.get_banco()
            cursor = mydb.cursor()
            self._execute(cursor, "DELETE FROM plant_config WHERE id = %s", (config_id,))
            mydb.commit()
            return cursor.rowcount > 0
        except self._db_errors as e:
            print(f"Erro ao deletar a configuração: {e}")
            return False
        finally:
            if cursor:
                cursor.close()
            if mydb:
                mydb.close()

    def insert_data_with_duration(
        self,
        experiment_number,
        step,
        pulse_train,
        pulse_value,
        time_to_change,
        experiment_name,
        duration,
    ):
        mydb = None
        mycursor = None
        try:
            mydb = self.get_banco()
            mycursor = mydb.cursor()
            step_json = json.dumps(step)
            sql = (
                "INSERT INTO dadoscoletados2 "
                "(experiment_id, step, pulse_train, pulse_value, experimentName, timeToChange, duration) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)"
            )
            self._execute(
                mycursor,
                sql,
                (
                    experiment_number,
                    step_json,
                    pulse_train,
                    pulse_value,
                    experiment_name,
                    time_to_change,
                    duration,
                ),
            )
            mydb.commit()
        except self._db_errors as e:
            print(f"Erro ao tentar inserir os dados no banco de dados: \n {e}")
        finally:
            if mycursor:
                mycursor.close()
            if mydb:
                mydb.close()
