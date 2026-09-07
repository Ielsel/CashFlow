"""
Pipeline consolidado, etapas 1 + 2 + 5 (parcial):

1. Bot do Telegram recebe a foto, salva em cupons_recebidos/ e registra
   no SQLite com status "pendente"
2. Um job periódico (a cada poucos segundos, via JobQueue do próprio
   python-telegram-bot) verifica o banco por imagens pendentes. Só
   quando encontra alguma é que o Ollama/GLM-OCR é acionado - o modelo
   não fica sendo chamado à toa quando não há nada novo. Além disso,
   cada chamada usa keep_alive=0, então o modelo é descarregado da
   VRAM assim que a resposta termina, em vez de ficar ocupando memória
   por até 5 minutos (padrão do Ollama) sem uso.
3. Resultado do OCR salvo em textos_extraidos/, status atualizado
   para "processado" (ou "erro", se falhar)
4. Se o Google Sheets estiver configurado (SPREADSHEET_ID no .env), o
   resultado do OCR é gravado primeiro na fila_sheets do SQLite (fonte
   de verdade local) - a escrita de verdade na planilha só acontece
   depois, no job de drenagem (item 5 abaixo). A extração de item/
   categoria de verdade ainda é a Etapa 3 (Fase 4, com Qwen), que ainda
   não foi implementada. Por enquanto só o valor total, as parcelas e a
   data são extraídos do texto do OCR via regex, como melhor esforço.
5. Um job de drenagem varre a fila_sheets por itens "pendente" e manda
   pro Sheets em lote (uma chamada para transações, outra para potinhos
   de compra parcelada), marcando cada item como "enviado" só depois de
   confirmar sucesso. Cada chamada à API do Sheets, de qualquer parte
   do pipeline, passa por um RateLimiter compartilhado (ver
   sheets/rate_limit.py) que fica um pouco abaixo da cota do Google -
   por isso a drenagem pode rodar com frequência sem risco de estourar
   a cota, mesmo com uma fila grande acumulada. Como o estado "pendente
   /enviado" mora no SQLite (não em memória), um restart do pipeline
   antes do envio não perde o dado - ele continua "pendente" e é
   drenado normalmente na próxima execução.
6. Um segundo job periódico varre a planilha (Compras_Parceladas e
   Carteira) por alocações feitas manualmente por você - crédito de
   compra parcelada e potinhos de Reserva/Conta - e ajusta o Sobrando
   automaticamente.
7. Um terceiro job, diário, garante que a linha do ciclo de fatura
   corrente existe na aba Fatura, e processa qualquer ciclo que você
   tenha marcado como "paga" - cobrando as parcelas do(s) potinho(s)
   ativo(s) daquele ciclo (ver sheets/fatura.py para a regra completa,
   incluindo o comportamento de "acumular" ciclos pulados).

Este arquivo substitui bot_recebe_cupom.py e ocr_processa.py - os dois
antigos podem ser apagados.

A integração com o Google Sheets mora no pacote sheets/ (config.py,
sheets_setup.py, transacoes.py, compras_parceladas.py, carteira.py,
fatura.py e sheets_manager.py como orquestrador) - este arquivo só
consome SheetsManager, sem conhecer a estrutura interna do pacote.

Requisitos:
    1. Ollama instalado e rodando: https://ollama.com/download
    2. Modelo baixado uma vez:  ollama pull glm-ocr
    3. pip install -r requirements.txt

Configuração (.env):
    TELEGRAM_BOT_TOKEN=...
    SPREADSHEET_ID=...            (opcional - se ausente, integração com Sheets fica desligada)
    GOOGLE_CREDENTIALS_PATH=credentials.json   (opcional - esse é o padrão)

Também ajuste DIA_FECHAMENTO_FATURA e DIA_VENCIMENTO_FATURA em
sheets/config.py para bater com o dia de fechamento/vencimento real do
seu cartão.

Rodar:
    python pipeline.py
"""

import json
import logging
import re
import sqlite3
import unicodedata
from contextlib import closing
from datetime import date, datetime
from pathlib import Path
import asyncio

