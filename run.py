import os
import json

from create_sittax import create_comp_and_card_sittax
from create_acessorias import create_comp_and_card_acessorias
from fetch_emails import process_emails

process_emails()
# Função para carregar logs existentes ou criar um novo arquivo de logs
def load_logs(log_file='logs.json'):
    if os.path.exists(log_file):
        with open(log_file, 'r', encoding='utf-8') as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                return []
    return []

# Função para salvar logs
def save_logs(logs, log_file='logs.json'):
    with open(log_file, 'w', encoding='utf-8') as file:
        json.dump(logs, file, ensure_ascii=False, indent=4)

# Função para processar os arquivos JSON
def process_json_files(cache_dir='cache/'):
    logs = load_logs()

    for filename in os.listdir(cache_dir):
        if filename.endswith('.json'):
            file_path = os.path.join(cache_dir, filename)
            with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)

                modelo = data.get('modeloDeContrato', '').strip()
                hash_name = filename[:-5]

                if modelo in ["Acessórias", "Acessórias + Komunic"]:
                    create_comp_and_card_acessorias(hash_name)
                elif modelo in ["Openix - Sittax SN", "Sittax - Simples Nacional"]:
                    create_comp_and_card_sittax(hash_name)
                else:
                    logs.append(data)
    save_logs(logs)

if __name__ == "__main__":
    process_json_files()