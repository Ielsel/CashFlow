"""
transacoes.py

Camada 1: log bruto e imutável de transações (aba "Transacoes").
Cada chamada de registrar_transacao() adiciona uma linha nova - este
módulo nunca lê nem atualiza linhas existentes.

O worksheet é resolvido UMA VEZ no __init__ (via abrir_worksheet_limitado,
que já aplica o RateLimiter compartilhado) e reutilizado (self._ws) em
vez de chamado de novo a cada método - cada chamada a
spreadsheet.worksheet(nome) é, ela própria, uma requisição de leitura à
API (fetch_sheet_metadata) para resolver o nome pelo índice de abas.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Optional

import gspread

from .config import ABA_TRANSACOES
from .rate_limit import RateLimiter, abrir_worksheet_limitado

logger = logging.getLogger(__name__)


class TransacoesManager:
    def __init__(self, spreadsheet: gspread.Spreadsheet, limiter: RateLimiter):
        self._sh = spreadsheet
        self._ws = abrir_worksheet_limitado(spreadsheet, ABA_TRANSACOES, limiter)

    def registrar_transacao(
        self,
        item: str,
        valor_total: float,
        destino: str,
        parcelas: int = 1,
        valor_parcela: Optional[float] = None,
        status: str = "confirmado",
        data: Optional[str] = None,
    ) -> None:
        """Adiciona uma linha imutável na aba Transacoes. Não mexe em saldo/potinhos."""
        if valor_parcela is None:
            valor_parcela = round(valor_total / parcelas, 2) if parcelas > 1 else valor_total
        linha = [
            data or dt.date.today().isoformat(),
            item,
            valor_total,
            parcelas,
            valor_parcela,
            destino,
            status,
        ]
        self._ws.append_row(linha)

    def registrar_transacoes_em_lote(self, transacoes: list[dict]) -> None:
        """
        Versão em lote de registrar_transacao: grava todas as linhas com
        uma única chamada append_rows, em vez de um append_row (uma
        requisição de escrita cada) por transação. Pensada para o job de
        flush periódico do pipeline.py, que acumula os resultados do OCR
        em memória e grava tudo de uma vez a cada N segundos.

        Cada dict aceita as mesmas chaves de registrar_transacao: item,
        valor_total, destino, parcelas (default 1), valor_parcela
        (calculado automaticamente se omitido), status (default
        "confirmado"), data (default hoje).

        PROTEÇÃO CONTRA DUPLICATA: append_rows não é uma operação
        idempotente - chamar duas vezes com o mesmo conteúdo cria duas
        linhas. A fila_sheets no SQLite (ver pipeline.py) só marca um
        item como "enviado" DEPOIS de confirmar que este método retornou
        sem erro; se a escrita anterior já tinha ido pro Sheets com
        sucesso e só a CONFIRMAÇÃO não chegou até o pipeline (ex: timeout
        de rede depois do commit no servidor), o item continua "pendente"
        no SQLite e seria reenviado no próximo drenar_fila_sheets. Por
        isso, antes de escrever, lemos a coluna "item" (que embute o nome
        do arquivo, ex. "[a definir] cupom_20260906_042845.jpg" - único
        por construção) e pulamos qualquer transação do lote cujo "item"
        já esteja presente na planilha - segunda camada de proteção,
        independente do controle de estado do SQLite.

        Isso funciona enquanto "item" permanecer esse placeholder com o
        nome do arquivo. Quando a Etapa 3 (categorização com Qwen)
        substituir esse texto por uma descrição de verdade, essa checagem
        perde a referência - nesse momento, vale mover a chave de
        deduplicação para uma coluna própria (ex. "arquivo_origem"),
        separada de "item".
        """
        if not transacoes:
            return

        itens_existentes = set(self._ws.col_values(2))  # coluna B = item
        novas = [t for t in transacoes if t["item"] not in itens_existentes]

        duplicadas = len(transacoes) - len(novas)
        if duplicadas:
            logger.warning(
                "%d transação(ões) do lote já estavam registradas no Sheets "
                "(retry de um flush anterior) - pulando para não duplicar.",
                duplicadas,
            )

        if not novas:
            return

        linhas = []
        for t in novas:
            parcelas = t.get("parcelas", 1)
            valor_total = t["valor_total"]
            valor_parcela = t.get("valor_parcela")
            if valor_parcela is None:
                valor_parcela = round(valor_total / parcelas, 2) if parcelas > 1 else valor_total
            linhas.append([
                t.get("data") or dt.date.today().isoformat(),
                t["item"],
                valor_total,
                parcelas,
                valor_parcela,
                t["destino"],
                t.get("status", "confirmado"),
            ])

        self._ws.append_rows(linhas)