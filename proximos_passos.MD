# Gestor Financeiro Automatizado com IA — Próximos Passos

> Este documento descreve o que ainda falta implementar. Para o que já está pronto e funcionando, ver `ESTADO_ATUAL.md`.

## Objetivo final (recap)

Tirar foto de um cupom fiscal no celular → sistema extrai, categoriza e registra automaticamente na planilha de finanças, sem intervenção manual. Já temos captura, OCR e a camada de dados do Google Sheets prontos; faltam a validação de imagem, a categorização automática, a conexão de tudo em um fluxo só e a confirmação ao usuário.

## O que falta implementar

### 1. Fechar a integração com o Google Sheets (Fase 1, reta final)

O código de `sheets_manager.py` e seus módulos já está pronto (ver `ESTADO_ATUAL.md`), mas ainda não está em uso real. Falta:

- Criar projeto no Google Cloud Console e ativar Google Sheets API + Google Drive API
- Criar conta de serviço, gerar chave JSON, compartilhar a planilha nova com o e-mail da conta de serviço
- Guardar o `.json` da credencial fora do controle de versão (mesmo tratamento do `.env`, adicionar ao `.gitignore`)
- Adicionar `gspread` e `google-auth` ao `requirements.txt`
- Plugar o `SheetsManager` no `pipeline.py` (hoje o pipeline só cuida de captura + OCR, ainda não chama `registrar_transacao` nem `sincronizar_tudo`)

**Decisões ainda em aberto nessa camada:**
- Como tratar os potinhos de `Contas` recorrentes (Internet, Gasolina) que já existem na Carteira: alocar automaticamente ao reconhecer o nome no cupom, ou só criar entradas novas?
- Fluxo de criação de um novo potinho de compra parcelada: o usuário cria manualmente antes na planilha, ou o bot pergunta na hora que reconhece uma compra parcelada em um cupom?

### 2. Validação: é um recibo? (Fase 2.5)

- Modelo: **EfficientNet** (ex. B0), mesma técnica já usada no ensemble de legibilidade do IC-Plates, aplicada aqui a uma classificação binária (recibo / não-recibo)
- Deve rodar **antes** do OCR, como filtro: evita gastar processamento em fotos erradas (print de meme, foto borrada, imagem sem relação)
- Se "não é recibo" → bot pede pra mandar a foto de novo, sem seguir no pipeline
- **Necessidade de dataset rotulado desde o início** (diferente do OCR e da categorização, que podem começar sem treino):
  - Opção rápida: usar um classificador de documentos genérico pré-treinado (Hugging Face) sem treinar nada, como primeira versão
  - Opção própria: treinar EfficientNet via transfer learning com um dataset pequeno (recibos reais + fotos aleatórias do celular como classe negativa) — poucas dezenas de exemplos já costumam ser suficientes com transfer learning
- **Ainda em aberto:** decidir qual das duas opções acima usar para a primeira versão

### 3. Estruturação e categorização (Fase 4)

**Abordagem escolhida: zero-shot inicial + loop de correção (active learning)** — não é necessário treinar nada para começar:

1. **Zero-shot via prompt** — Qwen2.5-3B-Instruct (AWQ/Q4) recebe o texto bruto do OCR e uma lista das categorias disponíveis, e devolve um palpite de categoria via prompt (sem fine-tuning)
2. **Confirmação/correção via Telegram** — o bot apresenta o palpite com botões inline (`InlineKeyboardMarkup`) listando o acervo de categorias próprio, permitindo confirmar ou trocar com um toque
3. **Coleta automática de dataset** — cada confirmação/correção vira uma linha `(texto do item, categoria correta)`, acumulada organicamente durante o uso normal
4. **Treino futuro, quando houver volume suficiente** — duas opções a avaliar:
   - **LoRA fine-tuning no Qwen** (via `peft`/`bitsandbytes` em 4-bit, cabe em <8GB de VRAM)
   - **Classificador leve dedicado**: embeddings pequenos (ex. `all-MiniLM`) + classificador simples (regressão logística/SVM) treinado no dataset próprio — mais rápido, mais barato de rodar, potencialmente mais preciso para categoria de conjunto fechado; pode virar comparação de benchmark, na mesma linha do TCC

Primeiro passo prático: prototipar com Qwen2.5-3B leve para validar rápido, e só depois avaliar se compensa migrar para o classificador de embeddings.

### 4. Integração final do fluxo (Fase 5)

- Conectar captura → validação → OCR → categorização → escrita automática no Google Sheets, tudo no mesmo `pipeline.py`
- Aplicar a lógica de crédito por potinho / ajuste do Sobrando a cada cupom processado (já implementada em código, só falta ser chamada nesse ponto do fluxo)
- Bot confirma o registro ao usuário no próprio Telegram (ex.: "R$47,30 - Mercado - Alimentação ✅"), fechando o ciclo sem precisar abrir a planilha manualmente

### 5. Refinamento (Fase 6)

- Ajustar categorias conforme o uso real mostrar necessidade
- Tratar erros de OCR (cupons ruins, letra pequena)
- Talvez adicionar um dashboard simples de gastos por categoria/mês

## Fases pendentes, em ordem

- **Fase 1 (reta final)** — credenciais do Google Cloud + conectar `SheetsManager` ao `pipeline.py`
- **Fase 2.5** — validação de imagem com EfficientNet
- **Fase 4** — categorização com Qwen (zero-shot) + loop de correção
- **Fase 5** — integração final do fluxo ponta a ponta + confirmação ao usuário
- **Fase 6** — refinamento geral