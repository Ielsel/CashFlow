# 💰 CashFlow

Sistema de controle financeiro pessoal desenvolvido em Python, com foco em organização de saldo e reservas financeiras via terminal (CLI).

---

## 🚀 Versão atual

Aplicação em **CLI (terminal)** com:

- Controle de saldo (depósito, saque e atualização)
- Extrato de operações com visualização via Pandas
- Criação e gerenciamento de reservas financeiras
- Validação de operações (saldo insuficiente, valores inválidos)
- Precisão decimal com a biblioteca `decimal` do Python
- Estrutura modular (lógica separada da interface)

---

## 📁 Estrutura do projeto

```
CASHFLOW/
├── src/
│   ├── main.py       # Interface CLI (menus e interação com usuário)
│   └── tools.py      # Lógica financeira (operações de saldo e reservas)
├── venv/             # Ambiente virtual Python
├── .gitattributes
├── .gitignore
├── LICENSE
└── README.md
```

---

## 🛠️ Tecnologias

- Python 3
- [Pandas](https://pandas.pydata.org/) — exibição do extrato em formato tabular
- `decimal` (built-in) — precisão em cálculos financeiros

---

## ⚙️ Como usar

### 1. Clone o repositório

```bash
git clone https://github.com/seu-usuario/cashflow.git
cd cashflow
```

### 2. Crie e ative o ambiente virtual

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate
```

### 3. Instale as dependências

```bash
pip install pandas
```

### 4. Execute o projeto

```bash
python src/main.py
```

---

## 🗺️ Navegação pelos menus

Ao iniciar, o sistema exibe o **Menu Principal** com o saldo disponível e três opções:

```
Saldo disponível: R$0.00
Opções:
1 - Saldo
2 - Reservas
3 - exit
```

### Menu Saldo

Acesse com a opção `1` no menu principal.

| Opção | Descrição |
|-------|-----------|
| 1 - Extrato | Exibe o histórico de operações em formato de tabela (Pandas DataFrame) |
| 2 - Depositar | Adiciona um valor ao saldo |
| 3 - Sacar | Retira um valor do saldo (validado contra saldo disponível) |
| 4 - Atualizar saldo | Redefine o saldo para um novo valor (requer confirmação com `YES`) |
| 5 - Voltar | Retorna ao menu principal |

**Exemplo de extrato:**

```
--EXTRATO--
     Operação   Valor  Saldo
0    Depósito  500.00  500.00
1       Saque  100.00  400.00
2  Atualização  300.00  300.00
```

### Menu Reservas

Acesse com a opção `2` no menu principal.

| Opção | Descrição |
|-------|-----------|
| 1 - Ver reservas | Lista todas as reservas criadas com seus valores |
| 2 - Criar reserva | Cria uma nova reserva com nome único e valor inicial (descontado do saldo) |
| 3 - Alterar reserva | Permite renomear, depositar ou sacar de uma reserva existente |
| 4 - Voltar | Retorna ao menu principal |

**Exemplo de criação de reserva:**

```
Digite um nome para a nova reserva: Viagem
Digite o valor da reserva: 200
Nova reserva adicionada!
Viagem: R$200.00
```

---

## 🔧 Como funciona

### `tools.py` — Lógica financeira

Contém todas as funções puras de manipulação de saldo e reservas:

| Função | Descrição |
|--------|-----------|
| `cash_format(value)` | Formata um `Decimal` para 2 casas decimais (arredondamento `ROUND_HALF_UP`) |
| `balance_deposit(balance, statement, amount)` | Soma `amount` ao saldo e registra no extrato |
| `balance_withdraw(balance, statement, amount)` | Subtrai `amount` do saldo e registra no extrato |
| `balance_update(balance, statement, amount)` | Redefine o saldo para `amount` e registra no extrato |
| `add_new_reserve(balance, statement, reserve, amount, name)` | Cria uma reserva descontando o valor do saldo; retorna `None` se saldo insuficiente |
| `rename_reserve(reserve, new_name, old_name)` | Renomeia uma reserva existente |
| `reserve_deposit(balance, reserve, amount, name)` | Transfere `amount` do saldo para a reserva |
| `reserve_withdraw(balance, reserve, amount, name)` | Transfere `amount` da reserva de volta ao saldo |

Todas as operações utilizam `Decimal` para garantir precisão nos cálculos monetários.

### `main.py` — Interface CLI

Contém os três menus de navegação:

- `main()` — inicializa as variáveis (`balance`, `reserve`, `account_statement`) e chama o menu principal
- `main_menu()` — loop do menu principal, roteia para os submenus
- `balance_menu()` — gerencia operações de saldo
- `reserve_menu()` — gerencia operações de reservas

---

## 📈 Roadmap

- [ ] Retirar a obrigatoriedade de valor inicial na criação de reservas
- [ ] Registrar movimentações de reservas no extrato
- [ ] Adicionar timestamp (data/hora) nas transações
- [ ] Implementar classes (`AccountStatement`, `Reserve`)
- [ ] Melhorar a exibição das reservas (formato tabular com Pandas)
- [ ] Exportação do extrato (CSV / Excel)
- [ ] Persistência com banco de dados (SQLAlchemy)
- [ ] Interface web (Django / Flask)

---

## 📄 Licença

Distribuído sob a licença presente em [LICENSE](./LICENSE).