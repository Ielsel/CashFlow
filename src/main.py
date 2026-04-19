'''
Features:
    Enhancements:
        - Registrar movimentações de reservas no extrato
        - Usar Pandas pra mostrar a reserva
        - Implementar classes (account_statement, Reserva) - Pensar mais sobre
        - Adicionar exclusão de uma reserva (retornar o valor da reserva para o saldo)

Fixes:
    - Melhorar formatação da exibição de reservas

Tech Improvements:
    - Adicionar timestamp (data/hora) nas transações
    - Melhorar estrutura do extrato (DataFrame / exportação)

Future (Long-term):
    - Integração com banco de dados (SQLAlchemy)
    - Interface web (Django)
'''

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
            reserve_option = int(input("1 - Ver reservas\n2 - Criar reserva\n3 - Alterar reserva\n4 - Voltar\nResposta: "))

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
                    # Formatar melhor a resposta: adicionar reserve_name e reserve_value
                    print(f"\nReservas:\n{reserve}\n")
                    continue
                
            # Criar reserva
            elif reserve_option == 2:
                reserve_name = input("Digite um nome para a nova reserva: ")

                # Verifica se já existe reserva com esse nome
                if reserve_name in reserve:
                    print("Já existe uma reserva com esse nome!")
                    continue
                
                try:
                    amount = Decimal(input("Digite o valor da reserva: "))
                    add_new_reserve_result = add_new_reserve(balance, account_statement, reserve, amount, reserve_name)
                    if add_new_reserve_result is None:
                        print("Você não tem saldo suficiente!\nOBS: Verifique o valor do saldo\n")
                        continue
                    else:
                        balance, account_statement, reserve, amount, reserve_name = add_new_reserve_result
                        print(f"Nova reserva adicionada!\n{reserve_name}: R${cash_format(amount)}\n")
                        continue

                except ValueError as error:
                    print(f"ERROR: {error}")
                    continue
            
            # Alterar reserva
            elif reserve_option == 3:

                if have_reserve:    

                    reserve_name = input(f"Digite o nome da reserva que deseja alterar\n{reserve}\nResposta: ")

                    # Verifica se existe reserva com o nome digitado
                    if reserve_name in reserve:
                        try:
                            type_modification = int(input(f"O que você deseja alterar da reserva {reserve_name}?\n1 - Alterar nome\n2 - Depositar valor\n3 - Sacar valor\nResposta:"))

                            if type_modification == 1:
                                new_reserve_name = input(f"Digite o novo nome da reserva {reserve_name}\n Resposta: ")
                                reserve = rename_reserve(reserve, new_reserve_name, reserve_name)

                            elif type_modification == 2:
                                amount_reserve_value = Decimal(input(f"Digite o valor de depósito para a reserva {reserve_name}\n Resposta: "))
                                balance, reserve = reserve_deposit(balance, reserve, amount_reserve_value, reserve_name)

                            elif type_modification == 3:
                                amount_reserve_value = Decimal(input(f"Digite o valor de saque para a reserva {reserve_name}\n Resposta: "))
                                balance, reserve = reserve_withdraw(balance, reserve, amount_reserve_value, reserve_name)

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

            # Voltar
            elif reserve_option == 4:
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
                    amount = Decimal(input("Adicione o valor: R$"))
                    balance, account_statement, amount = balance_deposit(balance, account_statement, amount)
                    print(f"Valor depositado: +R${cash_format(amount)}\nNovo saldo: R${cash_format(balance)}") 

                except Exception as error:
                    print(f"ERROR: {error}")
                    continue
            
            # Sacar
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
                        balance, account_statement, amount = balance_withdraw(balance, account_statement, amount)
                        print(f"Saque feito com sucesso: -R${cash_format(amount)}\nNovo saldo: R${cash_format(balance)}")
                        continue

                except ValueError as error:
                    print(f"ERROR: {error}")
                    continue
            
            # Atualizar saldo
            elif balance_option == 4:
                try:
                    if input("VOCÊ DESEJA ALTERAR O SALDO? ESSA AÇÃO NÃO PODE SER ALTERADA! YES/NO\nResposta: ") == "YES":
                        amount = Decimal(input("Novo valor do saldo: R$"))
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
                    print(f"Reservas\n{reserve}")

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