"""
sheets_manager.py

Orquestrador da integração com o Google Sheets para o gestor financeiro
automatizado. Substitui a planilha Excel local (Carteira.xlsx) por uma
estrutura em camadas na nuvem, evitando o problema de arquivo local
travando/corrompendo quando o script roda em background com o usuário
fora de casa.

Este módulo só cuida de autenticação, abertura da planilha e delegação -
a lógica de cada aba/etapa mora em seu próprio módulo:

    config.py              - constantes e dataclasses compartilhadas
    sheets_setup.py        - criação/migração das abas (EstruturaPlanilha)
    transacoes.py          - log bruto de transações (TransacoesManager)
    compras_parceladas.py  - potinhos de compra parcelada + crédito (ComprasParceladasManager)
    carteira.py            - Total/Sobrando + potinhos de Reservas/Contas (CarteiraManager)
    fatura.py              - ciclo mensal do cartão (FaturaManager)

Cada um dos managers acima resolve seu worksheet (self._ws) uma única
vez, no próprio __init__, através de abrir_worksheet_limitado (ver
rate_limit.py) - o mesmo RateLimiter, criado aqui e repassado a cada
manager, é compartilhado por toda a integração: qualquer chamada à API
do Sheets, de qualquer manager, passa por ele antes de sair, então o
limite (por padrão, um pouco abaixo dos 60/min que o Google libera por
usuário) vale para o conjunto de todas as abas, não por aba isolada.

EstruturaPlanilha e FaturaManager ainda NÃO passam pelo RateLimiter (os
módulos sheets_setup.py e fatura.py não foram revisados ainda) - se
esses dois ficarem responsáveis por picos de chamadas no futuro, vale
migrá-los para o mesmo padrão.

Uso típico a partir do pipeline.py (a API pública não muda em relação à
versão anterior de um arquivo só):

    from sheets_manager import SheetsManager

    sm = SheetsManager(spreadsheet_id="...", credentials_path="credentials.json")
    sm.registrar_transacao(item="Mercado", valor_total=47.30, destino="Alimentação")

    # ao identificar uma compra parcelada nova, informe a data do comprovante
    # para que o ciclo de fatura correto seja calculado:
    sm.criar_potinho_compra("Notebook", valor_total=1200.0, num_parcelas=12, data_compra=data)

    # versões em lote (uma escrita só na API, em vez de uma por item) -
    # usadas pelo job de drenagem da fila_sheets do pipeline.py:
    sm.registrar_transacoes_em_lote([...])
    sm.criar_potinhos_em_lote([...])

    # a cada execução do job periódico (crédito/alocação manual), chame:
    ajustes = sm.sincronizar_tudo()

    # a cada execução do job diário (ciclo de fatura):
    sm.garantir_ciclo_atual()
    resultado = sm.processar_faturas_pendentes()
"""

from __future__ import annotations

from datetime import date
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

from .config import SCOPES, AjusteCarteira, ResultadoParcela
from .sheets_setup import EstruturaPlanilha
from .transacoes import TransacoesManager
from .compras_parceladas import ComprasParceladasManager
from .carteira import CarteiraManager
from .fatura import FaturaManager, calcular_ciclo_referencia
from .rate_limit import RateLimiter


