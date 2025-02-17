import imaplib
import email
from email.header import decode_header
import re
import json
import os
import hashlib
from dotenv import load_dotenv

# Carregar variáveis do arquivo .env
load_dotenv()

# Configurações de conexão
EMAIL = os.getenv('EMAIL')
PASSWORD = os.getenv('PASSWORD')
IMAP_SERVER = os.getenv('IMAP_SERVER')

# Caminho para a pasta de cache
CACHE_DIR = 'cache'
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

def format_phone(phone):
    """Formata o telefone no padrão +55DDDXXXXXXXXX."""
    if not phone:
        return None

    # Remove todos os caracteres não numéricos
    phone = re.sub(r'\D', '', phone)

    # Verifica se o telefone já começa com +55
    if phone.startswith('55') and len(phone) == 13:
        return f"+{phone}"  # Adiciona o sinal de + se já estiver no formato 55DDDXXXXXXXXX

    # Verifica se o telefone tem 10 ou 11 dígitos (sem o +55)
    if len(phone) == 10 or len(phone) == 11:
        return f"+55{phone}"  # Adiciona o +55 no início

    return None  # Retorna None se o telefone não puder ser formatado

def extract_field(regex, body, field_name):
    """Extrai um campo do corpo do e-mail usando regex e remove tags HTML e espaços extras."""
    match = re.search(regex, body, re.DOTALL)  # re.DOTALL permite que o . capture também quebras de linha
    if match:
        # Remove tags HTML e espaços extras
        cleaned_value = re.sub(r'<[^>]+>', '', match.group(1)).strip()  # Remove tags HTML e espaços
        cleaned_value = re.sub(r'&nbsp;', ' ', cleaned_value)  # Substitui &nbsp; por espaço
        cleaned_value = re.sub(r'\s+', ' ', cleaned_value)  # Remove espaços extras
        return cleaned_value
    else:
        print(f"Campo '{field_name}' não encontrado.")
        return None

def format_cnpj(cnpj):
    cnpj = re.sub(r'\D', '', cnpj)  # Remove todos os caracteres não numéricos
    if len(cnpj) == 14:  # Verifica se o CNPJ tem 14 dígitos
        return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
    return cnpj  # Retorna o CNPJ sem formatação se não tiver 14 dígitos

def generate_hash(data):
    """Gera um hash único baseado em uma string."""
    return hashlib.md5(data.encode()).hexdigest()

