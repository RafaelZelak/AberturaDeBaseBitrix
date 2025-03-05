import os
import json
import requests
from datetime import datetime, timedelta
from verify_data import (
    check_system_affiliation_from_cache,
    check_company_in_bitrix,
    SYSTEM_MAPPING,
    check_company_system_affiliation
)

CACHE_DIR = "cache"
BITRIX_WEBHOOK_URL = os.getenv('BITRIX_WEBHOOK_URL')

MODELO_CONTRATO_TO_ID = {
    "Acessórias": "233",
    "Acessórias + Komunic": "235"
}

SITTAX_UPDATE_MAPPING = {
    "237": "655",  # Sittax -> Sittax/Acessórias
    "233": "655",  # Acessórias -> Sittax/Acessórias
    "235": "699"   # Acessórias + Komunic -> Sittax/Acessórias + Komunic
}

MODELO_CONTRATO_TO_UF_CRM_ID = {
    "Acessórias": "691",
    "Acessórias + Komunic": "693"
}

def clean_and_standardize_value(value):
    try:
        cleaned_value = value.split('(')[0].replace('R$', '').strip()
        cleaned_value = cleaned_value.replace('.', '').replace(',', '.')
        return f"{cleaned_value}"
    except Exception as e:
        print(f"Erro ao limpar o valor {value}: {e}")
        return None

def update_company_system_affiliation(cnpj, new_system_id):
    """
    Atualiza o campo UF_CRM_1708446996746 (sistema de afiliação) de uma empresa no Bitrix24.

    Parâmetros:
        cnpj (str): O CNPJ da empresa.
        new_system_id (str): O novo ID do sistema para o qual a empresa será atualizada.

    Retorno:
        bool: True se a atualização for bem-sucedida, False caso contrário.
    """
    company_response = check_company_in_bitrix(cnpj)
    if not company_response or "result" not in company_response or not company_response["result"]:
        print(f"Empresa com CNPJ {cnpj} não encontrada no Bitrix24.")
        return False

    company_id = company_response["result"][0].get("ID")
    if not company_id:
        print(f"ID da empresa com CNPJ {cnpj} não encontrado.")
        return False

    url = f"{BITRIX_WEBHOOK_URL}/crm.company.update"
    payload = {
        "id": company_id,
        "fields": {
            "UF_CRM_1708446996746": new_system_id
        }
    }

    response = requests.post(url, json=payload)
    if response.status_code == 200:
        print(f"Empresa com CNPJ {cnpj} atualizada para o sistema {SYSTEM_MAPPING.get(new_system_id, 'Desconhecido')}.")
        return True
    else:
        print(f"Erro ao atualizar empresa com CNPJ {cnpj}: {response.text}")
        return False

def create_company_in_bitrix(company_data):
    url = f"{BITRIX_WEBHOOK_URL}/crm.company.add"

    modelo_id = MODELO_CONTRATO_TO_ID.get(company_data.get("modeloDeContrato", ""), 233)
    uf_crm_id = MODELO_CONTRATO_TO_UF_CRM_ID.get(company_data.get("modeloDeContrato", ""), None)

    emails = [
        {"VALUE_TYPE": "WORK", "VALUE": email.strip(), "TYPE_ID": "EMAIL"}
        for email in company_data.get("emails", [])
    ]

    phones = [
        {"VALUE_TYPE": "WORK", "VALUE": phone.strip(), "TYPE_ID": "PHONE"}
        for phone in company_data.get("phones", [])
    ]

    valor_mensalidade = clean_and_standardize_value(company_data.get("valorMensalidade", ""))
    valor_licenca = clean_and_standardize_value(company_data.get("valorLicenca", ""))

    if valor_mensalidade is None or valor_licenca is None:
        print(f"Erro: Valores de mensalidade ou licença inválidos para a empresa {company_data['razaoSocial']}.")
        return None

    payload = {
        "fields": {
            "TITLE": company_data.get("razaoSocial", ""),
            "EMAIL": emails,
            "PHONE": phones,
            "UF_CRM_1701275490640": company_data.get("cnpj", ""),
            "UF_CRM_1708446996746": modelo_id,
            "UF_CRM_1727438279465": company_data.get("consultor", ""),
            "UF_CRM_1727438009508": valor_licenca,
            "UF_CRM_1727437983987": valor_mensalidade,
            "UF_CRM_1723638730243": uf_crm_id,
            "UF_CRM_1725555192239": company_data.get("diretor", "")
        }
    }

    response = requests.post(url, json=payload)
    if response.status_code == 200:
        print(f"Empresa {company_data['razaoSocial']} criada com sucesso.")
        return response.json().get("result")
    else:
        print(f"Erro ao criar empresa {company_data['razaoSocial']}: {response.text}")
        return None