class SheetsManager:
    """
    Orquestrador: autentica, abre a planilha, garante a estrutura das
    abas e repassa cada operação ao módulo responsável. Não contém regra
    de negócio própria.
    """

    def __init__(self, spreadsheet_id: str, credentials_path: str = "credentials.json"):
        creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
        self._client = gspread.authorize(creds)
        self._sh = self._client.open_by_key(spreadsheet_id)

        # Compartilhado por todos os managers abaixo - ver rate_limit.py.
        # 50/min fica um pouco abaixo da cota padrão do Google (60/min),
        # deixando margem para uso manual da planilha ao mesmo tempo.
        self._limiter = RateLimiter(max_requisicoes=50, janela_segundos=60.0)

        EstruturaPlanilha(self._sh).garantir_estrutura()

        self._carteira = CarteiraManager(self._sh, self._limiter)
        self._transacoes = TransacoesManager(self._sh, self._limiter)
        self._compras_parceladas = ComprasParceladasManager(
            self._sh, self._limiter, ajustar_sobrando=self._carteira.ajustar_sobrando
        )
        self._fatura = FaturaManager(self._sh)
        self._fatura.sincronizar_datas_ciclos()
        self.sincronizar_previsao_faturas()

    # ------------------------------------------------------------------ #
    # Transações (log bruto)
    # ------------------------------------------------------------------ #

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
        self._transacoes.registrar_transacao(
            item=item,
            valor_total=valor_total,
            destino=destino,
            parcelas=parcelas,
            valor_parcela=valor_parcela,
            status=status,
            data=data,
        )

    def registrar_transacoes_em_lote(self, transacoes: list[dict]) -> None:
        """
        Versão em lote de registrar_transacao - uma única escrita na aba
        Transacoes para todas as transações do lote, em vez de uma por
        item. Cada dict aceita as mesmas chaves de registrar_transacao
        (item, valor_total, destino, parcelas, valor_parcela, status,
        data).
        """
        self._transacoes.registrar_transacoes_em_lote(transacoes)

    # ------------------------------------------------------------------ #
    # Compras parceladas
    # ------------------------------------------------------------------ #

    def criar_potinho_compra(
        self,
        nome_compra: str,
        valor_total: float,
        num_parcelas: int,
        data_compra: Optional[date] = None,
        credito_inicial: float = 0.0,
        alocacao_automatica: bool = True,
    ) -> None:
        """
        data_compra: data do comprovante (extraída do OCR, ou informada por
        você). Usada para calcular automaticamente em qual ciclo de fatura
        (ciclo_inicial) a primeira parcela deve cair - ver fatura.py. Se
        omitida, o potinho fica sem ciclo_inicial e só pode ser processado
        manualmente via processar_parcela_vencida.
        """
        ciclo_inicial = calcular_ciclo_referencia(data_compra) if data_compra else ""
        self._compras_parceladas.criar_potinho_compra(
            nome_compra=nome_compra,
            valor_total=valor_total,
            num_parcelas=num_parcelas,
            credito_inicial=credito_inicial,
            alocacao_automatica=alocacao_automatica,
            ciclo_inicial=ciclo_inicial,
        )
        self.sincronizar_previsao_faturas()

    def criar_potinhos_em_lote(self, potinhos: list[dict]) -> None:
        """
        Versão em lote de criar_potinho_compra - uma única escrita na aba
        Compras_Parceladas para todas as compras parceladas do lote, e uma
        única atualização da previsão de fatura ao final (em vez de uma
        rodada de sincronizar_previsao_faturas por compra).

        Cada dict aceita: nome_compra, valor_total, num_parcelas,
        data_compra (opcional - usada para calcular ciclo_inicial, mesma
        regra de criar_potinho_compra), credito_inicial (default 0.0),
        alocacao_automatica (default True).
        """
        if not potinhos:
            return

        linhas = []
        for p in potinhos:
            data_compra = p.get("data_compra")
            ciclo_inicial = calcular_ciclo_referencia(data_compra) if data_compra else ""
            linhas.append({
                "nome_compra": p["nome_compra"],
                "valor_total": p["valor_total"],
                "num_parcelas": p["num_parcelas"],
                "credito_inicial": p.get("credito_inicial", 0.0),
                "alocacao_automatica": p.get("alocacao_automatica", True),
                "ciclo_inicial": ciclo_inicial,
            })

        self._compras_parceladas.criar_potinhos_em_lote(linhas)
        self.sincronizar_previsao_faturas()

    def processar_parcela_vencida(self, nome_compra: str, valor_parcela: Optional[float] = None) -> ResultadoParcela:
        return self._compras_parceladas.processar_parcela_vencida(nome_compra, valor_parcela)

    def sincronizar_creditos_manuais(self) -> list[dict]:
        return self._compras_parceladas.sincronizar_creditos_manuais()

    # ------------------------------------------------------------------ #
    # Carteira: Total/Sobrando + potinhos de Reservas/Contas
    # ------------------------------------------------------------------ #

    def sincronizar_potinhos_carteira(self) -> list[AjusteCarteira]:
        return self._carteira.sincronizar_potinhos_carteira()

    def listar_potinhos_carteira(self) -> list[dict]:
        return self._carteira.listar_potinhos_carteira()

    def get_sobrando(self) -> float:
        return self._carteira.get_sobrando()

    # ------------------------------------------------------------------ #
    # Fatura: ciclo mensal do cartão
    # ------------------------------------------------------------------ #

    def garantir_ciclo_atual(self) -> None:
        """Garante que a linha do ciclo corrente (e do próximo) existe na aba Fatura."""
        self._fatura.garantir_ciclo_atual()

    def sincronizar_previsao_faturas(self) -> None:
        """Atualiza Fatura e reserva, na Carteira, o total do ciclo em aberto."""
        ciclo_atual = calcular_ciclo_referencia(date.today())
        self._fatura.remover_ciclos_pendentes_anteriores(ciclo_atual)
        self._fatura.sincronizar_valores_previstos(
            self._compras_parceladas.listar_compras(), ciclo_minimo=ciclo_atual
        )
        self._carteira.sincronizar_fatura_atual(
            self._fatura.valor_previsto(ciclo_atual)
        )

    def processar_faturas_pendentes(self) -> list[dict]:
        """
        Varre a aba Fatura por ciclos marcados como "paga" ainda não
        processados (em ordem crescente de mes_referencia) e, para cada
        um, cobra uma parcela de cada potinho ativo elegível. Marca o
        ciclo como processado ao final. Retorna um resumo por ciclo, para
        log/confirmação.
        """
        resultados = []
        for ciclo in self._fatura.ciclos_pendentes_de_processamento():
            parcelas = self._compras_parceladas.processar_ciclo(ciclo["mes_referencia"])
            self._fatura.marcar_ciclo_processado(ciclo["linha"])
            resultados.append({
                "mes_referencia": ciclo["mes_referencia"],
                "parcelas_processadas": parcelas,
            })
        return resultados

    # ------------------------------------------------------------------ #
    # Conveniência: job periódico
    # ------------------------------------------------------------------ #

    def sincronizar_tudo(self) -> dict:
        """
        Conveniência para o job periódico (crédito/alocação manual) do
        pipeline.py: roda as duas sincronizações manuais (Compras_Parceladas
        e Carteira) numa só chamada. Não mexe em Fatura - isso é
        garantir_ciclo_atual()/processar_faturas_pendentes(), chamadas pelo
        job diário separado.
        """
        return {
            "total": self._carteira.sincronizar_total(),
            "compras_parceladas": self.sincronizar_creditos_manuais(),
            "carteira": self.sincronizar_potinhos_carteira(),
        }