def process_emails():
    """Processa todos os e-mails de 'contratos@setuptecnologia.com.br' e cria caches com base no ID do contrato."""
    print("Conectando ao servidor IMAP...")
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)

    try:
        # Login na conta
        print("Fazendo login...")
        mail.login(EMAIL, PASSWORD)

        # Selecionando a caixa de entrada
        mail.select('inbox')  # Seleciona a caixa de entrada

        # Buscando TODOS os e-mails
        print("Buscando todos os e-mails...")
        status, messages = mail.search(None, 'ALL')  # 'ALL' busca todos os e-mails

        if status == 'OK':
            email_ids = messages[0].split()
            print(f"Encontrados {len(email_ids)} e-mails.")

            for email_id in email_ids:
                print(f"\nProcessando e-mail ID: {email_id}...")
                status, msg_data = mail.fetch(email_id, '(RFC822)')

                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        # Parse do e-mail
                        msg = email.message_from_bytes(response_part[1])

                        # Decodificando o remetente
                        from_, encoding = decode_header(msg.get('From'))[0]
                        if isinstance(from_, bytes):
                            from_ = from_.decode(encoding if encoding else 'utf-8')

                        # Verificando se o e-mail é do remetente desejado
                        if 'contratos@setuptecnologia.com' in from_:
                            # Decodificando o assunto
                            subject, encoding = decode_header(msg['Subject'])[0]
                            if isinstance(subject, bytes):
                                subject = subject.decode(encoding if encoding else 'utf-8')

                            # Extraindo o corpo do e-mail
                            body = ""
                            if msg.is_multipart():
                                # Iterar sobre as partes do e-mail
                                for part in msg.walk():
                                    content_type = part.get_content_type()
                                    content_disposition = str(part.get("Content-Disposition"))

                                    # Verificar se é texto simples ou HTML
                                    if content_type == "text/plain" and "attachment" not in content_disposition:
                                        body = part.get_payload(decode=True).decode()
                                        break  # Prioriza texto simples
                                    elif content_type == "text/html" and "attachment" not in content_disposition:
                                        body = part.get_payload(decode=True).decode()
                            else:
                                # E-mail não é multipart, extrair diretamente
                                body = msg.get_payload(decode=True).decode()

                            # Extrair o ID do contrato
                            contrato = extract_field(r'<b>Contrato:</b>\s*(.*?)\s*<br />', body, "Contrato")
                            if not contrato:
                                continue

                            print(f"Contrato encontrado: {contrato}")  # Depuração: Exibir o contrato

                            # Verificar se o cache já existe para esse contrato
                            hash_contrato = generate_hash(contrato)
                            cache_file = os.path.join(CACHE_DIR, f"{hash_contrato}.json")
                            if os.path.exists(cache_file):
                                print(f"Cache já existe para o contrato {contrato}. Pulando...")
                                continue

                            # Extrair outros campos
                            softwareERP = extract_field(r'<b>Software ERP:</b>\s*(.*?)\s*<br />', body, "Software ERP")
                            contrato = extract_field(r'<b>Contrato:</b>\s*(.*?)\s*<br />', body, "Contrato")
                            modeloDeContrato = extract_field(r'<b>Modelo de Contrato:</b>\s*(.*?)\s*<br />', body, "Modelo de Contrato")
                            data = extract_field(r'<b>Data:</b>\s*(.*?)\s*<br />', body, "Data")
                            consultor = extract_field(r'<b>Consultor:</b>\s*(.*?)\s*<br />', body, "Consultor")
                            razaoSocial = extract_field(r'<b>Razão Social:</b>\s*(.*?)\s*<br />', body, "Razão Social")
                            cnpj = extract_field(r'<b>CNPJ:</b>\s*(.*?)\s*<br />', body, "CNPJ")
                            nomeFantasia = extract_field(r'<b>Nome Fantasia:</b>\s*(.*?)\s*<br />', body, "Nome Fantasia")
                            emailContratante = extract_field(r'<b>E-mail:</b>\s*(.*?)\s*<br />', body, "E-mail Contratante")
                            valorLicenca = extract_field(r'Valor da Licença:\s*(.*?)\s*<br />', body, "Valor da Licença")
                            tipoPagamento = extract_field(r'Tipo de Pagamento:\s*(.*?)\s*<br />', body, "Tipo de Pagamento")
                            formaPagamento = extract_field(r'Forma de Pagamento:\s*(.*?)\s*<br />', body, "Forma de Pagamento")
                            parcelas = extract_field(r'Parcelas:\s*(.*?)\s*<br />', body, "Parcelas")
                            entradaPix = extract_field(r'Entrada pix:\s*(.*?)\s*<br />', body, "Entrada Pix")
                            valorMensalidade = extract_field(r'Valor da Mensalidade:\s*(.*?)\s*<br />', body, "Valor da Mensalidade")
                            primeiraMensalidade = extract_field(r'Primeira Mensalidade:\s*(.*?)\s*<br />', body, "Primeira Mensalidade")
                            nomeDiretor = extract_field(r'Nome:\s*(.*?)\s*<br />', body, "Nome Diretor")
                            emailDiretor = extract_field(r'E-mail:\s*(.*?)\s*<br />', body, "E-mail Diretor")
                            telefoneDiretor = format_phone(extract_field(r'Telefone:\s*(.*?)\s*<br />', body, "Telefone Diretor"))
                            cpfDiretor = extract_field(r'CPF:\s*(.*?)\s*<br />', body, "CPF Diretor")
                            nomeFinanceiro = extract_field(r'Nome:\s*(.*?)\s*<br />', body, "Nome Financeiro")
                            emailFinanceiro = extract_field(r'E-mail:\s*(.*?)\s*<br />', body, "E-mail Financeiro")
                            telefoneFinanceiro = format_phone(extract_field(r'Telefone:\s*(.*?)\s*<br />', body, "Telefone Financeiro"))
                            qtdCnpj = extract_field(r'Qtd. CNPJ:\s*(.*?)\s*<br />', body, "Qtd. CNPJ")  # Novo campo

                            # Verificar se todos os campos necessários foram extraídos
                            if not all([razaoSocial, cnpj, modeloDeContrato, consultor]):
                                print("Dados incompletos no e-mail. Pulando...")
                                continue

                            # Formatar o CNPJ
                            cnpj = format_cnpj(cnpj)

                            # Criar uma lista de e-mails
                            emails = [emailContratante, emailDiretor, emailFinanceiro]

                            # Criar uma lista de telefones
                            phones = []
                            if telefoneDiretor:
                                phones.append(telefoneDiretor)
                            if telefoneFinanceiro:
                                phones.append(telefoneFinanceiro)

                            # Dicionário para armazenar as informações
                            info_extraidas = {
                                "razaoSocial": razaoSocial.strip(),  # Remove espaços extras
                                "cnpj": cnpj,  # CNPJ formatado
                                "modeloDeContrato": modeloDeContrato.strip(),
                                "consultor": consultor.strip(),
                                "emails": emails,  # Lista de e-mails
                                "phones": phones,  # Lista de telefones formatados
                                "valorMensalidade": valorMensalidade.strip() if valorMensalidade else None,  # Valor da mensalidade
                                "valorLicenca": valorLicenca.strip() if valorLicenca else None,  # Valor da Licença
                                "qtdCnpj": qtdCnpj.strip() if qtdCnpj else None,  # Novo campo: Qtd. CNPJ
                                "diretor": nomeDiretor.strip() if nomeDiretor else None
                            }

                            # Salvar as informações em um arquivo de cache
                            with open(cache_file, 'w') as f:
                                json.dump(info_extraidas, f)

                            print(f"Cache salvo em: {cache_file}")
                        else:
                            print("E-mail não é do remetente desejado. Pulando...")
        else:
            print("Nenhum e-mail encontrado ou erro na busca.")

    except Exception as e:
        print(f"Erro: {e}")

    finally:
        # Fechando a conexão
        print(f"\nFechando conexão...\n\n")
        print(70*"-")
        print(f"\n\n")
        mail.logout()

process_emails()