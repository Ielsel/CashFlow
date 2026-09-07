"""
fatura.py

Camada de controle do ciclo da fatura do cartão (aba "Fatura").

Em vez de cada potinho de compra parcelada ter sua própria data de
vencimento isolada, as parcelas são cobradas em bloco quando você marca
um ciclo mensal como "paga" na planilha. Isso reflete como o cartão de
crédito funciona de verdade: uma fatura fecha, vence, e só quando você
confirma que pagou é que as parcelas daquele ciclo (e de qualquer ciclo
anterior ainda pendente) são de fato abatidas dos potinhos / descontadas
do Sobrando.

Fluxo (ver pipeline.py):
    1. Um job diário chama garantir_ciclo_atual(), que cria a linha do
       ciclo do mês corrente (e do próximo) na aba Fatura, com status
       "pendente", caso ainda não exista.
    2. Você edita manualmente a coluna "status" de uma linha para "paga"
       quando pagar a fatura.
    3. O mesmo job diário chama sheets.processar_faturas_pendentes(),
       que varre por linhas "paga" ainda não processadas
       (ciclo_processado=False), em ordem crescente de mes_referencia, e
       para cada uma chama ComprasParceladasManager.processar_ciclo(...)
       - que cobra uma parcela de cada potinho ativo elegível.

Se você pular um mês (não marcar como paga), nada é descontado - a
parcela dele fica represada. Quando você finalmente marcar um ciclo
posterior como "paga", os ciclos pendentes anteriores são processados
primeiro, em ordem - as parcelas se acumulam: marcar dois ciclos
atrasados como pagos processa duas parcelas de cada potinho ativo, uma
de cada ciclo, no mesmo lote.

ATENÇÃO - risco de cobrança em duplicidade, e como foi resolvido:
processar_faturas_pendentes() (em sheets_manager.py) chama
processar_ciclo() e só DEPOIS chama marcar_ciclo_processado(). Se a
cobrança das parcelas tiver sucesso mas marcar_ciclo_processado falhar
(ex: erro de rede logo em seguida), o ciclo continua aparecendo como
"paga" e não processado - a próxima execução do job diário chamaria
processar_ciclo() de novo para o mesmo mes_referencia. A proteção não
mora aqui, mas em compras_parceladas.py: processar_ciclo() só cobra a
parcela de um potinho se este mes_referencia for exatamente o "próximo
ciclo devido" daquele potinho (ciclo_inicial + parcelas_pagas meses) -
uma segunda chamada para o mesmo ciclo não encontra mais nenhum potinho
nessa condição (já avançou na primeira chamada) e não faz nada.
"""

from __future__ import annotations

from datetime import date, timedelta

import gspread

from .config import ABA_FATURA, DIA_FECHAMENTO_FATURA, DIA_VENCIMENTO_FATURA


def _proximo_dia_util(d: date) -> date:
    """Empurra sábado/domingo para a segunda-feira seguinte."""
    while d.weekday() >= 5:  # 5=sábado, 6=domingo
        d += timedelta(days=1)
    return d


def _somar_mes(ano: int, mes: int, quantidade: int = 1) -> tuple[int, int]:
    total = (mes - 1) + quantidade
    return ano + total // 12, total % 12 + 1


def _coluna_a1(coluna: int) -> str:
    """Converte índice de coluna (1-based) para letra A1 do Sheets."""
    resultado = ""
    while coluna:
        coluna, resto = divmod(coluna - 1, 26)
        resultado = chr(65 + resto) + resultado
    return resultado


def _alocada_na_fatura(valor) -> bool:
    """Interpreta a coluna alocacao_automatica da compra parcelada."""
    if isinstance(valor, bool):
        return valor
    return str(valor).strip().lower() not in ("false", "0", "nao", "não", "nao")


def calcular_ciclo_referencia(data_compra: date, dia_fechamento: int = DIA_FECHAMENTO_FATURA) -> str:
    """
    Dada a data de uma compra, retorna o mes_referencia ("YYYY-MM") do
    ciclo de fatura em que a primeira parcela dessa compra deve cair.

    Compras ANTES do dia de fechamento entram no ciclo do mês corrente;
    NO dia de fechamento ou depois dele, já entram no ciclo do mês
    seguinte - uma compra feita no próprio dia do fechamento é tarde
    demais pra entrar na fatura que fecha nesse dia (ex: fechamento dia
    20, compra dia 20 de agosto -> cai na fatura que fecha dia 20 de
    setembro, não na de agosto). Por isso a comparação é "<", não "<=".
    """
    if data_compra.day < dia_fechamento:
        ano, mes = data_compra.year, data_compra.month
    else:
        ano, mes = _somar_mes(data_compra.year, data_compra.month, 1)
    return f"{ano:04d}-{mes:02d}"


