"""
carteira.py

Camada 2: aba "Carteira" - Total / Sobrando e os potinhos de Reservas
(Emergência, CNH, ...) e Contas (Internet, Gasolina, ...).

Potinhos de Reservas/Contas (controle 100% manual na planilha)
----------------------------------------------------------------
Diferente das compras parceladas (que têm ciclo de vida programático,
ver compras_parceladas.py), os potinhos de Reservas e Contas são
geridos inteiramente por você, direto na aba "Carteira":

  - Criar um potinho novo  -> adicione uma linha com categoria="reserva" ou
    "conta", o nome, a meta (opcional, só informativo) e "alocado" (pode
    começar em 0). Não precisa chamar nada em Python.
  - Remover um potinho     -> apague a linha. Não precisa de código.
  - Alocar/desalocar       -> edite o valor de "alocado" direto na célula.

O código nunca escreve em "alocado" - ele só LÊ e reage. A cada chamada de
sincronizar_potinhos_carteira() (rodada junto do job periódico em
pipeline.py), ele compara "alocado" com "alocado_processado" (coluna de
controle que ele mesmo mantém) linha a linha:

    delta = alocado - alocado_processado
    Sobrando -= delta
    alocado_processado = alocado

Ou seja: aumentar "alocado" puxa dinheiro do Sobrando; diminuir devolve.
Uma linha nova, sem "alocado_processado" preenchido, é tratada como se ele
fosse 0 - então já criar o potinho com "alocado" != 0 conta como uma
alocação normal.

O worksheet é resolvido UMA VEZ no __init__ (via abrir_worksheet_limitado,
que já aplica o RateLimiter compartilhado) e reutilizado (self._ws) em
vez de chamado de novo a cada método - cada chamada a
spreadsheet.worksheet(nome) é, ela própria, uma requisição de leitura à
API (fetch_sheet_metadata) para resolver o nome pelo índice de abas.

IMPORTANTE sobre leitura de números do Sheets: todas as leituras usam
value_render_option="UNFORMATTED_VALUE" em vez do padrão (que devolve o
texto formatado da célula - em pt-BR isso vem como "47,30" com vírgula,
e float("47,30") estoura ValueError, fazendo a sincronização falhar
silenciosamente). UNFORMATTED_VALUE devolve o número Python de verdade.
"""

from __future__ import annotations

import gspread

from .config import ABA_CARTEIRA, CATEGORIA_CONTROLE, CATEGORIAS_POTINHO, AjusteCarteira
from .rate_limit import RateLimiter, abrir_worksheet_limitado


