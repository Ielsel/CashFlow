'''
Features:
    Enhancements:
        - Sacar valores das reservas (reserva → saldo)
        - Adicionar valores em reservas existentes
        - Permitir edição do nome das reservas
        - Registrar movimentações de reservas no extrato

Fixes:
    - Corrigir precisão com Decimal em valores altos
    - Melhorar formatação da exibição de reservas
    - Atualizar e padronizar comentários do código

Tech Improvements:
    - Adicionar timestamp (data/hora) nas transações
    - Melhorar estrutura do extrato (DataFrame / exportação)

Future (Long-term):
    - Integração com banco de dados (SQLAlchemy)
    - Interface web (Django)
'''

# Bibliotecas
from decimal import *
import pandas as pd

getcontext().prec = 4

#========================
# Adicionar nova reserva
#========================
def add_new_reserve(account_statement, balance, reserve, amount, reserve_name):
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

    return account_statement, balance, reserve, amount, reserve_name # Retorna resultado

#========================
# Depósito de saldo
#========================
def balance_deposit(account_statement, balance, amount):
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
    
    return account_statement, balance, amount # retorna valores atualizados


#========================
# Saque de saldo
#========================
def balance_withdraw(account_statement, balance, amount):
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
    return account_statement, balance, amount # retorna valores atualizados

#========================
# Atualização de saldo
#========================
def balance_update(account_statement, balance, amount):
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

    return account_statement, balance, amount

#========================
# Interface menu de reservas
#========================
def reserve_menu(account_statement, balance, reserve):
    '''
        Menu de reservas, trás as opções:
            1 - Ver reservas: 
                mostrar nome e valor das reservas cadastradas
            2 - Criar reserva: 
                criar uma nova reserva com um nome que ainda não exista
            3 - Alterar reserva (em breve):
                Atualizar o valor e nome de qualquer reserva
            4 - Voltar:
                Voltar ao menu principal
    '''
    while True:
        print("--MENU RESERVAS--")
        try:
            reserve_option = int(input("1 - Ver reservas\n2 - Criar reserva\n3 - Alterar reserva (em breve)\n4 - Voltar\nResposta: "))

            if reserve_option == 1:
                if reserve == {}:
                    print("\nNenhuma reserva criada!\n")
                    continue
                else:
                    # Formatar melhor a resposta: adicionar reserve_name e reserve_value
                    print(f"\nReservas:\n{reserve}\n")
                    continue
            
            elif reserve_option == 2:
                reserve_name = input("Digite um nome para a nova reserva: ")

                # Verifica se já existe reserva com esse nome
                if reserve_name in reserve:
                    print("Já existe uma reserva com esse nome!")
                    continue
                
                try:
                    amount = Decimal(input("Digite o valor da reserva: "))
                    add_new_reserve_result = add_new_reserve(account_statement, balance, reserve, amount, reserve_name)
                    if add_new_reserve_result is None:
                        print("Você não tem saldo suficiente!\nOBS: Verifique o valor do saldo\n")
                        continue
                    else:
                        account_statement, balance, reserve, amount, reserve_name = add_new_reserve_result
                        print(f"Nova reserva adicionada!\n{reserve_name}: R${amount}\n")
                        continue

                except ValueError as error:
                    print(f"ERROR: {error}")
                    continue
            
            elif reserve_option == 4:
                break

        except ValueError as error:
            print(f"ERROR: {error}")
            continue

#========================
# Interface menu de saldo
#========================
def balance_menu(balance, account_statement):
    '''
        Menu de reservas, trás as opções:
            1 - Extrato:
                    mostrar extrato do movimento do saldo
            2 - Depositar:
                    chama available_balance_operations() pra depositar o saldo
            3 - Sacar:
                    chama available_balance_operations() pra sacar o saldo
            4 - Atualizar o valor do saldo:
                    chama available_balance_operations() pra atualizar o saldo
            5 - Voltar:
                Voltar ao menu principal
    '''
    while True:
        print("--MENU SALDO--")
        try:
            balance_option = int(input("1 - Extrato\n2 - Depositar\n3 - Sacar\n4 - Atualizar saldo\n5 - Voltar\nResposta: "))

            if balance_option == 1:
                print("\n--EXTRATO--")

                if account_statement == []:
                    print("\nSem extrato disponível!\n")
                else:
                    account_statement_dataframe = pd.DataFrame(data = account_statement)
                    print(f"\n{account_statement_dataframe}\n")

            elif balance_option == 2:
                try:
                    amount = Decimal(input("Adicione o valor: R$"))
                    account_statement, balance, amount = balance_deposit(account_statement, balance, amount)
                    #print(f"Valor depositado: +R${amount}\nNovo saldo: R${balance}") 
                    print(f"Valor depositado: +R${amount}\nNovo saldo: R${balance}") 

                except Exception as error:
                    print(f"ERROR: {error}")
                    continue
            
            elif balance_option == 3:
                try:
                    amount = Decimal(input("Valor do saque: R$"))
                    if amount > balance:
                        print("Valor de saque maior que o saldo!")
                        continue
                    elif amount <= 0:
                        print("Valor de saque inválido!")
                        continue
                    else:
                        account_statement, balance, amount = balance_withdraw(account_statement, balance, amount)
                        print(f"Saque feito com sucesso: -R${amount}\nNovo saldo: R${balance}")
                        continue

                except ValueError as error:
                    print(f"ERROR: {error}")
                    continue

            elif balance_option == 4:
                try:
                    if input("VOCÊ DESEJA ALTERAR O SALDO? ESSA AÇÃO NÃO PODE SER ALTERADA! YES/NO\nResposta: ") == "YES":
                        amount = Decimal(input("Novo valor do saldo: R$"))
                        account_statement, balance, amount = balance_update(account_statement, balance, amount)
                        print(f"Valor alterado com sucesso!\nNovo saldo: R${balance}")
                        continue

                    else:
                        print("ATUALIZAÇÃO DE SALDO ABORTADA!\n")
                        continue

                except ValueError as error:
                    print(f"ERROR: {error}")
                    continue

            elif balance_option == 5:
                return account_statement, balance
            
        except ValueError as error:
            print(f"ERROR: {error}")
            continue

#========================
# Interface menu principal
#========================
def main_menu(balance, reserve, account_statement):
    '''
        Menu principal, trás as opções:
            1 - Saldo:
                menu de saldos balance_menu()
            2 - Reservas:
                menu de reservas reserve_menu()
            3 - exit:
                finalizar
    '''

    while True:
        print(f"\nSaldo disponível: R${balance}")

        try:
            value_menu_option = int(input("Opções:\n1 - Saldo\n2 - Reservas\n3 - exit\nResposta: "))

            if value_menu_option == 1:
                balance, account_statement = balance_menu(balance, account_statement)

            elif value_menu_option == 2:

                if reserve == {}:
                    print("Nenhuma reserva criada!")

                else:
                    print(f"Reservas\n{reserve}")

                reserve_menu(account_statement, balance, reserve)

            elif value_menu_option == 3:
                print("...Finalizando CashFlow")
                return

        except ValueError as error:
            print(f"ERROR: {error}")
            continue
        
#========================
# Função principal
#========================
def main():
    '''
        Função principal, inicia as variáveis principais e chama o menu principal
    '''
    print("\n...Iniciando projeto CashFlow")

    balance = Decimal(0)
    reserve = {}
    account_statement = []

    main_menu(balance, reserve, account_statement)
    
main()