def calcular_datas_ciclo(
    mes_referencia: str,
    dia_fechamento: int = DIA_FECHAMENTO_FATURA,
    dia_vencimento: int = DIA_VENCIMENTO_FATURA,
) -> tuple[date, date]:
    """
    Calcula a data de fechamento e a data de vencimento (nominal, já
    empurrada para o próximo dia útil se cair em fim de semana) de um
    ciclo, a partir do mes_referencia ("YYYY-MM").
    """
    ano, mes = (int(p) for p in mes_referencia.split("-"))
    data_fechamento = date(ano, mes, dia_fechamento)

    if dia_vencimento < dia_fechamento:
        ano_v, mes_v = _somar_mes(ano, mes, 1)
    else:
        ano_v, mes_v = ano, mes
    data_vencimento = _proximo_dia_util(date(ano_v, mes_v, dia_vencimento))

    return data_fechamento, data_vencimento


class FaturaManager:
    def __init__(self, spreadsheet: gspread.Spreadsheet):
        self._sh = spreadsheet

    def garantir_ciclo(self, mes_referencia: str) -> None:
        """Cria a linha desse ciclo na aba Fatura se ainda não existir. Idempotente."""
        ws = self._sh.worksheet(ABA_FATURA)
        existentes = ws.col_values(1)[1:]  # coluna mes_referencia, sem cabeçalho
        if mes_referencia in existentes:
            return
        data_fechamento, data_vencimento = calcular_datas_ciclo(mes_referencia)
        ws.append_row([
            mes_referencia,
            data_fechamento.isoformat(),
            data_vencimento.isoformat(),
            "pendente",
            False,
            0,
        ])

    def sincronizar_valores_previstos(
        self, compras: list[dict], ciclo_minimo: str | None = None
    ) -> None:
        """
        Agenda cada parcela nos seus respectivos ciclos e recalcula o valor
        previsto de cada linha da aba Fatura. Quando ``ciclo_minimo`` é
        informado, parcelas de ciclos já passados não são listadas: ao enviar
        hoje um comprovante antigo, aparecem apenas as parcelas ainda futuras.

        A aba continua sendo a fonte de controle do pagamento (status e
        ciclo_processado), mas agora também mostra quanto há para pagar em
        cada mês. Recalcular do zero torna a operação idempotente: reiniciar
        o bot ou sincronizar novamente não duplica parcelas.
        """
        totais_por_ciclo: dict[str, float] = {}
        for compra in compras:
            # A flag controla se a compra compõe ou não a fatura. Compras
            # desmarcadas continuam registradas nas demais abas, mas não
            # reservam saldo nem entram em valor_previsto.
            if not _alocada_na_fatura(compra.get("alocacao_automatica", True)):
                continue
            ciclo_inicial = str(compra.get("ciclo_inicial", "")).strip()
            if not ciclo_inicial:
                continue
            try:
                ano, mes = (int(parte) for parte in ciclo_inicial.split("-"))
                num_parcelas = int(compra.get("num_parcelas") or 0)
                valor_parcela = float(compra.get("valor_parcela") or 0)
            except (TypeError, ValueError):
                continue

            if num_parcelas < 1 or valor_parcela <= 0:
                continue
            for indice in range(num_parcelas):
                ano_ciclo, mes_ciclo = _somar_mes(ano, mes, indice)
                ciclo = f"{ano_ciclo:04d}-{mes_ciclo:02d}"
                if ciclo_minimo and ciclo < ciclo_minimo:
                    continue
                totais_por_ciclo[ciclo] = round(
                    totais_por_ciclo.get(ciclo, 0.0) + valor_parcela, 2
                )

        ws = self._sh.worksheet(ABA_FATURA)
        # Lê a coluna de ciclos uma única vez. A versão anterior chamava
        # garantir_ciclo() para cada parcela e fazia uma leitura remota por
        # ciclo, esgotando facilmente a cota do Google Sheets.
        existentes = set(ws.col_values(1)[1:])
        for ciclo in totais_por_ciclo:
            if ciclo in existentes:
                continue
            data_fechamento, data_vencimento = calcular_datas_ciclo(ciclo)
            ws.append_row([
                ciclo,
                data_fechamento.isoformat(),
                data_vencimento.isoformat(),
                "pendente",
                False,
                0,
            ])
            existentes.add(ciclo)

        cabecalho = ws.row_values(1)
        coluna_valor = cabecalho.index("valor_previsto") + 1
        registros = ws.get_all_records(value_render_option="UNFORMATTED_VALUE")
        for linha, registro in enumerate(registros, start=2):
            ciclo = str(registro.get("mes_referencia", "")).strip()
            valor_atual = float(registro.get("valor_previsto", 0) or 0)
            novo_valor = totais_por_ciclo.get(ciclo, 0.0)
            if round(valor_atual, 2) != novo_valor:
                ws.update_cell(linha, coluna_valor, novo_valor)

    def remover_ciclos_pendentes_anteriores(self, ciclo_minimo: str) -> int:
        """Remove apenas previsões pendentes de ciclos anteriores ao atual.

        Ciclos pagos ou já processados são histórico financeiro e nunca são
        apagados. Esta limpeza serve para previsões retroativas criadas ao
        enviar agora um comprovante de compra antiga.
        """
        ws = self._sh.worksheet(ABA_FATURA)
        registros = ws.get_all_records(value_render_option="UNFORMATTED_VALUE")
        linhas_para_remover = []
        for linha, registro in enumerate(registros, start=2):
            ciclo = str(registro.get("mes_referencia", "")).strip()
            status = str(registro.get("status", "")).strip().lower()
            processado = bool(registro.get("ciclo_processado"))
            if ciclo < ciclo_minimo and status == "pendente" and not processado:
                linhas_para_remover.append(linha)

        for linha in reversed(linhas_para_remover):
            ws.delete_rows(linha)
        return len(linhas_para_remover)

    def valor_previsto(self, mes_referencia: str) -> float:
        """Retorna o total previsto de um ciclo, ou zero se ele não existir."""
        ws = self._sh.worksheet(ABA_FATURA)
        for registro in ws.get_all_records(value_render_option="UNFORMATTED_VALUE"):
            if str(registro.get("mes_referencia", "")).strip() == mes_referencia:
                return round(float(registro.get("valor_previsto", 0) or 0), 2)
        return 0.0

    def garantir_ciclo_atual(self) -> None:
        """
        Garante que existem linhas para o ciclo do mês corrente e do
        próximo na aba Fatura, para você sempre ter o ciclo em aberto
        visível pra marcar como pago quando chegar a hora.
        """
        hoje = date.today()
        ciclo_atual = calcular_ciclo_referencia(hoje)
        self.garantir_ciclo(ciclo_atual)

        ano, mes = (int(p) for p in ciclo_atual.split("-"))
        ano_prox, mes_prox = _somar_mes(ano, mes, 1)
        self.garantir_ciclo(f"{ano_prox:04d}-{mes_prox:02d}")

    def sincronizar_datas_ciclos(self) -> None:
        """Recalcula fechamento e vencimento dos ciclos já criados."""
        ws = self._sh.worksheet(ABA_FATURA)
        cabecalho = ws.row_values(1)
        col_fechamento = cabecalho.index("data_fechamento") + 1
        col_vencimento = cabecalho.index("data_vencimento") + 1

        atualizacoes = []
        for linha, registro in enumerate(
            ws.get_all_records(value_render_option="UNFORMATTED_VALUE"), start=2
        ):
            ciclo = str(registro.get("mes_referencia", "")).strip()
            try:
                data_fechamento, data_vencimento = calcular_datas_ciclo(ciclo)
            except (TypeError, ValueError):
                continue  # ignora linhas manuais que não sejam YYYY-MM

            if str(registro.get("data_fechamento", "")) != data_fechamento.isoformat():
                atualizacoes.append({
                    "range": f"{_coluna_a1(col_fechamento)}{linha}",
                    "values": [[data_fechamento.isoformat()]],
                })
            if str(registro.get("data_vencimento", "")) != data_vencimento.isoformat():
                atualizacoes.append({
                    "range": f"{_coluna_a1(col_vencimento)}{linha}",
                    "values": [[data_vencimento.isoformat()]],
                })

        if atualizacoes:
            ws.batch_update(atualizacoes, value_input_option="RAW")

    def ciclos_pendentes_de_processamento(self) -> list[dict]:
        """
        Retorna, em ordem crescente de mes_referencia, os ciclos marcados
        como "paga" que ainda não foram processados (ciclo_processado
        != True), já com o número da linha na planilha.
        """
        ws = self._sh.worksheet(ABA_FATURA)
        registros = ws.get_all_records(value_render_option="UNFORMATTED_VALUE")

        pendentes = []
        for i, r in enumerate(registros, start=2):  # +2: linha 1 é cabeçalho
            status = str(r.get("status", "")).strip().lower()
            ja_processado = bool(r.get("ciclo_processado"))
            if status == "paga" and not ja_processado:
                pendentes.append({"linha": i, "mes_referencia": str(r.get("mes_referencia", ""))})

        pendentes.sort(key=lambda c: c["mes_referencia"])
        return pendentes

    def marcar_ciclo_processado(self, linha: int) -> None:
        ws = self._sh.worksheet(ABA_FATURA)
        cabecalho = ws.row_values(1)
        col = cabecalho.index("ciclo_processado") + 1
        ws.update_cell(linha, col, True)