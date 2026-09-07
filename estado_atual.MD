# Gestor Financeiro Automatizado com IA — Estado Atual do Projeto

> Este documento descreve o que já está implementado e funcionando. Para o que falta fazer, ver `PROXIMOS_PASSOS.md`.

## Visão Geral

Evolução do `leitor-fatura` (ferramenta atual em Python/CustomTkinter que lê CSV do Nubank) para um sistema completo e automatizado de gestão financeira, aplicando a mesma competência técnica usada nos pipelines de OCR/visão computacional do trabalho (PCDF/NIA) a um contexto pessoal.

**Objetivo final:** tirar foto de um cupom fiscal no celular → sistema extrai, categoriza e registra automaticamente na planilha de finanças, sem intervenção manual.

**Restrição de hardware:** PC com GPU AMD Radeon RX 7600 (RDNA3, VRAM <8GB), Windows 11 — arquitetura precisa rodar modelos leves. Como é AMD (sem suporte a CUDA), o caminho de execução local usa **Ollama** (aceleração ROCm nativa para RX 7000 series no Windows) em vez de PyTorch/CUDA.

## Arquitetura Geral (visão completa do fluxo planejado)

```
[Celular] --foto do cupom--> [Bot Telegram] --> [Script no PC]
                                                        |
                                                        v
                                [Etapa 1: Validação - EfficientNet
                                   "isso é um recibo/cupom?"]
                                                    |         |
                                                  Não        Sim
                                                    |         |
                                     [Bot pede foto  v
                                      de novo]  [Etapa 2: OCR - GLM-OCR 0.9B via Ollama]
                                                        |
                                                        v
                                    [Etapa 3: Categorização - Qwen leve /
                                     classificador em embeddings]
                                                        |
                                                        v
                                [Etapa 4: Google Sheets - log de transação +
                                 ajuste automático de saldo/potinhos]
                                                        |
                                                        v
                                [Bot Telegram confirma: "R$47,30 - Mercado -
                                            Alimentação ✅"]
```

Deste fluxo, as etapas **Captura**, **OCR** e **Google Sheets (estrutura de dados e código)** já estão prontas. Validação (EfficientNet), Categorização (Qwen) e a confirmação final ao usuário ainda não existem — ver `PROXIMOS_PASSOS.md`.

## Componentes já implementados

### 1. Captura e transporte (celular → PC) ✅
- **Bot do Telegram** como ponte de comunicação
- Não depende de estar na mesma rede/Wi-Fi de casa
- Biblioteca: `python-telegram-bot`
- Script no PC escuta a API do bot e baixa a imagem automaticamente ao receber

### 2. OCR do cupom ✅
- Modelo: **GLM-OCR (0.9B)**, mesmo modelo já usado no pipeline de produção do trabalho, servido localmente via **Ollama** (`ollama pull glm-ocr`)
- Ollama gerencia o carregamento/descarregamento do modelo automaticamente — só é acionado quando há imagem pendente
- Extrai texto bruto: itens, valores, CNPJ, data
- Resultado salvo em `.txt` na pasta `textos_extraidos/`
- Como o hardware é AMD (não CUDA), a troca de modelo via `os.execvp` do plano original não se aplica — o **Ollama** já gerencia isso sozinho, carregando o modelo só quando necessário e descarregando por inatividade

### 3. Rastreamento com SQLite ✅
- Banco local `pipeline.db` registra cada imagem recebida: `nome_arquivo`, `status` (pendente/processado/erro), `data_envio`
- Bot grava o registro assim que a foto chega; o job periódico atualiza o status após o OCR

### 4. Camada de dados e código para o Google Sheets ✅ (código pronto; credenciais/uso real pendentes)

**Migração planejada: Excel (.xlsx) → Google Sheets**, via API oficial (`gspread`) com credencial de conta de serviço (service account) do Google Cloud Console — motivo: o script roda em background, possivelmente com o usuário fora de casa, e um `.xlsx` local trava/corrompe se estiver aberto durante a escrita.

**Estrutura de dados em duas camadas, já implementada em código:**

- **Camada 1 — aba "Transações"** (log bruto, imutável, uma linha por cupom processado): `data | item | valor_total | parcelas | valor_parcela | destino | status`
- **Camada 2 — a Carteira/potinhos**, atualizada automaticamente a partir do log.

**Sistema de crédito por potinho (compras parceladas), já implementado:**

| nome_compra | valor_total | num_parcelas | valor_parcela | saldo_credito | parcelas_pagas | alocacao_automatica | status |
|---|---|---|---|---|---|---|---|

Regra de processamento quando uma parcela vence:
```
se saldo_credito >= valor_parcela:
    abate valor_parcela do saldo_credito
senão:
    falta = valor_parcela - saldo_credito
    zera saldo_credito
    desconta falta do Sobrando   (obrigatório — o Sobrando sempre completa a diferença)
```

