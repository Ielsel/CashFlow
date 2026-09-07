"""
sheets_setup.py

Responsável por garantir que a planilha do Google Sheets tem as 4 abas
esperadas (Transacoes, Compras_Parceladas, Carteira, Fatura) com o
cabeçalho correto, por migrar planilhas antigas quando uma coluna nova
é introduzida no schema (credito_processado, alocado_processado,
ciclo_inicial, valor_previsto), e por aplicar uma formatação visual
simples e consistente nas 4 abas.

Não guarda estado próprio além da referência à spreadsheet - é chamado
uma vez na inicialização do SheetsManager (orquestrador). A formatação
roda nesse mesmo momento (não é chamada de novo pelos jobs periódicos),
então não passa pelo RateLimiter compartilhado - mesma situação em que
o resto deste arquivo já estava.
"""

from __future__ import annotations

import re

import gspread
from gspread.utils import rowcol_to_a1

from .config import (
    ABA_TRANSACOES,
    ABA_COMPRAS_PARCELADAS,
    ABA_CARTEIRA,
    ABA_FATURA,
    CATEGORIA_CONTROLE,
    CATEGORIAS_POTINHO,
    HEADER_TRANSACOES,
    HEADER_COMPRAS_PARCELADAS,
    HEADER_CARTEIRA,
    HEADER_FATURA,
)

# --- Cores usadas na formatação (RGB de 0.0 a 1.0, formato da Sheets API) ---

COR_CABECALHO_FUNDO = {"red": 0.16, "green": 0.24, "blue": 0.31}   # azul-acinzentado escuro
COR_CABECALHO_TEXTO = {"red": 1.0, "green": 1.0, "blue": 1.0}       # branco

COR_ZEBRA_PAR = {"red": 1.0, "green": 1.0, "blue": 1.0}             # branco
COR_ZEBRA_IMPAR = {"red": 0.93, "green": 0.95, "blue": 0.97}        # cinza-azulado bem claro

COR_VALOR_GUARDADO = {"red": 0.85, "green": 0.94, "blue": 0.83}     # verde claro - saldo_credito
COR_VALOR_A_PAGAR = {"red": 0.99, "green": 0.87, "blue": 0.82}      # salmão claro - valor_parcela


