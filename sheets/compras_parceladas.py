"""
compras_parceladas.py

Camada 3: potinhos de compra parcelada (aba "Compras_Parceladas") e o
sistema de crédito que os acompanha - ver a regra de negócio em
processar_parcela_vencida().

Depende de uma função `ajustar_sobrando` (normalmente
CarteiraManager.ajustar_sobrando, injetada pelo orquestrador) para
descontar/devolver valores do Sobrando quando o crédito do potinho não
é suficiente. Este módulo nunca acessa a aba Carteira diretamente.

O worksheet é resolvido UMA VEZ no __init__ (via abrir_worksheet_limitado,
que já aplica o RateLimiter compartilhado) e reutilizado (self._ws) em
vez de chamado de novo a cada método - cada chamada a
spreadsheet.worksheet(nome) é, ela própria, uma requisição de leitura à
API (fetch_sheet_metadata) para resolver o nome pelo índice de abas.

IMPORTANTE sobre leitura de números do Sheets: todas as leituras usam
get_all_records(value_render_option="UNFORMATTED_VALUE"). Sem isso, o
gspread devolve o valor FORMATADO da célula - numa planilha em pt-BR
isso vem como string "47,30" (vírgula), e float("47,30") estoura
ValueError. Esse erro subia silenciosamente até o try/except genérico
do job periódico no pipeline.py, fazendo a sincronização falhar sem
avisar ninguém. UNFORMATTED_VALUE devolve o número Python de verdade
(47.3), independente do locale da planilha.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

import gspread

from .config import ABA_COMPRAS_PARCELADAS, ResultadoParcela
from .fatura import _somar_mes
from .rate_limit import RateLimiter, abrir_worksheet_limitado

logger = logging.getLogger(__name__)


def _para_bool(valor) -> bool:
    """
    Interpreta um valor de checkbox/booleano vindo do Sheets. Com
    value_render_option="UNFORMATTED_VALUE" isso já vem como True/False
    nativo na grande maioria dos casos, mas mantemos o fallback de string
    (incluindo a variante localizada "verdadeiro") para planilhas onde a
    célula é só texto em vez de checkbox de verdade.
    """
    if isinstance(valor, bool):
        return valor
    return str(valor).strip().lower() in ("true", "1", "sim", "verdadeiro")


class ComprasParceladasManager:
    def __init__(
        self,
        spreadsheet: gspread.Spreadsheet,
        limiter: RateLimiter,
        ajustar_sobrando: Callable[[float], float],
    ):
        self._sh = spreadsheet
        self._ws = abrir_worksheet_limitado(spreadsheet, ABA_COMPRAS_PARCELADAS, limiter)
        self._ajustar_sobrando = ajustar_sobrando

    def criar_potinho_compra(
        self,
        nome_compra: str,
        valor_total: float,
        num_parcelas: int,
        credito_inicial: float = 0.0,
        alocacao_automatica: bool = True,
        ciclo_inicial: str = "",
    ) -> None:
        """
        Cria um novo potinho de compra parcelada.

        credito_inicial: quanto já foi alocado do Sobrando na hora da compra
        (pode ser 0, parcial, ou o valor_total inteiro - ver Exemplo A/B do
        planejamento).

        ciclo_inicial: mes_referencia ("YYYY-MM") do ciclo de fatura em que
        a primeira parcela deve ser cobrada - normalmente calculado a partir
        da data do comprovante via fatura.calcular_ciclo_referencia(). Deixe
        vazio se ainda não souber o ciclo (o potinho fica de fora do
        processamento automático por ciclo até você preencher).
        """
        self.criar_potinhos_em_lote([{
            "nome_compra": nome_compra,
            "valor_total": valor_total,
            "num_parcelas": num_parcelas,
            "credito_inicial": credito_inicial,
            "alocacao_automatica": alocacao_automatica,
            "ciclo_inicial": ciclo_inicial,
        }])

    def criar_potinhos_em_lote(self, potinhos: list[dict]) -> None:
        """
        Versão em lote de criar_potinho_compra: monta todas as linhas e
        grava com uma única chamada append_rows, em vez de um append_row
        (uma requisição de escrita cada) por compra parcelada. Pensada
        para o job de drenagem da fila_sheets do pipeline.py.

        Cada dict aceita as mesmas chaves de criar_potinho_compra:
        nome_compra, valor_total, num_parcelas, credito_inicial (default
        0.0), alocacao_automatica (default True), ciclo_inicial (default
        "").

        PROTEÇÃO CONTRA DUPLICATA: mesma lógica de
        TransacoesManager.registrar_transacoes_em_lote (ver lá o porquê),
        mas aqui não dá pra usar "nome_compra" sozinho como chave - duas
        compras diferentes na mesma loja (ex: dois pedidos na Amazon em
        meses diferentes) têm o mesmo nome_compra legitimamente. Em vez
        disso, a chave de deduplicação é a combinação (nome_compra,
        valor_total, num_parcelas, ciclo_inicial): um retry de verdade
        reenvia exatamente os mesmos quatro valores, enquanto duas
        compras genuinamente diferentes tendem a diferir em pelo menos
        um deles (valor, parcelamento ou o ciclo em que a primeira
        parcela cai).
        """
        if not potinhos:
            return

        registros_existentes = self._ws.get_all_records(value_render_option="UNFORMATTED_VALUE")
        chaves_existentes = {
            (
                str(r.get("nome_compra", "")).strip(),
                round(float(r.get("valor_total", 0) or 0), 2),
                int(r.get("num_parcelas", 0) or 0),
                str(r.get("ciclo_inicial", "")).strip(),
            )
            for r in registros_existentes
        }

        linhas = []
        for p in potinhos:
            valor_total = p["valor_total"]
            num_parcelas = p["num_parcelas"]
            credito_inicial = p.get("credito_inicial", 0.0)
            alocacao_automatica = p.get("alocacao_automatica", True)
            ciclo_inicial = p.get("ciclo_inicial", "")

            chave = (str(p["nome_compra"]).strip(), round(valor_total, 2), num_parcelas, ciclo_inicial.strip())
            if chave in chaves_existentes:
                logger.warning(
                    "Potinho '%s' (%dx de %.2f, ciclo %s) já existe em Compras_Parceladas "
                    "(retry de um envio anterior) - pulando para não duplicar.",
                    p["nome_compra"], num_parcelas, valor_total, ciclo_inicial,
                )
                continue

            valor_parcela = round(valor_total / num_parcelas, 2)

            if credito_inicial > 0:
                self._ajustar_sobrando(-credito_inicial)

            linhas.append([
                p["nome_compra"],
                valor_total,
                num_parcelas,
                valor_parcela,
                credito_inicial,
                0,  # parcelas_pagas
                alocacao_automatica,
                "ativo",
                credito_inicial,  # credito_processado - já sincronizado, veio de nós mesmos
                ciclo_inicial,
            ])
            # protege também contra duplicata DENTRO do mesmo lote (dois
            # itens do próprio pipeline.py com a mesma chave)
            chaves_existentes.add(chave)

        if not linhas:
            return

        # RAW impede que um ciclo como "2026-09" seja convertido pelo
        # Google Sheets em data serializada.
        self._ws.append_rows(linhas, value_input_option="RAW")

    def listar_compras(self) -> list[dict]:
        """Retorna as compras para montar a previsão dos ciclos de fatura."""
        return self._ws.get_all_records(value_render_option="UNFORMATTED_VALUE")

    def processar_parcela_vencida(self, nome_compra: str, valor_parcela: Optional[float] = None) -> ResultadoParcela:
        """
        Aplica a regra de negócio do planejamento:

            se saldo_credito >= valor_parcela:
                abate valor_parcela do saldo_credito
            senão:
                falta = valor_parcela - saldo_credito
                zera saldo_credito
                desconta falta do Sobrando   (obrigatório)

        Se o potinho tiver alocacao_automatica=False, a parcela ainda é registrada
        na aba Transacoes por quem chamar esta função, mas aqui não mexemos em
        saldo_credito nem em Sobrando - apenas retornamos o estado sem alterações.
        """
        registros = self._ws.get_all_records(value_render_option="UNFORMATTED_VALUE")

        linha_idx = None
        registro = None
        for i, r in enumerate(registros, start=2):  # +2: linha 1 é cabeçalho
            if r["nome_compra"] == nome_compra and str(r["status"]).strip().lower() == "ativo":
                linha_idx = i
                registro = r
                break

        if registro is None:
            raise ValueError(f"Potinho ativo '{nome_compra}' não encontrado.")

        valor_parcela = valor_parcela if valor_parcela is not None else float(registro["valor_parcela"])
        saldo_credito = float(registro["saldo_credito"] or 0)
        parcelas_pagas = int(registro["parcelas_pagas"] or 0)
        num_parcelas = int(registro["num_parcelas"])
        alocacao_automatica = _para_bool(registro["alocacao_automatica"])

        if not alocacao_automatica:
            # Lembrete manual: não mexe em crédito nem em Sobrando.
            return ResultadoParcela(
                nome_compra=nome_compra,
                valor_parcela=valor_parcela,
                abatido_do_credito=0.0,
                descontado_do_sobrando=0.0,
                saldo_credito_restante=saldo_credito,
                potinho_fechado=False,
            )

        if saldo_credito >= valor_parcela:
            abatido = valor_parcela
            descontado = 0.0
            novo_saldo_credito = round(saldo_credito - valor_parcela, 2)
        else:
            abatido = saldo_credito
            descontado = round(valor_parcela - saldo_credito, 2)
            novo_saldo_credito = 0.0
            self._ajustar_sobrando(-descontado)

        nova_qtd_pagas = parcelas_pagas + 1
        potinho_fechado = nova_qtd_pagas >= num_parcelas
        novo_status = "quitado" if potinho_fechado else "ativo"

        # Atualiza a linha do potinho (colunas: E=saldo_credito, F=parcelas_pagas,
        # H=status, I=credito_processado). credito_processado acompanha
        # saldo_credito aqui porque essa mudança já foi contabilizada no
        # Sobrando (ou não precisava ser, se veio do próprio crédito) -
        # assim o job de sincronização não reage a essa alteração de novo.
        self._ws.update_cell(linha_idx, 5, novo_saldo_credito)
        self._ws.update_cell(linha_idx, 6, nova_qtd_pagas)
        self._ws.update_cell(linha_idx, 8, novo_status)
        self._ws.update_cell(linha_idx, 9, novo_saldo_credito)

        return ResultadoParcela(
            nome_compra=nome_compra,
            valor_parcela=valor_parcela,
            abatido_do_credito=abatido,
            descontado_do_sobrando=descontado,
            saldo_credito_restante=novo_saldo_credito,
            potinho_fechado=potinho_fechado,
        )

    def processar_ciclo(self, mes_referencia: str) -> list[ResultadoParcela]:
        """
        Chamado pelo SheetsManager quando um ciclo de fatura é marcado
        como pago (ver fatura.py): cobra uma parcela (via
        processar_parcela_vencida) de cada potinho ativo cujo PRÓXIMO
        ciclo devido seja exatamente este mes_referencia.

        O próximo ciclo devido de um potinho é calculado como
        ciclo_inicial + parcelas_pagas meses - ou seja, não é só "esse
        potinho já começou", é "esse potinho ainda não teve a parcela
        deste ciclo específico cobrada". Isso importa porque
        processar_ciclo() pode, em tese, ser chamado duas vezes para o
        mesmo mes_referencia (ex: a cobrança teve sucesso mas
        marcar_ciclo_processado falhou logo depois por um erro de rede,
        e o job diário seguinte vê o ciclo ainda como "não processado" e
        tenta de novo) - sem essa checagem, a segunda chamada cobraria a
        mesma parcela uma segunda vez, descontando em dobro do
        crédito/Sobrando. Com ela, a segunda chamada não encontra mais
        nenhum potinho cujo "próximo devido" seja esse ciclo (já
        avançou para o ciclo seguinte na primeira chamada) e não faz
        nada - processar_ciclo() fica seguro para repetir.

        Potinhos sem ciclo_inicial preenchido (legado, criados antes
        desse controle existir, ou migrados de uma planilha antiga) são
        ignorados aqui - processe-os manualmente via
        processar_parcela_vencida, ou preencha ciclo_inicial na planilha
        se quiser incluí-los no processamento automático.
        """
        registros = self._ws.get_all_records(value_render_option="UNFORMATTED_VALUE")

        resultados = []
        for r in registros:
            if str(r.get("status", "")).strip().lower() != "ativo":
                continue
            ciclo_inicial = str(r.get("ciclo_inicial", "")).strip()
            if not ciclo_inicial:
                continue
            try:
                ano, mes = (int(parte) for parte in ciclo_inicial.split("-"))
                parcelas_pagas = int(r.get("parcelas_pagas") or 0)
            except (TypeError, ValueError):
                continue
            ano_devido, mes_devido = _somar_mes(ano, mes, parcelas_pagas)
            proximo_ciclo_devido = f"{ano_devido:04d}-{mes_devido:02d}"
            if proximo_ciclo_devido != mes_referencia:
                continue  # esse potinho não tem parcela devida NESTE ciclo específico
            resultado = self.processar_parcela_vencida(r["nome_compra"])
            resultados.append(resultado)
        return resultados

    def sincronizar_creditos_manuais(self) -> list[dict]:
        """
        Varre os potinhos ativos em Compras_Parceladas e, para cada um onde
        saldo_credito difere de credito_processado, ajusta o Sobrando pela
        diferença e sincroniza as duas colunas de novo.

        - Você aumentou saldo_credito na mão (ex: 0 -> 50) -> desconta 50 do
          Sobrando agora.
        - Você diminuiu saldo_credito na mão (ex: 50 -> 20) -> devolve 30
          para o Sobrando (você está "desalocando" aquele valor).

        Mudanças feitas pelo próprio sistema (criar_potinho_compra,
        processar_parcela_vencida) já deixam as duas colunas iguais, então
        não são pegas aqui de novo - só reage a edição manual na planilha.

        Retorna a lista de ajustes feitos, para log/confirmação.
        """
        registros = self._ws.get_all_records(value_render_option="UNFORMATTED_VALUE")

        ajustes = []
        for i, r in enumerate(registros, start=2):  # +2: linha 1 é cabeçalho
            if str(r.get("status", "")).strip().lower() != "ativo":
                continue

            saldo_credito = float(r.get("saldo_credito", 0) or 0)
            credito_processado = float(r.get("credito_processado", 0) or 0)
            delta = round(saldo_credito - credito_processado, 2)

            if delta == 0:
                continue

            novo_sobrando = self._ajustar_sobrando(-delta)
            self._ws.update_cell(i, 9, saldo_credito)  # credito_processado alcança saldo_credito

            ajustes.append({
                "nome_compra": r.get("nome_compra"),
                "delta_alocado": delta,
                "novo_sobrando": novo_sobrando,
            })

        return ajustes