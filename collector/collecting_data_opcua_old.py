from src.db_dao import RemoteLaboratoryDAO

import os
import csv
from opcua import Client
import threading
import time


def convert_data(step: list) -> int:
    
    fator_multiplicativo = 1
    resultado = 0
    
    for elemento in reversed(step):
    
        if elemento:
    
            resultado += fator_multiplicativo
    
        fator_multiplicativo *= 2
    
    return resultado

def getStep(input_values, client):
    
    step = []
    
    for opcua_name in input_values:
    
        node = client.get_node(f'ns=3;s="{opcua_name}"')
        value = node.get_value()
    
        #print(value)
    
        step.append(value)
    
    return step

def check_and_create_new_version(base_filename):
    
    version = 1
    
    txt_filename = f"{base_filename}_v{version}.txt"
    csv_filename = f"{base_filename}_v{version}.csv"
    
    while os.path.exists(txt_filename) or os.path.exists(csv_filename):
    
        version += 1
        txt_filename = f"{base_filename}_v{version}.txt"
        csv_filename = f"{base_filename}_v{version}.csv"
    
    return txt_filename, csv_filename

def save_data(experiment_number, step, input_values, cont, txt_filename, csv_filename):
    
    banco = RemoteLaboratoryDAO()
    
    timestamp = time.time()

    valor_do_passo = convert_data(step)

    banco.insert_data_into_database(experiment_number, cont, step, valor_do_passo)
    
    with open(txt_filename, 'a') as txt_file:
    
        txt_file.write(f"IOs: {input_values}\nPasso{cont}: {step} | Valor do passo: {valor_do_passo} | timestamp: {timestamp}\n")
        txt_file.flush()
    
    file_exists = os.path.isfile(csv_filename)

    with open(csv_filename, 'a', newline='') as csv_file:
        
        writer = csv.writer(csv_file)
        
        if not file_exists:
            
            writer.writerow(['Passo', 'Step', 'Valor do Passo', 'Timestamp'])

        writer.writerow([cont, step, valor_do_passo, timestamp])
    



'''  ----------- Função principal ------------ '''

def main():

    banco = RemoteLaboratoryDAO()

    server_ip = "172.21.1.1"
    input_values = ['xBG5', 'xBG6', 'xCL_   BG1', 'xCL_BG2', 'xCL_BG3', 'xCL_BG4', 'xCL_BG5', 'xCL_BG8']
    
    try:
        experiment_number = banco.get_last_experiment_id() + 1

    except:
        experiment_number = 1
    
    
    client = Client(f"opc.tcp://{server_ip}:4840")

    print('Digite o tempo que deseja coletar os dados: ')

    timeout = int(input())
    # timeout = timeout * 60    

    print('server IP: ' + server_ip)
    print('Experiment Number: ', experiment_number)
    print(f'timeout: {timeout} segundos.')

    try:

        client.connect()

    except Exception as error:

        print('Erro ao tentar se conectar com o servidor OPCUA: \n' + error + '\n\n')
        exit(1)

    print('cliente OPC-UA conectado com sucesso! \n\n')

    txt_filename, csv_filename = check_and_create_new_version('steps')

    cont = 0
    init = 0

    previous_state = []    

    while True:
    
        step = getStep(input_values, client)
        
        if step != previous_state:
            
            start_time = time.time()
            print(step)
            cont += 1
            
            thSave = threading.Thread(target = save_data, args=(experiment_number, step, input_values, cont, txt_filename, csv_filename))
            thSave.start()
    
            previous_state = step
    
        if init == 0:
    
            previous_state = step
    
            init = 1


        elapsed_time = time.time() - start_time

        print(elapsed_time)
        print(timeout)

        if elapsed_time > timeout:
            
            print(f"Tempo limite de coleta atingido ({elapsed_time:.2f} segundos). Finalizando...")
            break 

    last_experiment_id = banco.get_last_experiment_id()  # Pegando o último experimento realizado

    # Coletando uma lista de pulse_train do último experimento
    pulse_trains = banco.get_pulse_values_by_experiment(last_experiment_id)

    print('Trens de pulsos para serem cadastrados: \n')
    pulse_trains_str = "[" + ",".join(map(str, pulse_trains)) + "]"
    print(pulse_trains_str)

    #agora vou inserir no banco de dados o trem de pulso que vou enviar para o chat GPT
    try:

        banco.insert_pattern(experiment_number, pulse_trains_str)        
        print('Trem de pulso inserido no banco!')
        print('Experimento: ', experiment_number)

    except Exception as e:

        print(f"Erro ao inserir o trem de pulso no banco: {e}")

    exit(1)

if __name__ == "__main__":
    
    main()
