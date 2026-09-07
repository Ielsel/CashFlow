"""
config.py

Constantes e estruturas de dados compartilhadas pelos módulos do
gestor financeiro automatizado (Google Sheets).
"""

from __future__ import annotations

from dataclasses import dataclass

# Nomes das abas na planilha
ABA_TRANSACOES = "Transacoes"
ABA_COMPRAS_PARCELADAS = "Compras_Parceladas"
ABA_CARTEIRA = "Carteira"
ABA_FATURA = "Fatura"

# Categoria reservada para as linhas de controle (Total / Sobrando) na
# aba Carteira - nunca entra na sincronização de potinhos.
CATEGORIA_CONTROLE = "controle"
CATEGORIAS_POTINHO = ("reserva", "conta")

# Cabeçalhos de cada aba (usados na criação automática)
HEADER_TRANSACOES = [
    "data", "item", "valor_total", "parcelas", "valor_parcela", "destino", "status",
]

# Compras_Parceladas ganha "ciclo_inicial": o mes_referencia ("YYYY-MM")
# do ciclo de fatura em que a primeira parcela dessa compra deve ser
# cobrada. É calculado a partir da data do comprovante (ver fatura.py:
# calcular_ciclo_referencia) - potinhos migrados de planilhas antigas
# ficam com essa coluna vazia até você preencher manualmente.
HEADER_COMPRAS_PARCELADAS = [
    "nome_compra", "valor_total", "num_parcelas", "valor_parcela",
    "saldo_credito", "parcelas_pagas", "alocacao_automatica", "status",
    "credito_processado", "ciclo_inicial",
]

# Carteira: categoria | nome | meta | alocado | alocado_processado
#   - linhas categoria="controle" (Total, Sobrando): "alocado" guarda o
#     próprio valor de controle; "alocado_processado" não é usado.
#   - linhas categoria="reserva"/"conta": potinhos geridos manualmente
#     na planilha, ver docstring do módulo carteira.py.
HEADER_CARTEIRA = ["categoria", "nome", "meta", "alocado", "alocado_processado"]

# Fatura: uma linha por ciclo mensal do cartão.
#   - mes_referencia: "YYYY-MM"
#   - data_fechamento / data_vencimento: "YYYY-MM-DD", calculadas a
#     partir de DIA_FECHAMENTO_FATURA/DIA_VENCIMENTO_FATURA abaixo
#   - status: "pendente" ou "paga" (você edita isso manualmente)
#   - ciclo_processado: coluna de controle (checkbox) - marcada
#     automaticamente quando o sistema já cobrou as parcelas desse ciclo
HEADER_FATURA = [
    "mes_referencia", "data_fechamento", "data_vencimento", "status",
    "ciclo_processado", "valor_previsto",
]

# Dia fixo (1-28, para não ter problema com fevereiro) de fechamento e
# de vencimento nominal da fatura. O vencimento real pode variar 1-2 dias
# por causa de dia útil - isso é ajustado automaticamente (empurra para a
# próxima segunda se cair em fim de semana), mas os DIAS abaixo precisam
# bater com o seu cartão de verdade. AJUSTE OS DOIS NÚMEROS ABAIXO.
DIA_FECHAMENTO_FATURA = 20
DIA_VENCIMENTO_FATURA = 27

# credito_processado / alocado_processado: colunas de controle internas,
# não editadas por você. Espelham o último valor que o próprio sistema já
# contabilizou no Sobrando. Se você editar saldo_credito ou alocado
# manualmente na planilha, essas colunas ficam diferentes - é assim que o
# job de sincronização detecta uma alocação manual e ajusta o Sobrando.

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


@dataclass
class ResultadoParcela:
    """Resultado do processamento de uma parcela vencida, para log/confirmação no bot."""
    nome_compra: str
    valor_parcela: float
    abatido_do_credito: float
    descontado_do_sobrando: float
    saldo_credito_restante: float
    potinho_fechado: bool


@dataclass
class AjusteCarteira:
    """Resultado de uma sincronização manual de potinho de Reserva/Conta, para log/bot."""
    categoria: str
    nome: str
    delta_alocado: float
    novo_sobrando: float