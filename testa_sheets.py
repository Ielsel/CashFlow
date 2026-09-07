"""
Script temporário só pra diagnosticar. Roda com:
    python testa_sheets.py
Depois pode apagar.
"""
import os
from dotenv import load_dotenv
from sheets import SheetsManager

load_dotenv()

SPREADSHEET_ID = os.environ["SPREADSHEET_ID"]
CREDENTIALS_PATH = os.environ.get("GOOGLE_CREDENTIALS_PATH", "credentials.json")

print("Conectando...")
sm = SheetsManager(spreadsheet_id=SPREADSHEET_ID, credentials_path=CREDENTIALS_PATH)
print("Conectado e estrutura garantida com sucesso!")

print("\nTestando registrar_transacao...")
sm.registrar_transacao(
    item="TESTE DIAGNOSTICO",
    valor_total=1.23,
    destino="A categorizar",
    status="teste",
)
print("registrar_transacao OK - confere se apareceu uma linha na aba Transacoes")

print("\nTestando sincronizar_creditos_manuais...")
ajustes = sm.sincronizar_creditos_manuais()
print("sincronizar_creditos_manuais OK - ajustes:", ajustes)