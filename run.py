import os
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import json as json_lib  # para evitar conflito com o json da stdlib

from create_sittax import create_comp_and_card_sittax
from create_acessorias import create_comp_and_card_acessorias
from fetch_emails import process_emails

process_emails()

def process_json_files(cache_dir='cache/'):
    """
    Processa os arquivos JSON no diretório de cache e acumula
    apenas os registros de cards efetivamente criados no Bitrix.
    """
    novos_registros = []

    for filename in os.listdir(cache_dir):
        if filename.endswith('.json'):
            filepath = os.path.join(cache_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as file:
                data = json.load(file)

            modelo = data.get('modeloDeContrato', '').strip()
            hash_name = filename[:-5]
            registro = None

            print(f"📂 Processando arquivo: {filename} | Modelo: {modelo}")

            if modelo in ["Acessórias", "Acessórias + Komunic"]:
                registro = create_comp_and_card_acessorias(hash_name)
            elif modelo in ["Openix - Sittax SN", "Sittax - Simples Nacional"]:
                registro = create_comp_and_card_sittax(hash_name)

            print(f"🔍 Registro retornado para {hash_name}: {registro}")

            # Só adiciona aos novos registros se um registro válido for retornado
            if registro is not None:
                novos_registros.append(registro)
                print(f"✅ Novo registro adicionado: {registro}")

    print(f"📊 Total de novos registros criados: {len(novos_registros)}")
    return novos_registros


def send_new_records_email(novos_registros):
    """
    Envia emails separados para os grupos definidos:
    - EMAIL_RECEIVER_SITTAX -> Recebe apenas contratos Sittax.
    - EMAIL_RECEIVER_ACESSORIAS -> Recebe apenas contratos Acessórias.
    - EMAIL_RECEIVER_GENERAL -> Recebe todos os contratos.
    """
    if not novos_registros:
        print("Nenhum registro novo encontrado. Email não será enviado.")
        return

    EMAIL = os.getenv('EMAIL')
    PASSWORD = os.getenv('PASSWORD')
    SMTP_SERVER = os.getenv('SMTP_SERVER')

    try:
        EMAIL_RECEIVER_SITTAX = json_lib.loads(os.getenv('EMAIL_RECEIVER_SITTAX'))
        EMAIL_RECEIVER_ACESSORIAS = json_lib.loads(os.getenv('EMAIL_RECEIVER_ACESSORIAS'))
        EMAIL_RECEIVER_GENERAL = json_lib.loads(os.getenv('EMAIL_RECEIVER_GENERAL'))
    except Exception:
        EMAIL_RECEIVER_SITTAX = os.getenv('EMAIL_RECEIVER_SITTAX').split(',')
        EMAIL_RECEIVER_ACESSORIAS = os.getenv('EMAIL_RECEIVER_ACESSORIAS').split(',')
        EMAIL_RECEIVER_GENERAL = os.getenv('EMAIL_RECEIVER_GENERAL').split(',')

    # Separar registros por tipo de contrato
    registros_sittax = []
    registros_acessorias = []

    for registro in novos_registros:
        modelo = registro.get('modeloDeContrato', '')
        if modelo in ["Sittax - Simples Nacional", "Openix - Sittax SN"]:
            registros_sittax.append(registro)
        elif modelo in ["Acessórias", "Acessórias + Komunic"]:
            registros_acessorias.append(registro)

    # Função para montar e enviar o email
    def enviar_email(destinatarios, registros, tipo_email):
        if not registros or not destinatarios:
            return  # Se não há registros ou destinatários, não envia email

        subject = f"Nova Abertura de Base no Bitrix - {tipo_email}"

        body = """\
<html>
<head>
  <style>
    body {{
      font-family: Arial, sans-serif;
      background-color: #f4f4f4;
      color: #333;
      padding: 20px;
    }}
    .container {{
      background-color: #fff;
      padding: 20px;
      border-radius: 5px;
      box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }}
    h2 {{
      color: #2a7ae2;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 20px;
    }}
    th, td {{
      padding: 10px;
      text-align: left;
      border-bottom: 1px solid #ddd;
    }}
    th {{
      background-color: #2a7ae2;
      color: #fff;
    }}
    .footer {{
      margin-top: 20px;
      font-size: 0.9em;
      color: #777;
    }}
  </style>
</head>
<body>
  <div class="container">
    <h2>Nova Abertura de Base no Bitrix - {tipo_email}</h2>
    <p>Foram abertas as seguintes bases no Bitrix:</p>
    <table>
      <tr>
        <th>Empresa</th>
        <th>CNPJ</th>
        <th>Modelo de Contrato</th>
        <th>Link do Card</th>
      </tr>
      {rows}
    </table>
    <p class="footer">Este é um email automático. Por favor, não responda.</p>
  </div>
</body>
</html>
"""
        rows = ""
        for registro in registros:
            empresa = registro.get('razaoSocial', 'N/A')
            cnpj = registro.get('cnpj', 'N/A')
            modelo = registro.get('modeloDeContrato', 'N/A')
            card_id = str(registro.get('card_id', '')).strip()

            if modelo in ["Sittax - Simples Nacional", "Openix - Sittax SN"]:
                card_url = f"https://setup.bitrix24.com.br/page/suporte_mister/sittax/type/158/details/{card_id}/"
            elif modelo in ["Acessórias", "Acessórias + Komunic"]:
                card_url = f"https://setup.bitrix24.com.br/page/acessorias/acessorias_2/type/187/details/{card_id}/"
            else:
                card_url = f"https://setup.bitrix24.com.br/crm/item/view/{card_id}/"

            rows += f"<tr><td>{empresa}</td><td>{cnpj}</td><td>{modelo}</td><td><a href='{card_url}'>Ver Card</a></td></tr>\n"

        body = body.format(tipo_email=tipo_email, rows=rows)
        msg = MIMEMultipart("alternative")
        msg['From'] = EMAIL
        msg['To'] = ", ".join(destinatarios)
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))

        try:
            server = smtplib.SMTP(SMTP_SERVER, 587)
            server.starttls()
            server.login(EMAIL, PASSWORD)
            server.sendmail(EMAIL, destinatarios, msg.as_string())
            server.quit()
            print(f"📧 Email enviado com sucesso para {tipo_email}: {destinatarios}")
        except Exception as e:
            print(f"❌ Erro ao enviar email para {tipo_email}: {e}")

    # Enviar emails para os grupos correspondentes
    enviar_email(EMAIL_RECEIVER_SITTAX, registros_sittax, "Sittax")
    enviar_email(EMAIL_RECEIVER_ACESSORIAS, registros_acessorias, "Acessórias")
    enviar_email(EMAIL_RECEIVER_GENERAL, novos_registros, "Geral")  # Envia todos

if __name__ == "__main__":
    novos_registros = process_json_files()
    send_new_records_email(novos_registros)
