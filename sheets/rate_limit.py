"""
rate_limit.py

Limitador de taxa compartilhado por toda a integração com o Google
Sheets, e um proxy fino em volta de gspread.Worksheet que aplica esse
limite antes de cada chamada que gera uma requisição HTTP à API.

Por que isso existe: a cota do Google Sheets ("Read requests per minute
per user" / "Write requests per minute per user") é de 60 por padrão,
contada por usuário (a conta de serviço), somando leituras E escritas -
não é por aba nem por tipo de operação. Antes desta mudança, o pipeline
só reagia ao erro 429 depois dele acontecer (retry). Com o RateLimiter,
a ideia é não deixar a 429 acontecer: cada chamada que sairia para a API
primeiro "pede passagem" a este limitador, que dorme o tempo necessário
se já estivermos perto do limite na janela de 1 minuto.

Uso típico (dentro de cada manager do pacote sheets/):

    from .rate_limit import RateLimiter, abrir_worksheet_limitado

    class TransacoesManager:
        def __init__(self, spreadsheet, limiter: RateLimiter):
            self._ws = abrir_worksheet_limitado(spreadsheet, ABA_TRANSACOES, limiter)
            # a partir daqui, self._ws.append_row(...), self._ws.get_all_records(...)
            # etc. funcionam exatamente como o Worksheet original do gspread -
            # só que cada chamada passa pelo limitador antes de sair.
"""

from __future__ import annotations

import threading
import time
from collections import deque

import gspread


class RateLimiter:
    """
    Limitador de taxa por janela deslizante, thread-safe.

    Os managers do pacote sheets/ são chamados de dentro de
    asyncio.to_thread (as chamadas do gspread são bloqueantes), então
    isso roda em threads de worker do asyncio, não na event loop -
    daí o uso de threading.Lock/time.sleep em vez dos equivalentes
    assíncronos.

    Garante que nunca mais que `max_requisicoes` chamadas saiam num
    intervalo de `janela_segundos`, dormindo (bloqueando a thread atual)
    o tempo necessário antes de liberar a próxima. `max_requisicoes`
    fica deliberadamente um pouco ABAIXO da cota real do Google (60/min
    por padrão) para deixar margem para você usar a planilha manualmente
    ao mesmo tempo, sem estourar a cota.
    """

    def __init__(self, max_requisicoes: int = 50, janela_segundos: float = 60.0):
        self._max = max_requisicoes
        self._janela = janela_segundos
        self._timestamps: deque[float] = deque()
        self._lock = threading.Lock()

    def aguardar(self) -> None:
        """Bloqueia até haver espaço para mais uma requisição na janela atual."""
        while True:
            with self._lock:
                agora = time.monotonic()
                while self._timestamps and agora - self._timestamps[0] >= self._janela:
                    self._timestamps.popleft()

                if len(self._timestamps) < self._max:
                    self._timestamps.append(agora)
                    return

                espera = self._janela - (agora - self._timestamps[0])

            # dorme fora do lock, para não travar outras threads enquanto espera
            time.sleep(max(espera, 0.05))


class WorksheetComLimite:
    """
    Proxy em volta de um gspread.Worksheet: cada método passa por
    RateLimiter.aguardar() antes de delegar para o Worksheet real. A
    troca por esta classe é transparente para quem já usava
    self._ws.append_row(...) etc. - mesma assinatura, mesmo retorno.

    Só expõe os métodos que o projeto realmente usa hoje
    (transacoes.py, compras_parceladas.py, carteira.py). Se algum outro
    módulo (ex. fatura.py) precisar de outro método do Worksheet, é só
    adicionar aqui seguindo o mesmo padrão.
    """

    def __init__(self, worksheet: gspread.Worksheet, limiter: RateLimiter):
        self._ws = worksheet
        self._limiter = limiter

    def append_row(self, *args, **kwargs):
        self._limiter.aguardar()
        return self._ws.append_row(*args, **kwargs)

    def append_rows(self, *args, **kwargs):
        self._limiter.aguardar()
        return self._ws.append_rows(*args, **kwargs)

    def get_all_records(self, *args, **kwargs):
        self._limiter.aguardar()
        return self._ws.get_all_records(*args, **kwargs)

    def update_cell(self, *args, **kwargs):
        self._limiter.aguardar()
        return self._ws.update_cell(*args, **kwargs)

    def row_values(self, *args, **kwargs):
        self._limiter.aguardar()
        return self._ws.row_values(*args, **kwargs)

    def col_values(self, *args, **kwargs):
        self._limiter.aguardar()
        return self._ws.col_values(*args, **kwargs)

    def find(self, *args, **kwargs):
        self._limiter.aguardar()
        return self._ws.find(*args, **kwargs)

    def cell(self, *args, **kwargs):
        self._limiter.aguardar()
        return self._ws.cell(*args, **kwargs)


def abrir_worksheet_limitado(spreadsheet: gspread.Spreadsheet, nome: str, limiter: RateLimiter) -> WorksheetComLimite:
    """
    Equivalente a spreadsheet.worksheet(nome), mas passando também pelo
    RateLimiter (a própria resolução do nome da aba já é uma requisição
    de leitura) e devolvendo o Worksheet já embrulhado em
    WorksheetComLimite, pronto para ser guardado em self._ws.
    """
    limiter.aguardar()
    return WorksheetComLimite(spreadsheet.worksheet(nome), limiter)