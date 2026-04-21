from decimal import Decimal, ROUND_HALF_UP
import datetime

#====================================
# Verifica a validade das transações
#====================================
def transaction_verify(balance, amount):
    if balance < amount or amount < 0:
        return False
    else:
        return True

#==============
# Formata data
#==============
def date_format():
    return datetime.datetime.now().strftime("%d/%m/%y")

#================================
# Formata os valores pro usuário
#================================
def cash_format(cash_value):
    return cash_value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

#===============================
# Adiciona operações no extrato
#===============================
def add_account_statement(type_account_operation, account_statement, amount, balance):
    account_statement.append({
        "Data": date_format(),
        "Operação": type_account_operation,
        "Valor": amount,
        "Saldo": balance
    })

    return account_statement

#=========================
# Alterar nome da reserva
#=========================
def reserve_rename(reserve, new_reserve_name, reserve_name):
    reserve[new_reserve_name] = reserve.pop(reserve_name)
    return reserve

#=========================
# Sacar valor reserva
#=========================
def reserve_withdraw(balance, reserve, amount_reserve_value, reserve_name, account_statement):
    reserve[reserve_name] -= amount_reserve_value
    balance += amount_reserve_value
    add_account_statement(f"Saque {reserve_name}", account_statement, amount_reserve_value, balance)
    return balance, reserve, account_statement

#============================
# Depositar valor na reserva
#============================
def reserve_deposit(balance, reserve, amount_reserve_value, reserve_name, account_statement):
    reserve[reserve_name] += amount_reserve_value
    balance -= amount_reserve_value
    add_account_statement(f"Depósito {reserve_name}", account_statement, amount_reserve_value, balance)
    return balance, reserve, account_statement

#=========================
# Deletar reserva
#=========================
def reserve_delete(balance, account_statement, reserve, reserve_name):
    amount_reserve_value = reserve[reserve_name]
    balance, reserve, account_statement = reserve_withdraw(balance, reserve, amount_reserve_value, reserve_name, account_statement)
    reserve.pop(reserve_name)
    return balance, reserve, account_statement

#=========================
# Adicionar nova reserva
#=========================
def add_new_reserve(balance, account_statement, reserve, amount, reserve_name):
    '''
        Adiciona uma nova reserva definindo nome e valor, 
        subtraindo o valor do saldo para a nova reserva:
            nome: string, valor: Decimal
            Subtrai saldo: saldo = saldo - (valor da reserva)
    '''

    balance -= amount # Subtrai do saldo o dinheiro depositado na reserva
    reserve[reserve_name] = amount # Cria o novo item na lista de reserva
    add_account_statement("Transferência reserva", account_statement, amount, balance)

    return balance, account_statement, reserve, amount, reserve_name # Retorna resultado

#========================
# Depósito de saldo
#========================
def balance_deposit(balance, account_statement, amount):
    '''
        Deposita valor no saldo:
            Depósito de saldo: saldo + valor_input
    '''

    balance += amount
    add_account_statement("Depósito", account_statement, amount, balance)

    return balance, account_statement, amount # retorna valores atualizados


#========================
# Saque de saldo
#========================
def balance_withdraw(balance, account_statement, amount):
    '''
        Sacar valor do saldo:
            Saque de saldo: saldo - valor_input
    '''
    
    balance -= amount # Subtrai o valor do input no saldo
    add_account_statement("Saque", account_statement, amount, balance)
    return balance, account_statement, amount # retorna valores atualizados

#========================
# Atualização de saldo
#========================
def balance_update(balance, account_statement, amount):
    '''
        Atualizar saldo: saldo = novo_saldo
            Histórico de saldo = lista de saldos
    ''' 

    balance = amount # Atribui o input ao saldo
    add_account_statement("Atualização de saldo", account_statement, amount, balance)

    return balance, account_statement, amount