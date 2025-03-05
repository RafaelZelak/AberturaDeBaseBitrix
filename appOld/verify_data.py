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

def load_cache(hash):
    """Carrega o cache específico com base no hash fornecido."""
    cache_path = os.path.join(CACHE_DIR, f"{hash}.json")

    if not os.path.exists(cache_path):
        print(f"Cache {hash}.json não encontrado.")
        return None, None

    with open(cache_path, 'r') as f:
        data = json.load(f)

    print(f"Cache {hash}.json carregado.")
    return data, cache_path  # Retorna o caminho para deletar depois

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

def check_company_in_bitrix(cnpj):
    """Verifica se a empresa já está cadastrada no Bitrix pelo CNPJ."""
    params = {
        "filter": {"UF_CRM_1701275490640": cnpj},
        "select": ["ID", "UF_CRM_1701275490640", "UF_CRM_1708446996746"]  # CNPJ e campo personalizado
    }
    return bitrix_api_call("crm.company.list", params)

def check_sittax_affiliation(company_data):
    """Verifica se a empresa está afiliada à Sittax com base no campo personalizado."""
    custom_field = company_data.get("UF_CRM_1708446996746", "")

    # Verifica se o campo contém o ID da Sittax (237)
    if isinstance(custom_field, str) and "237" in custom_field:
        return True
    elif isinstance(custom_field, list) and "237" in custom_field:
        return True

    return False

def check_sittax_affiliation_from_cache(hash):
    """
    Verifica a afiliação da Sittax com base no cache específico (hash) e retorna True ou False.

    Parâmetros:
        hash (str): O hash do arquivo de cache a ser verificado.

    Retorno:
        bool: True se a empresa estiver afiliada à Sittax, False caso contrário.
    """
    # Carregar o cache específico com base no hash
    cache_data, cache_path = load_cache(hash)
    if not cache_data:
        return False

    # Verificar se o modelo de contrato contém "Sittax"
    modelo_contrato = cache_data.get("modeloDeContrato", "")
    if "Sittax" not in modelo_contrato:
        print("Modelo de Contrato não é 'Sittax'")
        print(f"Modelo do contrato -> {modelo_contrato}")
        return False

    print(f"Modelo de Contrato contém ({modelo_contrato})")

    # Verificar se a empresa já está cadastrada no Bitrix
    cnpj = cache_data.get("cnpj")
    if not cnpj:
        print("CNPJ não encontrado no cache.")
        return False

    # Buscar empresa no Bitrix pelo CNPJ
    company_response = check_company_in_bitrix(cnpj)
    if not company_response or "result" not in company_response or not company_response["result"]:
        print("Empresa não encontrada no Bitrix.")
        return False

    # Pegar os dados da primeira empresa encontrada
    company_data = company_response["result"][0]
    company_id = company_data.get("ID")
    company_cnpj = company_data.get("UF_CRM_1701275490640", "").strip()
    company_code = company_data.get("UF_CRM_1708446996746", "").strip()
    company_is = SYSTEM_MAPPING.get(company_code, "Outro")

    print(f"Empresa encontrada no Bitrix: ID {company_id}, CNPJ {company_cnpj}")

    # Verificar se a empresa está afiliada à Sittax
    if check_sittax_affiliation(company_data):
        print("Empresa afiliada à Sittax.")
        return True
    else:
        print(f"Empresa pertence a {company_is}")
        return False