class EstruturaPlanilha:
    def __init__(self, spreadsheet: gspread.Spreadsheet):
        self._sh = spreadsheet

    def garantir_estrutura(self) -> None:
        """
        Garante que as 4 abas existem e têm cabeçalho, seja a aba nova (criada
        pelo próprio código) ou uma que você já tenha criado manualmente na
        interface do Sheets (nesse caso ela existe mas está vazia - o cabeçalho
        é escrito do mesmo jeito). Idempotente: rodar de novo não duplica nada.

        A formatação visual (cabeçalho, zebra, destaque de colunas) roda por
        último, sempre - inclusive em abas que já existiam antes desta
        versão, para que planilhas antigas também fiquem formatadas.
        """
        ws_transacoes = self._obter_ou_criar_aba(ABA_TRANSACOES, cols=len(HEADER_TRANSACOES))
        if self._primeira_linha_vazia(ws_transacoes):
            ws_transacoes.append_row(HEADER_TRANSACOES)

        ws_compras = self._obter_ou_criar_aba(ABA_COMPRAS_PARCELADAS, cols=len(HEADER_COMPRAS_PARCELADAS), rows=200)
        if self._primeira_linha_vazia(ws_compras):
            ws_compras.append_row(HEADER_COMPRAS_PARCELADAS)
        else:
            self._migrar_coluna_credito_processado(ws_compras)
            self._migrar_coluna_ciclo_inicial(ws_compras)

        ws_carteira = self._obter_ou_criar_aba(ABA_CARTEIRA, cols=len(HEADER_CARTEIRA), rows=200)
        if self._primeira_linha_vazia(ws_carteira):
            ws_carteira.append_row(HEADER_CARTEIRA)
            # Linhas iniciais de controle: Total e Sobrando
            ws_carteira.append_row([CATEGORIA_CONTROLE, "Total", "", 0, ""])
            ws_carteira.append_row([CATEGORIA_CONTROLE, "Sobrando", "", 0, ""])
        else:
            self._migrar_coluna_alocado_processado(ws_carteira)

        ws_fatura = self._obter_ou_criar_aba(ABA_FATURA, cols=len(HEADER_FATURA), rows=60)
        if self._primeira_linha_vazia(ws_fatura):
            ws_fatura.append_row(HEADER_FATURA)
        else:
            self._migrar_coluna_valor_previsto_fatura(ws_fatura)

        self._formatar_aba(ws_transacoes, len(HEADER_TRANSACOES))
        self._formatar_aba(ws_compras, len(HEADER_COMPRAS_PARCELADAS))
        self._formatar_aba(ws_carteira, len(HEADER_CARTEIRA))
        self._formatar_aba(ws_fatura, len(HEADER_FATURA))

        # Guardado (saldo_credito, coluna E) vs. a pagar (valor_parcela,
        # coluna D) - só faz sentido em Compras_Parceladas.
        self._colorir_coluna(ws_compras, coluna=4, cor=COR_VALOR_A_PAGAR)   # valor_parcela
        self._colorir_coluna(ws_compras, coluna=5, cor=COR_VALOR_GUARDADO)  # saldo_credito

    def _obter_ou_criar_aba(self, titulo: str, cols: int, rows: int = 1000):
        """Retorna a worksheet, criando-a se não existir. Não mexe em conteúdo."""
        try:
            return self._sh.worksheet(titulo)
        except gspread.WorksheetNotFound:
            return self._sh.add_worksheet(title=titulo, rows=rows, cols=cols)

    @staticmethod
    def _primeira_linha_vazia(ws) -> bool:
        """True se a linha 1 não tem nenhum valor - cobre tanto aba nova quanto
        aba que você já criou manualmente na interface (fica vazia por padrão)."""
        primeira_linha = ws.row_values(1)
        return len(primeira_linha) == 0

    # ------------------------------------------------------------------ #
    # Formatação visual
    # ------------------------------------------------------------------ #

    @staticmethod
    def _letra_coluna(indice_1_based: int) -> str:
        """Ex: 1 -> 'A', 10 -> 'J'."""
        a1 = rowcol_to_a1(1, indice_1_based)
        return re.match(r"[A-Z]+", a1).group()

    def _formatar_cabecalho(self, ws, num_colunas: int) -> None:
        """Fundo escuro, texto branco em negrito, centralizado, e linha congelada."""
        ultima_coluna = self._letra_coluna(num_colunas)
        ws.format(f"A1:{ultima_coluna}1", {
            "backgroundColor": COR_CABECALHO_FUNDO,
            "textFormat": {"bold": True, "foregroundColor": COR_CABECALHO_TEXTO},
            "horizontalAlignment": "CENTER",
        })
        ws.freeze(rows=1)

    def _tem_banding(self, sheet_id: int) -> bool:
        """
        Evita adicionar uma faixa zebrada nova toda vez que garantir_estrutura()
        roda (o que aconteceria a cada inicialização do pipeline, empilhando
        regras duplicadas). Se a aba já tem alguma faixa (bandedRange), pula.
        """
        metadados = self._sh.fetch_sheet_metadata()
        for aba in metadados.get("sheets", []):
            if aba["properties"]["sheetId"] == sheet_id and aba.get("bandedRanges"):
                return True
        return False

    def _aplicar_zebra(self, ws, num_colunas: int) -> None:
        """
        Linhas alternadas via banding nativo do Sheets - diferente de colorir
        célula por célula, isso se estende sozinho conforme novas linhas são
        adicionadas na aba, sem precisar rodar de novo.
        """
        if self._tem_banding(ws.id):
            return
        self._sh.batch_update({
            "requests": [{
                "addBanding": {
                    "bandedRange": {
                        "range": {
                            "sheetId": ws.id,
                            "startRowIndex": 0,
                            "startColumnIndex": 0,
                            "endColumnIndex": num_colunas,
                        },
                        "rowProperties": {
                            "headerColor": COR_CABECALHO_FUNDO,
                            "firstBandColor": COR_ZEBRA_PAR,
                            "secondBandColor": COR_ZEBRA_IMPAR,
                        },
                    }
                }
            }]
        })

    def _colorir_coluna(self, ws, coluna: int, cor: dict) -> None:
        """
        Pinta o fundo de uma coluna inteira (da linha 2 até o limite de linhas
        da aba) com uma cor sólida - usado para destacar visualmente
        saldo_credito (guardado) e valor_parcela (a pagar) em
        Compras_Parceladas. Reaplicar isso não tem efeito colateral (só
        redefine a mesma cor), diferente da zebra - por isso não precisa de
        checagem de idempotência aqui.
        """
        letra = self._letra_coluna(coluna)
        ws.format(f"{letra}2:{letra}{ws.row_count}", {"backgroundColor": cor})

    def _formatar_aba(self, ws, num_colunas: int) -> None:
        self._formatar_cabecalho(ws, num_colunas)
        self._aplicar_zebra(ws, num_colunas)

    # ------------------------------------------------------------------ #
    # Migrações de schema
    # ------------------------------------------------------------------ #

    @staticmethod
    def _migrar_coluna_credito_processado(ws) -> None:
        """
        Compatibilidade com planilhas criadas antes da coluna credito_processado
        existir. Se a coluna já existe no cabeçalho, não faz nada (idempotente).
        Se não existe, adiciona o cabeçalho na última posição e faz backfill nas
        linhas já existentes com credito_processado = saldo_credito - ou seja,
        assume que tudo que já está na planilha hoje já foi contabilizado no
        Sobrando antes, evitando um ajuste indevido na primeira sincronização.
        """
        cabecalho = ws.row_values(1)
        if "credito_processado" in cabecalho:
            return

        col_saldo_credito = cabecalho.index("saldo_credito") + 1  # 1-based
        nova_col = len(cabecalho) + 1

        if ws.col_count < nova_col:
            ws.resize(cols=nova_col)

        ws.update_cell(1, nova_col, "credito_processado")

        valores_saldo = ws.col_values(col_saldo_credito)[1:]  # pula cabeçalho
        for i, valor in enumerate(valores_saldo, start=2):
            if valor != "":
                ws.update_cell(i, nova_col, valor)

    @staticmethod
    def _migrar_coluna_ciclo_inicial(ws) -> None:
        """
        Compatibilidade com potinhos criados antes do controle de ciclo de
        fatura existir. Adiciona a coluna vazia - potinhos antigos ficam de
        fora do processamento automático por ciclo (ver
        ComprasParceladasManager.processar_ciclo) até você preencher
        manualmente o mes_referencia ("YYYY-MM") em que a primeira parcela
        deveria ter sido cobrada. Processamento manual via
        processar_parcela_vencida continua funcionando normalmente enquanto
        isso - só o gatilho automático por fatura paga é que não os alcança.
        """
        cabecalho = ws.row_values(1)
        if "ciclo_inicial" in cabecalho:
            return

        nova_col = len(cabecalho) + 1
        if ws.col_count < nova_col:
            ws.resize(cols=nova_col)

        ws.update_cell(1, nova_col, "ciclo_inicial")

    @staticmethod
    def _migrar_coluna_alocado_processado(ws) -> None:
        """
        Mesma lógica de _migrar_coluna_credito_processado, aplicada à Carteira:
        se a coluna alocado_processado ainda não existe, cria e faz backfill
        com o valor atual de "alocado" em cada linha de potinho (reserva/conta),
        assumindo que o que já está na planilha hoje já foi contabilizado no
        Sobrando. Linhas de controle (Total/Sobrando) ficam de fora do backfill.
        """
        cabecalho = ws.row_values(1)
        if "alocado_processado" in cabecalho:
            return

        col_categoria = cabecalho.index("categoria") + 1
        col_alocado = cabecalho.index("alocado") + 1
        nova_col = len(cabecalho) + 1

        if ws.col_count < nova_col:
            ws.resize(cols=nova_col)

        ws.update_cell(1, nova_col, "alocado_processado")

        categorias = ws.col_values(col_categoria)[1:]
        valores_alocado = ws.col_values(col_alocado)[1:]
        for i, (categoria, valor) in enumerate(zip(categorias, valores_alocado), start=2):
            if categoria.strip().lower() in CATEGORIAS_POTINHO and valor != "":
                ws.update_cell(i, nova_col, valor)

    @staticmethod
    def _migrar_coluna_valor_previsto_fatura(ws) -> None:
        """Adiciona o total esperado ao schema de Fatura já existente."""
        cabecalho = ws.row_values(1)
        if "valor_previsto" in cabecalho:
            return

        nova_col = len(cabecalho) + 1
        if ws.col_count < nova_col:
            ws.resize(cols=nova_col)
        ws.update_cell(1, nova_col, "valor_previsto")