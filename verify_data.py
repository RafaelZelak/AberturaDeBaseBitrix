import os
import json
import requests
import time
from dotenv import load_dotenv

# Carregar variáveis do arquivo .env
load_dotenv()

# Caminho para a pasta de cache
CACHE_DIR = 'cache'

# Configurações da API do Bitrix
BITRIX_WEBHOOK_URL = os.getenv('BITRIX_WEBHOOK_URL')

# Mapeamento de IDs para sistemas
SYSTEM_MAPPING = {
    "233": "Acessórias",
    "237": "Sittax",
    "235": "Acessórias + KOMUNIC",
    "655": "Sittax / Acessórias",
    "699": "Sittax /Acessórias + KOMUNIC",
    "701": "Best Doctor"
}

# Mapeamento de modeloDeContrato para entityTypeId e outras configurações
MODELO_CONTRATO_CONFIG = {
    "Sittax - Simples Nacional": {"entityTypeId": 158, "system_id": "237"},
    "Openix - Sittax SN": {"entityTypeId": 158, "system_id": "237"},
    "Best Doctors": {"entityTypeId": 180, "system_id": "701"},
    "Acessórias": {"entityTypeId": 187, "system_id": "233"},
    "Acessórias + Komunic": {"entityTypeId": 187, "system_id": "235"}
}

def load_cache(hash):
    """Carrega o cache específico com base no hash fornecido."""
    cache_path = os.path.join(CACHE_DIR, f"{hash}.json")

    if not os.path.exists(cache_path):
        print(f"Cache {hash}.json não encontrado.")
        return None, None

    with open(cache_path, 'r') as f:
        data = json.load(f)

    print(f"Cache {hash}.json carregado.")
    return data, cache_path

def bitrix_api_call(method, params, max_retries=5, delay=2):
    """Faz uma chamada à API do Bitrix e retorna o resultado."""
    url = f"{BITRIX_WEBHOOK_URL}{method}.json"
    retries = 0

    while retries < max_retries:
        response = requests.post(url, json=params)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 503 and "QUERY_LIMIT_EXCEEDED" in response.text:
            print(f"Erro na API Bitrix: {response.status_code} - {response.text}. Tentando novamente em {delay} segundos...")
            retries += 1
            time.sleep(delay)
        else:
            print(f"Erro na API Bitrix: {response.status_code} - {response.text}")
            return None

    print(f"Número máximo de tentativas ({max_retries}) atingido.")
    return None

def check_company_system_affiliation(cnpj, expected_system_id):
    """
    Verifica se a empresa no Bitrix24 está associada ao sistema esperado.

    Parâmetros:
        cnpj (str): O CNPJ da empresa.
        expected_system_id (str): O ID do sistema esperado (ex: "237" para Sittax).

    Retorno:
        bool: True se o sistema corresponder, False caso contrário.
        str: O sistema atual da empresa.
    """
    company_response = check_company_in_bitrix(cnpj)
    if not company_response or "result" not in company_response or not company_response["result"]:
        print("Empresa não encontrada no Bitrix24.")
        return False, None

    company_data = company_response["result"][0]
    current_system_id = company_data.get("UF_CRM_1708446996746", "")

    # Verifica se o sistema atual corresponde ao esperado
    if str(current_system_id) == str(expected_system_id):
        return True, SYSTEM_MAPPING.get(current_system_id, "Desconhecido")
    else:
        return False, SYSTEM_MAPPING.get(current_system_id, "Desconhecido")

def check_company_in_bitrix(cnpj):
    """Verifica se a empresa já está cadastrada no Bitrix pelo CNPJ."""
    params = {
        "filter": {"UF_CRM_1701275490640": cnpj},
        "select": ["ID", "UF_CRM_1701275490640", "UF_CRM_1708446996746"]
    }
    return bitrix_api_call("crm.company.list", params)

def check_system_affiliation(company_data, system_id):
    """Verifica se a empresa está afiliada a um sistema específico com base no campo personalizado."""
    custom_field = company_data.get("UF_CRM_1708446996746", "")

    # Verifica se o campo contém o ID do sistema
    if isinstance(custom_field, str) and system_id in custom_field:
        return True
    elif isinstance(custom_field, list) and system_id in custom_field:
        return True

    return False

