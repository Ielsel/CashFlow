'''
Features:
    Enhancements:
        - Implementar classes (account_statement, Reserva) - Pensar mais sobre x

Fixes:
    - Melhorar formatação da exibição de reservas

Future (Long-term):
    - Integração com banco de dados (SQLAlchemy)
    - Interface web (Django)
'''

# ! Esse código vai ser substituito por app

# Imports
from decimal import Decimal, getcontext
import pandas as pd
from tools import *

getcontext().prec = 28

#============================
# Interface menu de reservas
#============================
def reserve_menu(balance, account_statement, reserve):
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
            reserve_option = int(input("1 - Ver reservas\n2 - Criar reserva\n3 - Alterar reserva\n4 - Excluir reserva\n5 - Voltar\nResposta: "))

            if reserve == {}:              
                have_reserve = False
            else:
                have_reserve = True

            # Ver reservas
            if reserve_option == 1:
                if have_reserve == False:
                    print("\nNenhuma reserva criada!\n")
                    continue
                else:
                    for name, value in reserve.items():
                        print(f"{name}: R${cash_format(value)}")
                    continue
                
            # Criar reserva
            elif reserve_option == 2:
                reserve_name = input("Digite um nome para a nova reserva: ")

                # Verifica se já existe reserva com esse nome
                if reserve_name in reserve:
                    print("Já existe uma reserva com esse nome!")
                    continue
                
                try:
                    amount = Decimal(input("Digite o valor da reserva: ").replace(",", "."))

                    if transaction_verify(balance, amount):
                        balance, account_statement, reserve, amount, reserve_name = add_new_reserve(balance, account_statement, reserve, amount, reserve_name)
                        print(f"Nova reserva adicionada!\n{reserve_name}: R${cash_format(amount)}\n")
                        continue
                        
                    else:
                        print("Você não tem saldo suficiente!\nOBS: Verifique o valor do saldo\n")
                        continue

                except ValueError as error:
                    print(f"ERROR: {error}")
                    continue
            
            # Alterar reserva
            elif reserve_option == 3:

                if have_reserve:    

                    print("\nReservas disponíveis:")
                    for name, value in reserve.items():
                        print(f"- {name}: R${cash_format(value)}")

                    reserve_name = input("Digite o nome da reserva: ")

                    # Verifica se existe reserva com o nome digitado
                    if reserve_name in reserve:
                        try:
                            type_modification = int(input(f"O que você deseja alterar da reserva {reserve_name}?\n1 - Alterar nome\n2 - Depositar valor\n3 - Sacar valor\nResposta:"))

                            # Alterar nome da reserva
                            if type_modification == 1:

                                new_reserve_name = input(f"Digite o novo nome da reserva {reserve_name}\n Resposta: ")

                                if new_reserve_name in reserve:
                                    print("Já existe uma reserva com esse nome!")
                                    continue
                                else:
                                    reserve = reserve_rename(reserve, new_reserve_name, reserve_name)
                                    continue

                            # Depositar valor na reserva
                            elif type_modification == 2:
                                amount_reserve_value = Decimal(input(f"Digite o valor de depósito para a reserva {reserve_name}\n Resposta: ").replace(",", "."))

                                if transaction_verify(balance, amount_reserve_value):
                                    balance, reserve, account_statement = reserve_deposit(balance, reserve, amount_reserve_value, reserve_name, account_statement)
                                    print(f"Valor de R${cash_format(amount_reserve_value)} depositado na reserva {reserve_name}\nNovo saldo: R${cash_format(balance)}")
                                    continue
                                else:
                                    print("Você não tem saldo suficiente!\nOBS: Verifique o valor do saldo\n")
                                    continue

                            # Sacar valor da reserva
                            elif type_modification == 3:
                                amount_reserve_value = Decimal(input(f"Digite o valor de saque para a reserva {reserve_name}\n Resposta: ").replace(",", "."))

                                if transaction_verify(reserve[reserve_name], amount_reserve_value):
                                    balance, reserve, account_statement = reserve_withdraw(balance, reserve, amount_reserve_value, reserve_name, account_statement)
                                    print(f"Valor de R${cash_format(amount_reserve_value)} sacado da reserva {reserve_name}\nNovo saldo: R${cash_format(balance)}")
                                    continue
                                else:
                                    print("Saldo da reserva insuficiente!\nOBS: Verifique o valor da reserva\n")
                                    continue

                            else:
                                print("O valor digitado é inválido!")
                        
                        except ValueError as error:
                            print(f"ERROR: {error}")
                            continue
                    
                    else:
                        print(f"\nNão existe reserva \"{reserve_name}\"\n")
                        continue

                else:
                    print("\nNenhuma reserva criada para ser alterada!\n")
            
            # Excluir reserva
            elif reserve_option == 4:
                print("\nReservas disponíveis:")
                for name, value in reserve.items():
                    print(f"- {name}: R${cash_format(value)}")

                reserve_name = input("Digite o nome da reserva: ")

                if reserve_name in reserve:
                    balance, reserve, account_statement = reserve_delete(balance, account_statement, reserve, reserve_name)
                    print(f"Reserva {reserve_name} excluída com sucesso!")

                else:
                    print(f"\nNão existe reserva \"{reserve_name}\"\n")
                    continue

            # Voltar
            elif reserve_option == 5:
                return balance, account_statement, reserve
            
            else:
                print("O valor digitado é inválido!")

        except ValueError as error:
            print(f"ERROR: {error}")
            continue

