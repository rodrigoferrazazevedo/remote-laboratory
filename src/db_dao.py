import mysql.connector
from mysql.connector import Error
import json

class RemoteLaboratoryDAO:
    
    def __init__(self) -> None:
        pass

    def get_banco(self):

        try:

            mydb = mysql.connector.connect(
                host='localhost',
                database='cae_dr',
                user='root',
                password='')

            return mydb

        except mysql.connector.Error as e:

            print("Erro ao acessar o banco de dados:", e)

    def get_verificacao_foto(self) -> int:
        
        try:

            mydb = self.get_banco()
            cursor = mydb.cursor()

            comando = 'SELECT State FROM cae_dr.variablesofsystem WHERE `Function` = "cameraControl"'

            cursor.execute(comando)
            result = cursor.fetchone()

            return result[0] if result else None
        
        except mysql.connector.Error as e:

            print("Erro ao acessar a tabela: \n", e)



    def insert_data_into_database(self, experiment_number, step, pulse_train, pulse_value, time_to_change, experiment_name):
        try:
            mydb = self.get_banco()
            mycursor = mydb.cursor()
            
            # Converta o step (lista) para JSON para salvar como string no banco
            step_json = json.dumps(step)
            
            sql = '''
                INSERT INTO `cae_dr`.`dadoscoletados2` 
                (experiment_id, step, pulse_train, pulse_value, experimentName, timeToChange)
                VALUES (%s, %s, %s, %s, %s, %s)
            '''
            
            mycursor.execute(sql, (experiment_number, step_json, pulse_train, pulse_value, experiment_name, time_to_change))
            mydb.commit()
        except Error as e:
            print(f"Erro ao tentar inserir os dados no banco de dados: \n {e}")
        finally:
            mydb.close()

    # def insert_data_into_database(self,experiment_number, step, pulse_train, pulse_value, time_to_change, experiment_name):
        
    #     sql = f'INSERT INTO `cae_dr`.`dadoscoletados2` ( `experiment_id`,`step`, `pulse_train`, `pulse_value`, `experimentName`, `timeToChange`) VALUES ({experiment_number}, {step}, "{pulse_train}", {pulse_value}, "{experiment_name}", "{time_to_change}");'
        
    #     try:

    #         mydb = self.get_banco()

    #         mycursor = mydb.cursor()

    #         mycursor.execute(sql)

    #         mydb.commit()      

    #     except Error as e:
            
    #         print(f"Erro ao tentar inserir os dados no banco de dados: \n {e}")

    #     finally:
            
    #         mydb.close()


    def get_last_experiment_id(self):
        try:
            mydb = self.get_banco()
            cursor = mydb.cursor()

            sql = "SELECT MAX(experiment_id) FROM dadoscoletados2"
            cursor.execute(sql)

            result = cursor.fetchone()

            return result[0] if result[0] is not None else None

        except mysql.connector.Error as e:
            print("Erro ao acessar a tabela:", e)
            return None

        finally:
            
            if mydb.is_connected():
                cursor.close()
                mydb.close()

    def get_pulse_values_by_experiment(self, experiment_id):

        try:
            mydb = self.get_banco()
            cursor = mydb.cursor()

            sql = "SELECT pulse_value FROM dadoscoletados2 WHERE experiment_id = %s ORDER BY step ASC"
            cursor.execute(sql, (experiment_id,))

            results = cursor.fetchall()

            pulse_values = [row[0] for row in results]

            return pulse_values

        except mysql.connector.Error as e:
            print("Erro ao acessar a tabela:", e)
            return []

        finally:
            if mydb.is_connected():
                cursor.close()
                mydb.close()


    def insert_pattern(self, experiment_id, pattern):
        try:
            mydb = self.get_banco()
            cursor = mydb.cursor()

            sql = """
            INSERT INTO dadoscoletados_summary (experiment_id, pattern)
            VALUES (%s, %s);
            """

            cursor.execute(sql, (experiment_id, pattern))

            mydb.commit()

        except mysql.connector.Error as e:
            print("Erro ao inserir o padrão na tabela:", e)

        finally:
            if mydb.is_connected():
                cursor.close()
                mydb.close()

    def get_patterns_by_experiment(self, experiment_id):

        try:
            mydb = self.get_banco()
            cursor = mydb.cursor()

            sql = "SELECT pattern FROM dadoscoletados_summary WHERE experiment_id = %s ORDER BY id DESC"
            cursor.execute(sql, (experiment_id,))

            results = cursor.fetchall()

            patterns = [row[0] for row in results]

            return patterns[0]

        except mysql.connector.Error as e:
            print("Erro ao acessar a tabela:", e)
            return []

        finally:

            if mydb.is_connected():
                
                cursor.close()
                mydb.close()


    def get_plant_config(self, experiment_name: str):
        try:
            mydb = mysql.connector.connect(
                host='localhost',
                database='cae_dr',
                user='root',
                password=''
            )
            cursor = mydb.cursor(dictionary=True)
            sql = "SELECT * FROM plant_config WHERE experiment_name = %s"
            cursor.execute(sql, (experiment_name,))
            config = cursor.fetchone()
            cursor.close()
            mydb.close()
            if config is None:
                raise ValueError(f"Configuração para experimento '{experiment_name}' não encontrada")
            return config
        except Exception as e:
            print(f"Erro ao buscar configuração do experimento: {e}")
            return None

    def list_plant_configs(self):
        try:
            mydb = mysql.connector.connect(
                host='localhost',
                database='cae_dr',
                user='root',
                password=''
            )
            cursor = mydb.cursor()
            cursor.execute("SELECT experiment_name FROM plant_config ORDER BY experiment_name ASC")
            plants = cursor.fetchall()
            cursor.close()
            mydb.close()
            return [p[0] for p in plants]
        except Exception as e:
            print(f"Erro ao buscar plantas no banco: {e}")
            return []

    def list_full_plant_configs(self):
        mydb = None
        cursor = None
        try:
            mydb = self.get_banco()
            cursor = mydb.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT id, experiment_name, ip_profinet, rack_profinet, slot_profinet,
                       db_number_profinet, num_of_inputs, num_of_outputs
                FROM plant_config
                ORDER BY experiment_name ASC
                """
            )
            return cursor.fetchall()
        except mysql.connector.Error as e:
            print(f"Erro ao buscar as plantas no banco: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
            if mydb and mydb.is_connected():
                mydb.close()

    def get_plant_config_by_id(self, config_id: int):
        mydb = None
        cursor = None
        try:
            mydb = self.get_banco()
            cursor = mydb.cursor(dictionary=True)
            cursor.execute(
                "SELECT * FROM plant_config WHERE id = %s",
                (config_id,)
            )
            return cursor.fetchone()
        except mysql.connector.Error as e:
            print(f"Erro ao buscar a configuração: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
            if mydb and mydb.is_connected():
                mydb.close()

    def create_plant_config(self, experiment_name, ip_profinet, rack_profinet,
                             slot_profinet, db_number_profinet, num_inputs, num_outputs):
        mydb = None
        cursor = None
        try:
            mydb = self.get_banco()
            cursor = mydb.cursor()
            cursor.execute(
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
                    num_outputs
                )
            )
            mydb.commit()
            return cursor.lastrowid
        except mysql.connector.Error as e:
            print(f"Erro ao criar a configuração da planta: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
            if mydb and mydb.is_connected():
                mydb.close()

    def update_plant_config(self, config_id, experiment_name, ip_profinet,
                             rack_profinet, slot_profinet, db_number_profinet,
                             num_inputs, num_outputs):
        mydb = None
        cursor = None
        try:
            mydb = self.get_banco()
            cursor = mydb.cursor()
            cursor.execute(
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
                )
            )
            mydb.commit()
            return cursor.rowcount
        except mysql.connector.Error as e:
            print(f"Erro ao atualizar a configuração da planta: {e}")
            return 0
        finally:
            if cursor:
                cursor.close()
            if mydb and mydb.is_connected():
                mydb.close()

    def delete_plant_config(self, config_id: int) -> bool:
        mydb = None
        cursor = None
        try:
            mydb = self.get_banco()
            cursor = mydb.cursor()
            cursor.execute("DELETE FROM plant_config WHERE id = %s", (config_id,))
            mydb.commit()
            return cursor.rowcount > 0
        except mysql.connector.Error as e:
            print(f"Erro ao deletar a configuração: {e}")
            return False
        finally:
            if cursor:
                cursor.close()
            if mydb and mydb.is_connected():
                mydb.close()
        
    def insert_data_with_duration(self, experiment_number, step, pulse_train, pulse_value, time_to_change, experiment_name, duration):
        try:
            mydb = self.get_banco()
            mycursor = mydb.cursor()

            step_json = json.dumps(step)
            
            sql = '''
                INSERT INTO dadoscoletados2 
                (experiment_id, step, pulse_train, pulse_value, experimentName, timeToChange, duration) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            '''
            mycursor.execute(sql, (experiment_number, step_json, pulse_train, pulse_value, experiment_name, time_to_change, duration))
            mydb.commit()
        except Error as e:
            print(f"Erro ao tentar inserir os dados no banco de dados: \n {e}")
        finally:
            mydb.close()

    # teste = RemoteLaboratoryDAO()


