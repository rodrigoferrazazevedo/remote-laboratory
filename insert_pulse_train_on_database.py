from src.db_dao import RemoteLaboratoryDAO

banco = RemoteLaboratoryDAO()
    
last_experiment_id = banco.get_last_experiment_id()  # Pegando o último experimento realizado
# last_experiment_id = 35
# Coletando uma lista de pulse_train do último experimento
pulse_trains = banco.get_pulse_values_by_experiment(last_experiment_id)

print('Trens de pulsos para serem cadastrados: \n')
pulse_trains_str = "[" + ",".join(map(str, pulse_trains)) + "]"
print(pulse_trains_str)

experiment_number = banco.get_last_experiment_id()

banco.insert_pattern(experiment_number, pulse_trains_str)        
print('Trem de pulso inserido no banco!')
print('Experimento: ', experiment_number)

pulse_train_from_db = banco.get_pulse_values_by_experiment(1)
print(pulse_train_from_db)