def check_system_affiliation_from_cache(hash, modelo_contrato):
    """
    Verifica a afiliação da empresa com base no cache específico (hash) e retorna True ou False.

    Parâmetros:
        hash (str): O hash do arquivo de cache a ser verificado.
        modelo_contrato (str): O modelo de contrato da empresa.

    Retorno:
        bool: True se a empresa estiver afiliada ao sistema, False caso contrário.
    """
    cache_data, cache_path = load_cache(hash)
    if not cache_data:
        return False

    if modelo_contrato not in MODELO_CONTRATO_CONFIG:
        print(f"Modelo de Contrato inválido: {modelo_contrato}")
        return False

    sistema_esperado = MODELO_CONTRATO_CONFIG[modelo_contrato]["system_id"]
    modelo_contrato_cache = cache_data.get("modeloDeContrato", "")
    if sistema_esperado not in modelo_contrato_cache:
        print(f"Modelo de Contrato não é '{SYSTEM_MAPPING[sistema_esperado]}'")
        print(f"Modelo do contrato -> {modelo_contrato_cache}")
        return False

    print(f"Modelo de Contrato contém ({modelo_contrato_cache})")

    cnpj = cache_data.get("cnpj")
    if not cnpj:
        print("CNPJ não encontrado no cache.")
        return False

    company_response = check_company_in_bitrix(cnpj)
    if not company_response or "result" not in company_response or not company_response["result"]:
        print("Empresa não encontrada no Bitrix.")
        return False

    company_data = company_response["result"][0]
    company_id = company_data.get("ID")
    company_cnpj = company_data.get("UF_CRM_1701275490640", "").strip()
    company_code = company_data.get("UF_CRM_1708446996746", "").strip()
    company_is = SYSTEM_MAPPING.get(company_code, "Outro")

    print(f"Empresa encontrada no Bitrix: ID {company_id}, CNPJ {company_cnpj}")

    if check_system_affiliation(company_data, sistema_esperado):
        print(f"Empresa afiliada ao sistema {SYSTEM_MAPPING[sistema_esperado]}.")
        return True
    else:
        print(f"Empresa pertence a {company_is}")
        return False

def check_card_exists(company_id):
    """
    Verifica se já existe um card associado a uma empresa no Bitrix24.
    Retorna o ID do primeiro card encontrado, ou None caso contrário.
    """
    params = {
        "filter": {"companyId": company_id},  # Filtra cards vinculados à empresa
        "select": ["id"]
    }
    response = bitrix_api_call("crm.item.list", params)

    if response and "result" in response and "items" in response["result"]:
        items = response["result"]["items"]
        card_ids = [str(item["id"]) for item in items if "id" in item]  # Captura os IDs dos cards existentes

        if card_ids:
            print(f"✅ Cards encontrados para a empresa ID {company_id}: {card_ids}")
            return card_ids[0]  # Retorna o primeiro card encontrado como string

    print(f"❌ Nenhum card encontrado para a empresa ID {company_id}.")
    return None  # Nenhum card encontrado

def check_existing_card_in_spa(company_id, entity_type_id, bitrix_webhook_url):
    """
    Verifica se existe um card vinculado à empresa em um SPA específico.

    :param company_id: ID da empresa no Bitrix24.
    :param entity_type_id: ID do SPA onde procurar (Sittax = 158, Acessórias = 187).
    :param bitrix_webhook_url: URL do webhook do Bitrix24.
    :return: ID do card encontrado, ou None se não houver nenhum card.
    """
    params = {
        "entityTypeId": entity_type_id,
        "filter": {"companyId": company_id},  # Filtro direto pelo ID da empresa
        "select": ["id"]
    }

    response = bitrix_api_call("crm.item.list", params)

    if response and "result" in response and "items" in response["result"]:
        items = response["result"]["items"]
        if items:
            card_id = str(items[0]["id"])  # Pega o primeiro card encontrado
            print(f"✅ Card encontrado para empresa ID {company_id} no SPA {entity_type_id}: {card_id}")
            return card_id

    print(f"❌ Nenhum card encontrado para empresa ID {company_id} no SPA {entity_type_id}.")
    return None  # Nenhum card encontrado