def check_card_exists(company_id):
    """
    Verifica se já existe um card no CRM para a empresa, considerando apenas cards ativos.

    Parâmetros:
        company_id (str): O ID da empresa no Bitrix24.

    Retorno:
        list: Lista de IDs dos cards encontrados. Retorna uma lista vazia se nenhum card for encontrado.
    """
    url = f"{BITRIX_WEBHOOK_URL}/crm.item.list"
    payload = {
        "entityTypeId": 187,
        "filter": {
            "companyId": company_id,
            "stageId": "DT187_99:NEW",
            "categoryId": "99"
        },
        "select": ["id"]
    }

    response = requests.post(url, json=payload)
    if response.status_code == 200:
        result = response.json().get("result", {})
        print(f"Resposta da API: {result}")

        # Corrigindo o processamento do resultado
        if "items" in result and isinstance(result["items"], list):
            card_ids = [str(item["id"]) for item in result["items"]]
        else:
            card_ids = []

        print(f"Cards encontrados para a empresa ID {company_id}: {card_ids}")
        return card_ids
    else:
        print(f"Erro ao verificar cards para a empresa ID {company_id}: {response.text}")
        return []

def create_card_in_bitrix(company_data, company_id):
    url = f"{BITRIX_WEBHOOK_URL}/crm.item.add"

    valor_mensalidade = clean_and_standardize_value(company_data.get("valorMensalidade", ""))
    valor_licenca = clean_and_standardize_value(company_data.get("valorLicenca", ""))
    pacote = company_data.get("qtdCnpj", "")

    if valor_mensalidade is None or valor_licenca is None:
        print(f"❌ Erro: Valores de mensalidade ou licença inválidos para a empresa {company_data['razaoSocial']}.")
        return None

    payload = {
        "entityTypeId": 187,
        "fields": {
            "title": company_data.get("razaoSocial", ""),
            "stageId": "DT187_99:NEW",
            "categoryId": 99,
            "assignedById": 629,
            "opened": "N",
            "begindate": datetime.now().strftime("%Y-%m-%d"),
            "closedate": (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"),
            "currencyId": "BRL",
            "ufCrm25_1737492364136": company_data.get("razaoSocial", ""),
            "ufCrm25_1737656457068": company_data.get("cnpj", ""),
            "ufCrm25_1710505471575": company_data.get("emails", [])[0] if company_data.get("emails") else "",
            "ufCrm25_1710505566404": valor_mensalidade,
            "ufCrm25_1710505188682": pacote,
            "companyId": company_id
        }
    }

    response = requests.post(url, json=payload)

    if response.status_code == 200:
        print(f"✅ Card criado com sucesso para a empresa {company_data['razaoSocial']}.")
        return response.json()  # Retorna a resposta completa, incluindo o `card_id`
    else:
        print(f"❌ Erro ao criar card para a empresa {company_data['razaoSocial']}: {response.text}")
        return None

def create_comp_and_card_acessorias(hash_value):
    json_path = os.path.join(CACHE_DIR, f"{hash_value}.json")
    if not os.path.exists(json_path):
        print(f"❌ Arquivo JSON para o hash {hash_value} não encontrado.")
        return None

    with open(json_path, 'r', encoding='utf-8') as file:
        company_data = json.load(file)

    modelo_contrato = company_data.get("modeloDeContrato", "")
    if modelo_contrato not in ["Acessórias", "Acessórias + Komunic"]:
        print(f"⚠️ Modelo de contrato inválido: {modelo_contrato}. Ignorando empresa.")
        return None

    cnpj = company_data.get("cnpj")
    expected_system_id = MODELO_CONTRATO_TO_ID.get(modelo_contrato, "233")

    is_affiliated, current_system = check_company_system_affiliation(cnpj, expected_system_id)

    if is_affiliated:
        print(f"✅ Empresa com CNPJ {cnpj} já existe no Bitrix24 e está associada ao sistema {current_system}.")
        return None

    # Verifica se a empresa já existe antes de criar
    company_response = check_company_in_bitrix(cnpj)
    if company_response and "result" in company_response and company_response["result"]:
        company_id = company_response["result"][0]["ID"]
        print(f"🔄 Usando empresa existente ID: {company_id}")
    else:
        company_id = create_company_in_bitrix(company_data)
        if not company_id:
            print(f"❌ Erro ao criar empresa {company_data['razaoSocial']}")
            return None
        print(f"🏢 Nova empresa criada com sucesso. ID: {company_id}")

    # Verifica se já existe um card
    existing_card_ids = check_card_exists(company_id)
    if existing_card_ids:
        print(f"⚠️ Card(s) já existente(s) para {company_data['razaoSocial']}. IDs: {existing_card_ids}")
        # Retorna None ao invés do dicionário quando encontra cards existentes
        return None

    # Só cria um novo card se não existir nenhum
    print("➕ Criando novo card...")
    response = create_card_in_bitrix(company_data, company_id)

    if response and "result" in response:
        card_id = response["result"]
        if isinstance(card_id, dict) and "item" in card_id and "id" in card_id["item"]:
            card_id = card_id["item"]["id"]

        print(f"✅ Card criado com sucesso para {company_data['razaoSocial']}. ID: {card_id}")
        return {
            "razaoSocial": company_data["razaoSocial"],
            "cnpj": company_data["cnpj"],
            "card_id": str(card_id),
            "modeloDeContrato": modelo_contrato
        }

    print(f"❌ Erro: O card não foi criado corretamente para {company_data['razaoSocial']}.")
    return None