# load_dotenv() precisa rodar ANTES de importar qualquer coisa que leia
# variáveis de ambiente na hora do import (na versão anterior deste
# arquivo, o import do pacote "sheets" vinha antes do load_dotenv() -
# nesse projeto isso não chegava a causar bug porque sheets/config.py
# não lê variáveis de ambiente, mas é uma armadilha fácil de cair se
# isso mudar no futuro, então a ordem certa é: dotenv primeiro).
from dotenv import load_dotenv
load_dotenv()

import ollama
import os
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from sheets import SheetsManager

# --- Configuração ---------------------------------------------------

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID")
GOOGLE_CREDENTIALS_PATH = os.environ.get("GOOGLE_CREDENTIALS_PATH", "credentials.json")

MODEL_NAME = "glm-ocr"
PASTA_IMAGENS = Path("cupons_recebidos")
PASTA_TEXTOS = Path("textos_extraidos")
CAMINHO_DB = Path("pipeline.db")
INTERVALO_VERIFICACAO_SEGUNDOS = 15
INTERVALO_DRENAGEM_FILA_SEGUNDOS = 20  # varre a fila_sheets por itens pendentes e envia em lote
LIMITE_LOTE_DRENAGEM = 300  # no máx. essa quantidade de itens por chamada de drenagem, por tipo
INTERVALO_SYNC_MANUAL_SEGUNDOS = 30  # varre Compras_Parceladas e Carteira por alocações manuais
INTERVALO_SYNC_FATURA_SEGUNDOS = 24 * 60 * 60  # garante ciclo atual + processa fatura(s) paga(s)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# --- Sheets: conexão opcional --------------------------------------
# Se SPREADSHEET_ID não estiver no .env, ou a credencial não existir ainda,
# o pipeline continua funcionando normalmente (só OCR + SQLite), e a
# integração com o Sheets fica desligada até você terminar o setup do
# Google Cloud Console.

sheets: SheetsManager | None = None
if SPREADSHEET_ID:
    try:
        sheets = SheetsManager(
            spreadsheet_id=SPREADSHEET_ID,
            credentials_path=GOOGLE_CREDENTIALS_PATH,
        )
        logger.info("Integração com Google Sheets ativa (spreadsheet %s).", SPREADSHEET_ID)
    except Exception:
        logger.exception(
            "Não consegui conectar ao Google Sheets. Verifique SPREADSHEET_ID, "
            "%s e o compartilhamento da planilha com a conta de serviço. "
            "Seguindo sem integração por enquanto.",
            GOOGLE_CREDENTIALS_PATH,
        )
        sheets = None
else:
    logger.info("SPREADSHEET_ID não definido no .env - integração com Sheets desligada.")


# --- Banco de dados -------------------------------------------------