- **Exemplo A** — compra de R$20 em 2x (parcela R$10), alocada integralmente na hora da compra: cria potinho com `saldo_credito = 20`; cada parcela de R$10 abate do crédito, sem tocar o Sobrando, até fechar.
- **Exemplo B** — compra de R$10 em 2x (parcela R$5), sem alocação antecipada: potinho criado com `saldo_credito = 0`; cada parcela de R$5 desconta direto do Sobrando.
- **Crédito parcial**: se o potinho tem R$6 de crédito e a parcela é R$10, os R$6 abatem do crédito e os R$4 restantes saem do Sobrando obrigatoriamente.
- **Flag `alocacao_automatica`**: compras parceladas marcadas assim têm a parcela registrada no log de Transações, mas o sistema não mexe em `saldo_credito` nem no Sobrando — fica como lembrete manual.

**Potinhos de Reservas/Contas na Carteira** (Emergência, CNH, Internet, Gasolina...) seguem controle 100% manual direto na planilha, com uma coluna de controle (`alocado_processado`) que o código usa só para *detectar* uma edição manual em `alocado` e refletir a diferença no Sobrando — o código nunca escreve em `alocado` diretamente.

## Estrutura do Projeto (código atual)

Pasta do projeto: `leitor-faturav5/` (Windows 11, venv Python).

```
leitor-faturav5/
├── venv/                      # ambiente virtual (não versionado)
├── pipeline.py                # script principal - roda tudo (captura + OCR)
├── config.py                  # constantes e dataclasses compartilhadas da camada Sheets
├── sheets_setup.py            # criação/migração das abas do Google Sheets
├── transacoes.py              # Camada 1 - log bruto de transações
├── compras_parceladas.py      # Camada 3 - potinhos de compra parcelada + crédito
├── carteira.py                # Camada 2 - Total/Sobrando + potinhos de Reservas/Contas
├── sheets_manager.py          # orquestrador: delega para os módulos acima
├── requirements.txt           # dependências do projeto
├── .env                       # token do bot (não versionado)
├── .gitignore
├── cupons_recebidos/          # imagens recebidas via Telegram (criada em runtime)
├── textos_extraidos/          # resultado do OCR em .txt (criada em runtime)
└── pipeline.db                # banco SQLite de rastreamento (criado em runtime)
```

### `pipeline.py` — funcionamento detalhado

Script único que consolida captura (bot) + rastreamento (SQLite) + processamento (OCR via Ollama), rodando tudo no mesmo processo/event loop assíncrono do `python-telegram-bot`.

**Banco de dados (`pipeline.db`, tabela `imagens`):**
- `id` — chave primária autoincremento
- `nome_arquivo` — nome do arquivo de imagem (único)
- `status` — `pendente` / `processado` / `erro`
- `data_envio` — timestamp ISO de quando a imagem chegou

Funções: `iniciar_banco()` cria a tabela se não existir; `registrar_imagem()` insere uma linha nova com status `pendente`; `listar_pendentes()` retorna os nomes de arquivo ainda não processados; `atualizar_status()` muda o status de um registro.

**Fluxo do bot (handlers do Telegram):**
- `receber_foto()`: disparado quando chega uma foto. Baixa a imagem na maior resolução disponível, salva em `cupons_recebidos/` com nome `cupom_<timestamp>.jpg`, registra no SQLite com status `pendente`, e responde confirmando o recebimento.
- `receber_nao_foto()`: disparado para qualquer mensagem que não seja foto — responde pedindo pra mandar uma foto.

**OCR (`extrair_texto()`):**
Chama `ollama.chat()` com o modelo `glm-ocr`, mandando o prompt `"Text Recognition:"` junto com o caminho da imagem. Retorna o texto extraído.

**Job periódico (`processar_pendentes()`):**
Rodado a cada 15 segundos via `JobQueue` do próprio `python-telegram-bot` (não é um processo separado). A cada execução:
1. Consulta o SQLite por imagens com status `pendente`. Se não houver nenhuma, encerra sem fazer nada — o Ollama não é acionado à toa.
2. Para cada pendência, roda o OCR em uma thread separada (`asyncio.to_thread`), para não travar o bot de responder outras mensagens enquanto o modelo processa.
3. Salva o texto extraído em `textos_extraidos/<nome_base>.txt`.
4. Atualiza o status no banco para `processado` (ou `erro`, se a extração falhar).

**Inicialização (`main()`):** valida que o token do bot foi carregado do `.env`, inicializa o banco, registra os handlers, agenda o job periódico, e inicia o polling do Telegram (`app.run_polling()`) — a partir daí o script fica rodando indefinidamente, escutando o bot e verificando pendências.

### Camada de integração com o Google Sheets — módulos e funcionamento

A integração com o Sheets não fica em um arquivo só: está dividida por etapa/responsabilidade, cada uma em seu próprio módulo, para que a lógica de negócio de cada camada (Transações, Compras Parceladas, Carteira) fique isolada e mais fácil de testar/alterar sem mexer nas outras. `sheets_manager.py` não contém regra de negócio própria — é só o orquestrador.

