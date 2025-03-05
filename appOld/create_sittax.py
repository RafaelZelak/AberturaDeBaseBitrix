import os
import json
import requests
from datetime import datetime, timedelta
from verify_data import check_sittax_affiliation_from_cache, check_company_in_bitrix

# Configurações
CACHE_DIR = "cache"
BITRIX_WEBHOOK_URL = os.getenv('BITRIX_WEBHOOK_URL')

# Mapeamentos
MODELO_CONTRATO_TO_ID = {
    "Sittax - Simples Nacional": 237,
    "Acessórias": 233,
    "Acessórias + KOMUNIC": 235,
    "Sittax / Acessórias": 655,
    "Sittax / Acessórias + KOMUNIC": 699,
    "Best Doctor": 701,
}

MODELO_CONTRATO_TO_UF_CRM_ID = {
    "Sittax - Simples Nacional": 691,  # ID para Setup
    "Openix - Sittax SN": 693,        # ID para Openix
}

MODELO_CONTRATO_TO_REVENDA_ID = {
    "Sittax - Simples Nacional": 815,  # ID para Setup
    "Openix - Sittax SN": 813,         # ID para Openix
}

# Função para limpar e padronizar valores monetários
def clean_and_standardize_value(value):
    try:
        cleaned_value = value.split('(')[0].replace('R$', '').strip()
        cleaned_value = cleaned_value.replace('.', '').replace(',', '.')
        return f"{cleaned_value}"
    except Exception as e:
        print(f"Erro ao limpar o valor {value}: {e}")
        return None

# Função para criar a empresa no Bitrix24
def create_company_in_bitrix(company_data):
    url = f"{BITRIX_WEBHOOK_URL}/crm.company.add"

    modelo_id = MODELO_CONTRATO_TO_ID.get(company_data.get("modeloDeContrato", ""), 237)
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
            "UF_CRM_1727441490980": company_data.get("consultor", ""),
            "UF_CRM_1727441546022": valor_licenca,
            "UF_CRM_1727441557582": valor_mensalidade,
            "UF_CRM_1723638730243": uf_crm_id,
            "UF_CRM_1725555192239": company_data.get("diretor", "")
        }
    }

    response = requests.post(url, json=payload)
    if response.status_code == 200:
        print(f"Empresa {company_data['razaoSocial']} criada com sucesso.")
        return response.json().get("result")  # Retorna o ID da empresa
    else:
        print(f"Erro ao criar empresa {company_data['razaoSocial']}: {response.text}")
        return None

# Função para criar o card no Bitrix24
def create_card_in_bitrix(company_data, company_id):
    url = f"{BITRIX_WEBHOOK_URL}/crm.item.add"

    revenda_id = MODELO_CONTRATO_TO_REVENDA_ID.get(company_data.get("modeloDeContrato", ""), 815)
    valor_mensalidade = clean_and_standardize_value(company_data.get("valorMensalidade", ""))
    valor_licenca = clean_and_standardize_value(company_data.get("valorLicenca", ""))
    pacote = company_data.get("qtdCnpj", "")

    if valor_mensalidade is None or valor_licenca is None:
        print(f"Erro: Valores de mensalidade ou licença inválidos para a empresa {company_data['razaoSocial']}.")
        return

    begin_date = datetime.now().strftime("%Y-%m-%d")
    close_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

    payload = {
        "entityTypeId": 158,  # EntityTypeId do Smart Process Sittax
        "fields": {
            "title": company_data.get("razaoSocial", ""),
            "stageId": "DT158_11:NEW",
            "categoryId": 11,
            "assignedById": 629,
            "opened": "N",
            "begindate": begin_date,
            "closedate": close_date,
            "currencyId": "BRL",
            "opportunity": 0,
            "isManualOpportunity": "N",
            "sourceId": "CALL",
            "ufCrm5_1737545372279": company_data.get("razaoSocial", ""),
            "ufCrm5_1737545379350": company_data.get("cnpj", ""),
            "ufCrm5_1710961669613": company_data.get("emails", [])[0] if company_data.get("emails") else "",
            "ufCrm25_1710505566404": valor_mensalidade,
            "ufCrm25_1710505188682": pacote,
            "ufCrm5_1736438430958": revenda_id,
            "companyId": company_id,
            "contactId": 0,
            "mycompanyId": 0,
            "taxValue": 0,
            "taxValueAccount": 0,
            "accountCurrencyId": "BRL",
            "opportunityAccount": 0,
            "webformId": 0
        }
    }

    response = requests.post(url, json=payload)
    if response.status_code == 200:
        print(f"Card criado com sucesso para a empresa {company_data['razaoSocial']}.")
    else:
        print(f"Erro ao criar card para a empresa {company_data['razaoSocial']}: {response.text}")

# Função principal para criar empresa e card
def create_comp_and_card_sittax(hash_value):
    json_path = os.path.join(CACHE_DIR, f"{hash_value}.json")
    if not os.path.exists(json_path):
        print(f"Arquivo JSON para o hash {hash_value} não encontrado.")
        return

    with open(json_path, 'r') as file:
        company_data = json.load(file)

        # Verifica se o modelo de contrato é válido
        modelo_contrato = company_data.get("modeloDeContrato", "")
        if modelo_contrato not in ["Sittax - Simples Nacional", "Openix - Sittax SN"]:
            print(f"Modelo de contrato inválido: {modelo_contrato}. Ignorando empresa.")
            return

        # Verifica se a empresa já existe no Bitrix24
        cnpj = company_data.get("cnpj")
        company_response = check_company_in_bitrix(cnpj)
        if company_response and "result" in company_response and company_response["result"]:
            print(f"Empresa com CNPJ {cnpj} já existe no Bitrix24. Ignorando criação.")
            return

        # Verifica afiliação à Sittax e cria a empresa/card se necessário
        if not check_sittax_affiliation_from_cache(hash_value):
            company_id = create_company_in_bitrix(company_data)
            if company_id:
                create_card_in_bitrix(company_data, company_id)
        else:
            print(f"=== Já existe no Bitrix (ignorar) ===\n\n")