def iniciar_banco() -> None:
    with closing(sqlite3.connect(CAMINHO_DB)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS imagens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome_arquivo TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'pendente',
                data_envio TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS fila_sheets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL,
                chave_idempotencia TEXT NOT NULL UNIQUE,
                payload TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pendente',
                tentativas INTEGER NOT NULL DEFAULT 0,
                criado_em TEXT NOT NULL,
                enviado_em TEXT,
                ultimo_erro TEXT
            )
            """
        )
        conn.commit()


def registrar_imagem(nome_arquivo: str) -> None:
    with closing(sqlite3.connect(CAMINHO_DB)) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO imagens (nome_arquivo, status, data_envio) "
            "VALUES (?, 'pendente', ?)",
            (nome_arquivo, datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()


def listar_pendentes() -> list[str]:
    with closing(sqlite3.connect(CAMINHO_DB)) as conn:
        cursor = conn.execute(
            "SELECT nome_arquivo FROM imagens WHERE status = 'pendente'"
        )
        return [linha[0] for linha in cursor.fetchall()]


def atualizar_status(nome_arquivo: str, status: str) -> None:
    with closing(sqlite3.connect(CAMINHO_DB)) as conn:
        conn.execute(
            "UPDATE imagens SET status = ? WHERE nome_arquivo = ?",
            (status, nome_arquivo),
        )
        conn.commit()


# --- Fila para o Sheets (SQLite como fonte de verdade) ------------------
#
# Em vez de guardar os resultados do OCR num buffer em memória (que se
# perde se o pipeline reiniciar antes do envio), tudo entra primeiro
# nesta tabela, com status "pendente". drenar_fila_sheets() lê os itens
# pendentes, tenta enviar em lote, e só marca como "enviado" depois de
# confirmar sucesso - se falhar, o item continua "pendente" e é
# retentado no próximo ciclo, sem precisar de nenhum código especial de
# retry (o próprio SELECT ... WHERE status = 'pendente' já pega de
# novo). chave_idempotencia é UNIQUE: enfileirar o mesmo item duas vezes
# (ex: por causa de um restart no meio do processamento de
# processar_pendentes) é descartado pelo INSERT OR IGNORE em vez de
# criar uma entrada duplicada na fila.

def enfileirar_para_sheets(tipo: str, chave_idempotencia: str, payload: dict) -> None:
    with closing(sqlite3.connect(CAMINHO_DB)) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO fila_sheets (tipo, chave_idempotencia, payload, status, criado_em) "
            "VALUES (?, ?, ?, 'pendente', ?)",
            (tipo, chave_idempotencia, json.dumps(payload), datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()


def listar_fila_pendente(tipo: str, limite: int) -> list[dict]:
    with closing(sqlite3.connect(CAMINHO_DB)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT id, payload FROM fila_sheets WHERE tipo = ? AND status = 'pendente' "
            "ORDER BY id ASC LIMIT ?",
            (tipo, limite),
        )
        return [dict(linha) for linha in cursor.fetchall()]


def marcar_enviados(ids: list[int]) -> None:
    if not ids:
        return
    with closing(sqlite3.connect(CAMINHO_DB)) as conn:
        marcadores = ",".join("?" * len(ids))
        conn.execute(
            f"UPDATE fila_sheets SET status = 'enviado', enviado_em = ? WHERE id IN ({marcadores})",
            (datetime.now().isoformat(timespec="seconds"), *ids),
        )
        conn.commit()


def registrar_falha_fila(ids: list[int], erro: str) -> None:
    if not ids:
        return
    with closing(sqlite3.connect(CAMINHO_DB)) as conn:
        marcadores = ",".join("?" * len(ids))
        conn.execute(
            f"UPDATE fila_sheets SET tentativas = tentativas + 1, ultimo_erro = ? WHERE id IN ({marcadores})",
            (erro[:500], *ids),  # trunca para não inchar o banco com tracebacks gigantes
        )
        conn.commit()


# --- OCR (Ollama) -----------------------------------------------------

def extrair_texto(caminho_imagem: Path) -> str:
    resposta = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": "Text Recognition:",
                "images": [str(caminho_imagem)],
            }
        ],
        # keep_alive=0 faz o Ollama descarregar o modelo da VRAM assim que
        # esta resposta termina, em vez de mantê-lo residente por até 5
        # minutos (padrão) sem uso - importante numa GPU com pouca VRAM.
        # Custo: se houver várias imagens pendentes na mesma rodada de
        # processar_pendentes(), o modelo é recarregado do zero a cada
        # imagem do loop (mais lento, porém sem ocupar memória à toa entre
        # rodadas). Se isso incomodar por causa de picos de fotos em
        # sequência, trocar por keep_alive="30s" é uma opção intermediária.
        keep_alive=0,
    )
    return resposta["message"]["content"].strip()


# --- Extração best-effort do valor total, parcelas e data --------------
# Placeholder até a Etapa 3 (Fase 4, categorização com Qwen) existir de
# verdade. São todas heurísticas por regex e podem errar em cupons com
# layout incomum - se errar com frequência, mandar um exemplo do .txt
# extraído ajuda a ajustar o padrão.

# Evita casar "SUBTOTAL" (TOTAL é substring dele) e "TOTAL DE ITENS"/
# "QTD TOTAL" (que são contagem de itens, não valor em R$).
PADRAO_TOTAL = re.compile(
    r"(?<!SUB)TOTAL(?!\s*(?:DE\s*)?ITENS)(?:\s+A\s+PAGAR|\s+GERAL)?[^\d]{0,15}"
    r"(\d{1,3}(?:\.\d{3})*,\d{2}|\d+[.,]\d{2})",
    re.IGNORECASE,
)

# Fallback para comprovantes de pagamento (ex: Nubank), que não usam a
# palavra solta "TOTAL" - usam "Valor" (à vista) ou "Valor total"
# (parcelado), às vezes com o valor numa linha separada do rótulo.
PADRAO_VALOR_ROTULO = re.compile(
    r"^Valor(?:\s+total)?\s*\n?\s*R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2}|\d+[.,]\d{2})",
    re.IGNORECASE | re.MULTILINE,
)

PADRAO_PARCELAS = re.compile(
    r"(\d{1,2})\s*[xX]\s*(?:DE)?\s*R?\$?"          # ex: "3X DE R$", "10x R$"
    r"|PARCEL(?:A|AS|AMENTO)[:\s]*?(\d{1,2})"       # ex: "PARCELAMENTO: 3"
    r"|(\d{1,2})\s*PARCELAS?",                       # ex: "3 PARCELAS"
    re.IGNORECASE,
)

# Nome do estabelecimento/loja, quando presente (comprovantes de pagamento
# tipo Nubank) - usado como nome do potinho ao criar uma compra parcelada.
PADRAO_ESTABELECIMENTO = re.compile(
    r"^Estabelecimento\s*\n?\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)

# Forma de pagamento - decide o que entra na previsão de Fatura: compra
# no CRÉDITO (seja 1x ou parcelada) aparece na fatura do cartão; débito,
# pix e dinheiro saem direto da conta/carteira na hora e nunca entram na
# fatura. Cobre tanto cupom fiscal ("FORMA DE PAGAMENTO: CARTAO DE
# CREDITO") quanto comprovante de pagamento tipo Nubank ("Cartão de
# crédito", "Pix", "Dinheiro"). PIX e DÉBITO são checados antes de
# CRÉDITO porque "cartão de débito" nunca deve cair no ramo de crédito.
PADRAO_PIX = re.compile(r"\bPIX\b", re.IGNORECASE)
PADRAO_DEBITO = re.compile(r"CART[ÃA]O\s+DE\s+D[ÉE]BITO|\bD[ÉE]BITO\b", re.IGNORECASE)
PADRAO_CREDITO = re.compile(r"CART[ÃA]O\s+DE\s+CR[ÉE]DITO|\bCR[ÉE]DITO\b", re.IGNORECASE)
PADRAO_DINHEIRO = re.compile(r"\bDINHEIRO\b|\bESP[ÉE]CIE\b", re.IGNORECASE)

# Data do comprovante/cupom - cobre "05/09/2026", "05/09/26", "05-09-2026".
# Pega a PRIMEIRA data encontrada no texto: cupons/comprovantes normalmente
# trazem a data da operação logo no topo, antes de qualquer outra data
# (validade, vencimento de boleto, etc.) que possa aparecer mais abaixo.
PADRAO_DATA = re.compile(r"\b(\d{2})[/.-](\d{2})[/.-](\d{2}|\d{4})\b")

# Comprovantes de cartão frequentemente trazem a data por extenso, por
# exemplo "21 MAR 2026 - 20:22". Aceita abreviações e nomes completos em
# português, com ou sem acento.
PADRAO_DATA_EXTENSO = re.compile(
    r"\b(\d{1,2})\s+([A-ZÇÃÕ]+)\.?\s+(\d{2}|\d{4})\b",
    re.IGNORECASE,
)
MESES_POR_NOME = {
    "JAN": 1, "JANEIRO": 1,
    "FEV": 2, "FEVEREIRO": 2,
    "MAR": 3, "MARCO": 3,
    "ABR": 4, "ABRIL": 4,
    "MAI": 5, "MAIO": 5,
    "JUN": 6, "JUNHO": 6,
    "JUL": 7, "JULHO": 7,
    "AGO": 8, "AGOSTO": 8,
    "SET": 9, "SETEMBRO": 9,
    "OUT": 10, "OUTUBRO": 10,
    "NOV": 11, "NOVEMBRO": 11,
    "DEZ": 12, "DEZEMBRO": 12,
}


def extrair_valor_total(texto: str) -> float | None:
    # tenta primeiro o padrão de cupom fiscal (palavra "TOTAL"); cupons
    # costumam listar subtotais por categoria antes do total final, então
    # a última ocorrência tende a ser a soma final
    matches = list(PADRAO_TOTAL.finditer(texto))
    if matches:
        valor_str = matches[-1].group(1)
    else:
        # cupom não tinha "TOTAL" - tenta o formato de comprovante de
        # pagamento (Nubank etc.), rótulo "Valor"/"Valor total"
        m = PADRAO_VALOR_ROTULO.search(texto)
        if not m:
            return None
        valor_str = m.group(1)

    valor_str = valor_str.replace(".", "").replace(",", ".")
    try:
        return round(float(valor_str), 2)
    except ValueError:
        return None


def extrair_parcelas(texto: str) -> int:
    match = PADRAO_PARCELAS.search(texto)
    if not match:
        return 1
    grupo = next((g for g in match.groups() if g), None)
    if grupo is None:
        return 1
    try:
        qtd = int(grupo)
        return qtd if 1 <= qtd <= 24 else 1  # sanity check contra falso positivo
    except ValueError:
        return 1


def extrair_estabelecimento(texto: str) -> str | None:
    match = PADRAO_ESTABELECIMENTO.search(texto)
    return match.group(1).strip() if match else None


def extrair_forma_pagamento(texto: str) -> str:
    """
    Detecta a forma de pagamento no texto do comprovante/cupom. Retorna
    "credito", "debito", "pix" ou "dinheiro" quando encontra um padrão
    reconhecido, e "desconhecido" quando nenhum bate (melhor esforço,
    mesma lógica dos outros extratores deste arquivo - se errar com
    frequência, mandar um exemplo do .txt extraído ajuda a ajustar o
    padrão).
    """
    if PADRAO_PIX.search(texto):
        return "pix"
    if PADRAO_DEBITO.search(texto):
        return "debito"
    if PADRAO_CREDITO.search(texto):
        return "credito"
    if PADRAO_DINHEIRO.search(texto):
        return "dinheiro"
    return "desconhecido"


def extrair_data_compra(texto: str) -> date | None:
    """
    Extrai a data da compra/comprovante, usada para calcular em qual
    ciclo de fatura a primeira parcela deve cair (ver
    sheets/fatura.py:calcular_ciclo_referencia). Assume formato
    dia/mês/ano (padrão brasileiro) - se o OCR de um comprovante
    específico vier em outro formato, ajuste este regex.
    """
    match_numerico = PADRAO_DATA.search(texto)
    match_extenso = PADRAO_DATA_EXTENSO.search(texto)
    candidatos = [m for m in (match_numerico, match_extenso) if m]
    if not candidatos:
        return None

    match = min(candidatos, key=lambda m: m.start())
    dia, mes_bruto, ano = match.groups()
    if match is match_extenso:
        mes = unicodedata.normalize("NFD", mes_bruto.upper())
        mes = "".join(c for c in mes if unicodedata.category(c) != "Mn")
        mes_int = MESES_POR_NOME.get(mes)
        if mes_int is None:
            return None
    else:
        mes_int = int(mes_bruto)

    ano_int = int(ano)
    if ano_int < 100:
        ano_int += 2000
    try:
        return date(ano_int, mes_int, int(dia))
    except ValueError:
        return None


def enfileirar_ocr(nome_arquivo: str, texto_ocr: str) -> None:
    """
    Extrai valor/parcelas/data/estabelecimento do texto do OCR e grava o
    resultado na fila_sheets (SQLite) - a escrita de verdade na
    planilha só acontece em drenar_fila_sheets(), a cada
    INTERVALO_DRENAGEM_FILA_SEGUNDOS, respeitando o RateLimiter
    compartilhado (ver sheets/rate_limit.py). Como o estado fica em
    SQLite (não em memória), um restart do pipeline antes do envio não
    perde o dado. Item e destino de verdade ainda não são extraídos
    (isso é a Etapa 3, Fase 4) - ficam como placeholders montados aqui.
    """
    if sheets is None:
        return

    valor_total = extrair_valor_total(texto_ocr)
    parcelas = extrair_parcelas(texto_ocr)
    # Se o OCR não encontrou a data no comprovante, a foto ainda representa
    # uma compra feita agora. Usamos a data de recebimento para que uma compra
    # parcelada não fique sem ciclo de fatura e sem reserva na Carteira.
    data_compra = extrair_data_compra(texto_ocr) or date.today()
    estabelecimento = extrair_estabelecimento(texto_ocr)

    forma_pagamento = extrair_forma_pagamento(texto_ocr)
    if forma_pagamento == "desconhecido":
        logger.warning(
            "Forma de pagamento não identificada em %s - assumindo crédito por padrão "
            "(a maioria dos comprovantes fotografados é de compra no cartão). Confira "
            "manualmente se não deveria ser débito/pix/dinheiro.",
            nome_arquivo,
        )
        forma_pagamento = "credito"

    enfileirar_para_sheets("transacao", nome_arquivo, {
        "item": f"[a definir] {nome_arquivo}",
        "valor_total": valor_total if valor_total is not None else 0.0,
        "destino": "A categorizar",
        "parcelas": parcelas,
        "status": "aguardando_categorizacao" if valor_total is not None else "erro_extracao_valor",
        "data": data_compra.isoformat() if data_compra else None,
    })

    # Toda compra no CRÉDITO entra na fatura do cartão - seja parcelada
    # (parcelas > 1) ou à vista em 1x (parcelas = 1, que vira um potinho
    # "quitado" na primeira cobrança, sem parcelas futuras). Débito, pix
    # e dinheiro saem direto da conta/carteira na hora e nunca criam
    # potinho - não fazem parte da previsão da Fatura. Nenhum crédito é
    # alocado antecipadamente (credito_inicial=0.0) - isso continua
    # manual por enquanto (edite saldo_credito direto na planilha, ou
    # chame sm.criar_potinho_compra à parte, se quiser adiantar a
    # reserva).
    if forma_pagamento == "credito" and valor_total is not None:
        enfileirar_para_sheets("potinho", f"{nome_arquivo}#potinho", {
            "nome_compra": estabelecimento or f"Compra {nome_arquivo}",
            "valor_total": valor_total,
            "num_parcelas": parcelas,
            "data_compra": data_compra.isoformat() if data_compra else None,
        })

    logger.info(
        "Enfileirado para o Sheets: %s (forma_pagamento=%s, valor_total=%s, parcelas=%s, data_compra=%s)",
        nome_arquivo, forma_pagamento, valor_total, parcelas, data_compra,
    )


# --- Handlers do Telegram --------------------------------------------

async def receber_foto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    PASTA_IMAGENS.mkdir(exist_ok=True)

    foto = update.message.photo[-1]
    arquivo = await foto.get_file()

    # message_id é único por mensagem no chat (mesmo dentro de um álbum
    # enviado de uma vez) - usar só o timestamp (precisão de segundo)
    # permitia que duas fotos enviadas rapidamente em sequência caíssem
    # no mesmo nome de arquivo: a segunda sobrescrevia o arquivo da
    # primeira no disco, e o INSERT OR IGNORE (nome_arquivo é UNIQUE)
    # descartava silenciosamente o registro dela no SQLite - a primeira
    # foto simplesmente sumia, sem nenhum aviso de erro. O timestamp
    # continua no nome só para ordenação/leitura humana.
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_arquivo = f"cupom_{timestamp}_{update.message.message_id}.jpg"
    caminho_completo = PASTA_IMAGENS / nome_arquivo

    await arquivo.download_to_drive(custom_path=str(caminho_completo))
    registrar_imagem(nome_arquivo)

    logger.info("Imagem salva e registrada: %s", nome_arquivo)
    await update.message.reply_text(f"📸 Recebido: {nome_arquivo} (na fila de OCR)")


async def receber_nao_foto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Por enquanto eu só processo fotos. Manda a foto do cupom 📸"
    )


# --- Job periódico: verifica pendências e roda o OCR -------------------

async def processar_pendentes(context: ContextTypes.DEFAULT_TYPE) -> None:
    pendentes = listar_pendentes()
    if not pendentes:
        return  # nada a fazer, o Ollama nem é acionado

    logger.info("%d imagem(ns) pendente(s). Rodando OCR...", len(pendentes))
    PASTA_TEXTOS.mkdir(exist_ok=True)

    for nome_arquivo in pendentes:
        caminho_imagem = PASTA_IMAGENS / nome_arquivo
        if not caminho_imagem.exists():
            logger.warning("Arquivo %s não encontrado em disco, marcando como erro.", nome_arquivo)
            atualizar_status(nome_arquivo, "erro")
            continue

        try:
            # roda em thread separada para não travar o bot enquanto o OCR processa
            texto = await asyncio.to_thread(extrair_texto, caminho_imagem)
        except Exception:
            logger.exception("Falha no OCR de %s", nome_arquivo)
            atualizar_status(nome_arquivo, "erro")
            continue

        caminho_txt = PASTA_TEXTOS / f"{caminho_imagem.stem}.txt"
        caminho_txt.write_text(texto, encoding="utf-8")
        atualizar_status(nome_arquivo, "processado")
        logger.info("Processado: %s -> %s", nome_arquivo, caminho_txt.name)

        # Não fala com o Sheets aqui - só extrai os dados (CPU, sem API) e
        # grava na fila_sheets. drenar_fila_sheets() envia tudo em lote.
        enfileirar_ocr(nome_arquivo, texto)


# --- Job periódico: drena a fila_sheets, respeitando o RateLimiter -----

async def drenar_fila_sheets(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Lê a fila_sheets (SQLite) por itens "pendente" e manda pro Sheets em
    lote - uma chamada para transações, outra para potinhos de compra
    parcelada. Cada chamada à API já passa pelo RateLimiter
    compartilhado (ver sheets/rate_limit.py), então esta função não
    precisa controlar taxa nenhuma: só marca como "enviado" no SQLite
    depois de confirmar sucesso, ou registra a falha (sem apagar da
    fila) para tentar de novo no próximo ciclo. Diferente do buffer em
    memória da versão anterior, isso sobrevive a um restart do pipeline
    - um item que ainda não foi confirmado como enviado continua
    "pendente" no banco e é drenado normalmente na próxima execução.
    """
    if sheets is None:
        return

    pendentes_transacao = listar_fila_pendente("transacao", LIMITE_LOTE_DRENAGEM)
    if pendentes_transacao:
        transacoes = [json.loads(p["payload"]) for p in pendentes_transacao]
        ids = [p["id"] for p in pendentes_transacao]
        try:
            await asyncio.to_thread(sheets.registrar_transacoes_em_lote, transacoes)
            marcar_enviados(ids)
            logger.info("Lote de %d transação(ões) enviado ao Sheets.", len(transacoes))
        except Exception as exc:
            registrar_falha_fila(ids, str(exc))
            logger.exception(
                "Falha ao enviar lote de %d transação(ões) ao Sheets - "
                "continuam pendentes na fila, tentativa de novo no próximo ciclo.",
                len(transacoes),
            )

    pendentes_potinho = listar_fila_pendente("potinho", LIMITE_LOTE_DRENAGEM)
    if pendentes_potinho:
        potinhos = []
        for p in pendentes_potinho:
            payload = json.loads(p["payload"])
            if payload.get("data_compra"):
                payload["data_compra"] = date.fromisoformat(payload["data_compra"])
            potinhos.append(payload)
        ids = [p["id"] for p in pendentes_potinho]
        try:
            await asyncio.to_thread(sheets.criar_potinhos_em_lote, potinhos)
            marcar_enviados(ids)
            logger.info("Lote de %d potinho(s) de compra parcelada enviado ao Sheets.", len(potinhos))
        except Exception as exc:
            registrar_falha_fila(ids, str(exc))
            logger.exception(
                "Falha ao enviar lote de %d potinho(s) ao Sheets - "
                "continuam pendentes na fila, tentativa de novo no próximo ciclo.",
                len(potinhos),
            )


