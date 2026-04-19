from decimal import Decimal, ROUND_HALF_UP

#================================
# Formata os valores pro usuário
#================================
def cash_format(cash_value):
    return cash_value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

#=========================
# Alterar nome da reserva
#=========================
def rename_reserve(reserve, new_reserve_name, reserve_name):
    reserve[new_reserve_name] = reserve.pop(reserve_name)
    return reserve

#=========================
# Sacar valor reserva
#=========================
def reserve_withdraw(balance, reserve, amount_reserve_value, reserve_name):
    reserve[reserve_name] -= amount_reserve_value
    balance += amount_reserve_value
    return balance, reserve

#============================
# Depositar valor na reserva
#============================
def reserve_deposit(balance, reserve, amount_reserve_value, reserve_name):
    reserve[reserve_name] += amount_reserve_value
    balance -= amount_reserve_value
    return balance, reserve

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

    # Tratamento caso o valor incluído na reserva seja maior que o saldo ou seja negativo
    if balance < amount or amount < 0:
        return None
    
    balance -= amount # Subtrai do saldo o dinheiro depositado na reserva
    reserve[reserve_name] = amount # Cria o novo item na lista de reserva

    account_statement.append({
        "Operação": "Transferência reserva",
        "Valor": amount,
        "Saldo": balance
    })

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
    account_statement.append({
        "Operação": "Depósito",
        "Valor": amount,
        "Saldo": balance
    })
    
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
    account_statement.append({
        "Operação": "Saque",
        "Valor": amount,
        "Saldo": balance
    })
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

    account_statement.append({
        "Operação": "Atualização",
        "Valor": amount,
        "Saldo": balance
    })

    return balance, account_statement, amount