class CarteiraManager:
    def __init__(self, spreadsheet: gspread.Spreadsheet, limiter: RateLimiter):
        self._sh = spreadsheet
        self._ws = abrir_worksheet_limitado(spreadsheet, ABA_CARTEIRA, limiter)
        self._linha_sobrando_cache: int | None = None

    # ------------------------------------------------------------------ #
    # Total / Sobrando
    # ------------------------------------------------------------------ #

    def _linha_sobrando(self) -> int:
        """
        Resolve e cacheia o número da linha de "Sobrando". self._ws.find()
        é uma chamada de leitura à API - sem cache, ajustar_sobrando() e
        get_sobrando() pagavam essa busca de novo em toda chamada, mesmo
        a linha nunca mudando de lugar em uso normal. Se você reordenar
        manualmente as linhas da aba Carteira, reinicie o pipeline para
        forçar a releitura.
        """
        if self._linha_sobrando_cache is None:
            self._linha_sobrando_cache = self._ws.find("Sobrando").row
        return self._linha_sobrando_cache

    def ajustar_sobrando(self, delta: float) -> float:
        """
        Soma (ou subtrai, se delta negativo) do valor atual de Sobrando.
        Retorna o novo valor. Exposto publicamente porque
        compras_parceladas.py também precisa chamá-lo.
        """
        linha = self._linha_sobrando()
        valor_atual = float(self._ws.cell(linha, 4, value_render_option="UNFORMATTED_VALUE").value or 0)
        novo_valor = round(valor_atual + delta, 2)
        self._ws.update_cell(linha, 4, novo_valor)
        return novo_valor

    def get_sobrando(self) -> float:
        linha = self._linha_sobrando()
        return float(self._ws.cell(linha, 4, value_render_option="UNFORMATTED_VALUE").value or 0)

    def sincronizar_total(self) -> float | None:
        """
        Trata a alteração manual de ``Total`` como entrada/retirada de
        dinheiro. A coluna alocado_processado registra o último Total já
        refletido no Sobrando, impedindo que o job periódico aplique a mesma
        entrada mais de uma vez.
        """
        registros = self._ws.get_all_records(value_render_option="UNFORMATTED_VALUE")
        cabecalho = self._ws.row_values(1)
        col_processado = cabecalho.index("alocado_processado") + 1

        for linha, registro in enumerate(registros, start=2):
            if (
                str(registro.get("categoria", "")).strip().lower() != CATEGORIA_CONTROLE
                or str(registro.get("nome", "")).strip().lower() != "total"
            ):
                continue

            total = float(registro.get("alocado", 0) or 0)
            total_processado = float(registro.get("alocado_processado", 0) or 0)
            delta = round(total - total_processado, 2)
            if delta:
                novo_sobrando = self.ajustar_sobrando(delta)
                self._ws.update_cell(linha, col_processado, total)
                return novo_sobrando
            return None

        raise ValueError("Linha de controle 'Total' não encontrada na aba Carteira.")

    def sincronizar_fatura_atual(self, valor_fatura: float) -> float:
        """
        Espelha na Carteira o total previsto para a fatura em aberto e
        reserva exatamente a diferença no Sobrando.

        Exemplo: se a Fatura atual passa de R$100 para R$310, o Sobrando
        diminui R$210. Rodar novamente com R$310 não produz novo desconto.
        """
        registros = self._ws.get_all_records(value_render_option="UNFORMATTED_VALUE")
        linha_fatura = None
        valor_anterior = 0.0
        for linha, registro in enumerate(registros, start=2):
            if (
                str(registro.get("categoria", "")).strip().lower() == CATEGORIA_CONTROLE
                and str(registro.get("nome", "")).strip().lower() == "fatura atual"
            ):
                linha_fatura = linha
                valor_anterior = float(registro.get("alocado", 0) or 0)
                break

        if linha_fatura is None:
            self._ws.append_row([CATEGORIA_CONTROLE, "Fatura atual", "", 0, ""])
            linha_fatura = len(registros) + 2

        novo_valor = round(valor_fatura, 2)
        delta = round(valor_anterior - novo_valor, 2)
        if delta:
            self.ajustar_sobrando(delta)
        self._ws.update_cell(linha_fatura, 4, novo_valor)
        return novo_valor

    # ------------------------------------------------------------------ #
    # Potinhos de Reservas/Contas
    # ------------------------------------------------------------------ #

    def sincronizar_potinhos_carteira(self) -> list[AjusteCarteira]:
        """
        Varre a aba Carteira e, para cada linha de potinho (categoria
        "reserva" ou "conta") onde "alocado" difere de "alocado_processado",
        ajusta o Sobrando pela diferença e sincroniza as duas colunas.

        Cobre os três casos de edição manual direto na planilha:
        - Potinho novo, criado com "alocado" != 0 -> conta como alocação
          nova (alocado_processado ausente é tratado como 0).
        - "alocado" aumentado num potinho existente -> desconta a diferença
          do Sobrando.
        - "alocado" diminuído -> devolve a diferença para o Sobrando.

        Linhas de controle (Total, Sobrando) são ignoradas. Potinhos
        removidos (linha apagada) simplesmente não aparecem mais - nenhum
        ajuste retroativo é feito sobre eles.

        Retorna a lista de ajustes feitos, para log/confirmação no bot.
        """
        registros = self._ws.get_all_records(value_render_option="UNFORMATTED_VALUE")

        cabecalho = self._ws.row_values(1)
        col_alocado = cabecalho.index("alocado") + 1
        col_alocado_processado = cabecalho.index("alocado_processado") + 1

        ajustes: list[AjusteCarteira] = []
        for i, r in enumerate(registros, start=2):  # +2: linha 1 é cabeçalho
            categoria = str(r.get("categoria", "")).strip().lower()
            if categoria not in CATEGORIAS_POTINHO:
                continue

            alocado = float(r.get("alocado", 0) or 0)
            alocado_processado_raw = r.get("alocado_processado", "")
            alocado_processado = float(alocado_processado_raw or 0)

            delta = round(alocado - alocado_processado, 2)
            if delta == 0:
                continue

            novo_sobrando = self.ajustar_sobrando(-delta)
            self._ws.update_cell(i, col_alocado_processado, alocado)

            ajustes.append(AjusteCarteira(
                categoria=categoria,
                nome=r.get("nome", ""),
                delta_alocado=delta,
                novo_sobrando=novo_sobrando,
            ))

        return ajustes

    def listar_potinhos_carteira(self) -> list[dict]:
        """
        Retorna os potinhos de Reserva/Conta atuais (categoria, nome, meta,
        alocado) - útil para o bot mostrar um resumo sem precisar abrir a
        planilha, ou para conferir o que existe antes de decidir alocar algo.
        """
        registros = self._ws.get_all_records(value_render_option="UNFORMATTED_VALUE")
        return [
            {
                "categoria": r.get("categoria"),
                "nome": r.get("nome"),
                "meta": r.get("meta"),
                "alocado": r.get("alocado"),
            }
            for r in registros
            if str(r.get("categoria", "")).strip().lower() in CATEGORIAS_POTINHO
        ]