# --- Job periódico: sincroniza alocações manuais (crédito + Carteira) ---

async def sincronizar_manual(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Varre a planilha por edições feitas diretamente por você:
    - Compras_Parceladas: saldo_credito alterado na mão
    - Carteira: potinhos de Reserva/Conta criados ou com "alocado" alterado

    Em ambos os casos, o Sobrando é ajustado automaticamente pela diferença.
    """
    if sheets is None:
        return
    try:
        resultado = await asyncio.to_thread(sheets.sincronizar_tudo)
    except Exception:
        logger.exception("Falha ao sincronizar alocações manuais com o Sheets.")
        return

    for ajuste in resultado["compras_parceladas"]:
        logger.info(
            "Crédito manual detectado (Compras_Parceladas): %s (%.2f) - Sobrando agora: %.2f",
            ajuste["nome_compra"], ajuste["delta_alocado"], ajuste["novo_sobrando"],
        )

    if resultado["total"] is not None:
        logger.info("Total alterado manualmente - Sobrando agora: %.2f", resultado["total"])

    for ajuste in resultado["carteira"]:
        logger.info(
            "Alocação manual detectada (Carteira/%s): %s (%.2f) - Sobrando agora: %.2f",
            ajuste.categoria, ajuste.nome, ajuste.delta_alocado, ajuste.novo_sobrando,
        )


# --- Job diário: garante o ciclo de fatura atual e processa faturas pagas ---

async def sincronizar_fatura(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    1. Garante que a linha do ciclo de fatura corrente (e do próximo)
       existe na aba Fatura, pronta pra você marcar "status" como "paga"
       quando pagar.
    2. Processa qualquer ciclo marcado como "paga" que ainda não tenha
       sido processado - cobrando a parcela correspondente de cada
       potinho ativo elegível. Se você tiver pulado um mês, os ciclos
       atrasados são processados em ordem antes do mais recente (é assim
       que as parcelas "se acumulam" - ver sheets/fatura.py).
    """
    if sheets is None:
        return
    try:
        await asyncio.to_thread(sheets.garantir_ciclo_atual)
        resultado = await asyncio.to_thread(sheets.processar_faturas_pendentes)
    except Exception:
        logger.exception("Falha ao sincronizar o ciclo de fatura com o Sheets.")
        return

    for ciclo in resultado:
        logger.info(
            "Fatura %s processada: %d parcela(s) cobrada(s).",
            ciclo["mes_referencia"], len(ciclo["parcelas_processadas"]),
        )
        for parcela in ciclo["parcelas_processadas"]:
            logger.info(
                "  - %s: parcela R$%.2f (abatido do crédito: R$%.2f, do Sobrando: R$%.2f)%s",
                parcela.nome_compra, parcela.valor_parcela,
                parcela.abatido_do_credito, parcela.descontado_do_sobrando,
                " [potinho quitado]" if parcela.potinho_fechado else "",
            )


# --- Inicialização -------------------------------------------------------

def main() -> None:
    if not TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN não encontrado. Verifique o arquivo .env."
        )

    iniciar_banco()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(MessageHandler(filters.PHOTO, receber_foto))
    app.add_handler(MessageHandler(~filters.PHOTO, receber_nao_foto))

    app.job_queue.run_repeating(
        processar_pendentes,
        interval=INTERVALO_VERIFICACAO_SEGUNDOS,
        first=5,
    )
    app.job_queue.run_repeating(
        drenar_fila_sheets,
        interval=INTERVALO_DRENAGEM_FILA_SEGUNDOS,
        first=20,
    )
    app.job_queue.run_repeating(
        sincronizar_manual,
        interval=INTERVALO_SYNC_MANUAL_SEGUNDOS,
        first=10,
    )
    app.job_queue.run_repeating(
        sincronizar_fatura,
        interval=INTERVALO_SYNC_FATURA_SEGUNDOS,
        first=15,
    )

    logger.info(
        "Pipeline iniciado. Verificando pendências a cada %ds. Banco: %s",
        INTERVALO_VERIFICACAO_SEGUNDOS,
        CAMINHO_DB.resolve(),
    )
    app.run_polling()


if __name__ == "__main__":
    main()