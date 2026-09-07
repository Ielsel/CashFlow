# Como rodar o bot (Windows 11)

Passo a passo para colocar o `bot_recebe_cupom.py` funcionando localmente.

## 1. Verificar/instalar o Python

No PowerShell, teste:

```powershell
py --version
```

- Se retornar uma versão (ex: `Python 3.12.x`), pule para o passo 2.
- Se aparecer o aviso do Microsoft Store dizendo que o Python não foi encontrado:
  1. Desative o alias problemático em **Configurações → Aplicativos → Aliases de execução de aplicativo** (desligue `python.exe` e `python3.exe`)
  2. Baixe o instalador oficial em **python.org/downloads** (não pela Microsoft Store)
  3. Durante a instalação, marque a caixa **"Add python.exe to PATH"**
  4. Feche e abra um PowerShell novo, teste `py --version` de novo

## 2. Criar o ambiente virtual (venv)

Na pasta do projeto:

```powershell
py -m venv venv
```

> Se `py` não funcionar mas `python` funcionar, use `python -m venv venv` no lugar.

## 3. Ativar o venv

```powershell
venv\Scripts\Activate.ps1
```

Se aparecer erro de política de execução de script, rode uma vez (só precisa fazer isso uma vez por máquina):

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Depois tente ativar de novo. Quando ativo, o terminal mostra `(venv)` no início da linha.

## 4. Instalar as dependências

Com o venv ativo:

```powershell
pip install -r requirements.txt
```

## 5. Configurar o token do bot

Se ainda não tem um bot, crie um falando com o `@BotFather` no Telegram (`/newbot`) e copie o token gerado.

Abra o arquivo `.env` (na raiz do projeto) e cole o token na linha indicada:

```
TELEGRAM_BOT_TOKEN=seu_token_aqui
```

Salve o arquivo. Não precisa colocar aspas, e o `.env` **não deve** ser versionado no Git (já está no `.gitignore`) — ele guarda a credencial do seu bot.

## 6. Rodar o bot

```powershell
python bot_recebe_cupom.py
```

O script carrega o token do `.env` automaticamente. Manda uma foto para o bot no Telegram e confira se ela aparece na pasta `cupons_recebidos`, criada automaticamente na primeira foto recebida.

---

## Nas próximas vezes

Toda vez que for trabalhar no projeto em um terminal novo:

```powershell
venv\Scripts\Activate.ps1
python bot_recebe_cupom.py
```

O token já fica salvo no `.env` — não precisa redefinir nada.