#============================
# Interface menu de saldo
#============================
def balance_menu(balance, account_statement):
    '''
        Menu de reservas, trás as opções:
            1 - Extrato:
                    mostrar extrato do movimento do saldo
            2 - Depositar:
                    chama available_balance_operations() pra depositar o saldo
            3 - Sacar:
                    chama available_balance_operations() pra sacar o saldo
            4 - Atualizar saldo:
                    chama available_balance_operations() pra atualizar o saldo
            5 - Voltar:
                    Voltar ao menu principal
    '''
    while True:
        print("--MENU SALDO--")
        try:
            balance_option = int(input("1 - Extrato\n2 - Depositar\n3 - Sacar\n4 - Atualizar saldo\n5 - Voltar\nResposta: "))

            # Extrato
            if balance_option == 1:
                print("\n--EXTRATO--")

                if account_statement == []:
                    print("\nSem extrato disponível!\n")
                else:
                    account_statement_dataframe = pd.DataFrame(data = account_statement)
                    print(f"\n{account_statement_dataframe}\n")

            # Depositar
            elif balance_option == 2:
                try:
                    amount = Decimal(input("Adicione o valor: R$").replace(",", "."))

                    if amount <= 0:
                        print("\nValor de depósito inválido!\n")
                    else:
                        balance, account_statement, amount = balance_deposit(balance, account_statement, amount)
                        print(f"Valor depositado: +R${cash_format(amount)}\nNovo saldo: R${cash_format(balance)}") 

                except Exception as error:
                    print(f"ERROR: {error}")
                    continue
            
            # Sacar
            elif balance_option == 3:
                try:
                    amount = Decimal(input("Valor do saque: R$").replace(",", "."))

                    if transaction_verify(balance, amount):
                        balance, account_statement, amount = balance_withdraw(balance, account_statement, amount)
                        print(f"Saque feito com sucesso: -R${cash_format(amount)}\nNovo saldo: R${cash_format(balance)}")
                        continue

                    else:
                        print("Valor de saque inválido!")
                        continue

                except ValueError as error:
                    print(f"ERROR: {error}")
                    continue
            
            # Atualizar saldo
            elif balance_option == 4:
                try:
                    if input("VOCÊ DESEJA ALTERAR O SALDO? ESSA AÇÃO NÃO PODE SER ALTERADA! YES/NO\nResposta: ") == "YES":
                        amount = Decimal(input("Novo valor do saldo: R$").replace(",", "."))
                        balance, account_statement, amount = balance_update(balance, account_statement, amount)
                        print(f"Valor alterado com sucesso!\nNovo saldo: R${cash_format(balance)}")
                        continue

                    else:
                        print("ATUALIZAÇÃO DE SALDO ABORTADA!\n")
                        continue

                except ValueError as error:
                    print(f"ERROR: {error}")
                    continue
            
            # voltar
            elif balance_option == 5:
                return balance, account_statement
            
            else:
                print("O valor digitado é inválido!")
            
        except ValueError as error:
            print(f"ERROR: {error}")
            continue

#============================
# Interface menu principal
#============================
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
        print(f"\nSaldo disponível: R${cash_format(balance)}")

        try:
            value_menu_option = int(input("Opções:\n1 - Saldo\n2 - Reservas\n3 - exit\nResposta: "))

            # Menu de saldo
            if value_menu_option == 1:
                balance, account_statement = balance_menu(balance, account_statement)

            # Menu de reservas
            elif value_menu_option == 2:

                if reserve == {}:
                    print("Nenhuma reserva criada!")

                else:
                    print("Reservas:")
                    for name, value in reserve.items():
                        print(f"- {name}: R${cash_format(value)}")

                balance, account_statement, reserve = reserve_menu(balance, account_statement, reserve)

            # Exit
            elif value_menu_option == 3:
                print("...Finalizando CashFlow")
                return

        except ValueError as error:
            print(f"ERROR: {error}")
            continue
        
#============================
# Função principal
#============================
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