- **`config.py`** — constantes compartilhadas (nomes das abas, cabeçalhos, categorias de potinho) e os dataclasses `ResultadoParcela` e `AjusteCarteira`, usados como retorno tipado das operações de sincronização.
- **`sheets_setup.py`** (`EstruturaPlanilha`) — garante que as 3 abas (Transacoes, Compras_Parceladas, Carteira) existem com o cabeçalho certo, seja em planilha nova ou criada manualmente na interface do Sheets. Também roda as migrações idempotentes quando uma coluna de controle nova é introduzida no schema (`credito_processado`, `alocado_processado`), fazendo backfill nas linhas já existentes.
- **`transacoes.py`** (`TransacoesManager`) — Camada 1: só adiciona linhas no log bruto e imutável de transações. Nunca lê nem atualiza linhas existentes.
- **`compras_parceladas.py`** (`ComprasParceladasManager`) — Camada 3: ciclo de vida dos potinhos de compra parcelada (`criar_potinho_compra`, `processar_parcela_vencida`, `sincronizar_creditos_manuais`), aplicando a regra de crédito descrita acima. Não acessa a aba Carteira diretamente — recebe uma função `ajustar_sobrando` injetada pelo orquestrador para descontar/devolver valores do Sobrando.
- **`carteira.py`** (`CarteiraManager`) — Camada 2: leitura/escrita de `Sobrando` (`ajustar_sobrando`, `get_sobrando`) e sincronização dos potinhos de Reserva/Conta geridos manualmente na planilha (`sincronizar_potinhos_carteira`, `listar_potinhos_carteira`). É o único módulo que sabe escrever na coluna `Sobrando`.
- **`sheets_manager.py`** (`SheetsManager`, orquestrador) — autentica no Google (`Credentials` + `gspread.authorize`), abre a planilha, chama `EstruturaPlanilha.garantir_estrutura()` uma vez na inicialização, instancia os três managers (injetando `CarteiraManager.ajustar_sobrando` no `ComprasParceladasManager`) e expõe os métodos públicos (`registrar_transacao`, `criar_potinho_compra`, `processar_parcela_vencida`, `sincronizar_creditos_manuais`, `sincronizar_potinhos_carteira`, `listar_potinhos_carteira`, `get_sobrando`, `sincronizar_tudo`), cada um delegando para o módulo responsável.

Uso típico (já implementado, ainda não plugado no `pipeline.py`):

```python
from sheets_manager import SheetsManager

sm = SheetsManager(spreadsheet_id="...", credentials_path="credentials.json")
sm.registrar_transacao(item="Mercado", valor_total=47.30, destino="Alimentação")
sm.processar_parcela_vencida("Notebook", valor_parcela=250.00)

# a cada execução do job periódico, chame também:
ajustes = sm.sincronizar_tudo()  # varre Compras_Parceladas + Carteira
```

### `requirements.txt` (atual)
- `python-telegram-bot[job-queue]==22.8` — biblioteca do bot, com a extensão de agendamento de jobs periódicos
- `python-dotenv==1.0.1` — carrega variáveis do `.env`
- `ollama` — cliente Python que fala com o servidor local do Ollama (a aplicação Ollama em si é instalada separadamente, fora do pip)

### `.env`
Guarda `TELEGRAM_BOT_TOKEN`, carregado automaticamente pelo `pipeline.py` via `python-dotenv`. Nunca deve ser versionado.

### `.gitignore`
Ignora `venv/`, `.env`, `cupons_recebidos/`, `__pycache__/` e `*.pyc` — evita subir credenciais, dados pessoais (fotos de cupom) e artefatos de ambiente para o controle de versão.

### Dependências externas (fora do projeto Python)
- **Ollama** (aplicação Windows): serve o modelo `glm-ocr` localmente em `http://127.0.0.1:11434`, com aceleração nativa para a RX 7600. Precisa estar rodando em background (ícone na bandeja do sistema) para o `pipeline.py` funcionar.

## Reaproveitamento de Know-How Existente

Todo o projeto reaproveita competências já desenvolvidas em contexto profissional (estágio PCDF/NIA):
- GLM-OCR → já usado no pipeline de produção do trabalho, aqui servido via Ollama
- Estrutura de fila/processamento em background → já aplicado no `leitor-fatura` e em outros projetos

Isso torna o projeto uma extensão natural e de baixo atrito da mesma especialização técnica, aplicada a um problema pessoal real (organização financeira).

## Status

🚧 **Em execução.** Concluído: captura via bot Telegram, OCR via GLM-OCR/Ollama (consolidados em `pipeline.py` com rastreamento SQLite), e a estrutura de dados + regras de negócio do Google Sheets, implementadas em código e modularizadas (`config.py`, `sheets_setup.py`, `transacoes.py`, `compras_parceladas.py`, `carteira.py`, `sheets_manager.py`). Para o que ainda falta, ver `PROXIMOS_PASSOS.md`.