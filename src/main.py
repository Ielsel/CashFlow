'''
Features:
    Adicionar despesas;
    Adicionar movimento das reservas;
    Adicionar import pandas
    Poder sacar e adicionar valores nas reservas já criadas
    Poder modificar o nome da reserva
    
Fix:
    Extrato é diferente do histórico de saldo, são valores depositados e saques
    Mostrar as reservas com melhor formatação pro usuário
'''
# Bibliotecas
from decimal import *

getcontext().prec = 4

#========================
# Adicionar nova reserva
#========================
def add_new_reserve(balance_history, balance, reserve, reserve_balance, reserve_name):
    '''
        Adiciona uma nova reserva definindo nome e valor, 
        subtraindo o valor do saldo para a nova reserva:
            nome: string, valor: Decimal
            Subtrai saldo: saldo = saldo - (valor da reserva)
    '''

    # Tratamento caso o valor incluído na reserva seja maior que o saldo ou seja negativo
    if balance < reserve_balance or reserve_balance < 0:
        return None
    
    balance -= reserve_balance # Subtrai do saldo o dinheiro depositado na reserva
    balance_history.append(balance) # Coloca o novo saldo no histórico
    reserve[reserve_name] = reserve_balance # Cria o novo item na lista de reserva
    return balance_history, balance, reserve # Retorna resultado

#========================
# Modificações de saldo
#========================
def available_balance_operations(balance_history, balance, balance_add, balance_option):
    '''
        Deposita, faz saque e atualiza o saldo:
            Depósito de saldo: saldo + valor_input
            Saque de saldo: saldo - valor_input
            Atualizar saldo: saldo = novo_saldo
            Histórico de saldo = lista de saldos
    '''

    # Depósito
    if balance_option == 2:
        #balance += Decimal(balance_add) # Adiciona o valor do input no saldo
        balance += balance_add
        balance_history.append(balance) # Adiciona o novo saldo na lista de histórico de saldos
        return balance_history, balance, balance_add # retorna valores atualizados
    
    # Saque
    elif balance_option == 3:
        balance -= balance_add # Subtrai o valor do input no saldo
        balance_history.append(balance) # Adiciona o novo saldo na lista de histórico de saldos
        return balance_history, balance, balance_add # retorna valores atualizados

    # Atualizar saldo
    elif balance_option == 4:
        balance = balance_add # Atribui o input ao saldo
        balance_history.append(balance)
        return balance_history, balance

#========================
# Interface menu de reservas
#========================
def reserve_menu(balance_history, balance, reserve):
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
                    reserve_balance = Decimal(input("Digite o valor da reserva: "))
                    add_new_reserve_result = add_new_reserve(balance_history, balance, reserve, reserve_balance, reserve_name)
                    if add_new_reserve_result is None:
                        print("Você não tem saldo suficiente!\nOBS: Verifique o valor do saldo\n")
                        continue
                    else:
                        balance_history, balance, reserve = add_new_reserve_result
                        print(f"Nova reserva adicionada!\n{reserve_name}: R${reserve_balance}\n")
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
def balance_menu(balance_history, balance):
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

                if balance_history == []:
                    print("\nSem extrato disponível!\n")
                else:
                    for balance_index in range(len(balance_history)):
                        print(f"{balance_index}º valor: R${balance_history[balance_index]}\n")

            elif balance_option == 2:
                try:
                    balance_add = Decimal(input("Adicione o valor: R$"))
                    balance_history, balance, balance_add = available_balance_operations(balance_history, balance, balance_add, balance_option)
                    print(f"Valor depositado: +R${balance_add}\nNovo saldo: R${balance}") 

                except Exception as error:
                    print(f"ERROR: {error}")
                    continue

                return balance_history, balance
            
            elif balance_option == 3:
                try:
                    balance_add = Decimal(input("Valor do saque: R$"))
                    if balance_add > balance:
                        print("Valor de saque maior que o saldo!")
                        continue
                    elif balance_add <= 0:
                        print("Valor de saque inválido!")
                        continue
                    else:
                        balance_history, balance, balance_add = available_balance_operations(balance_history, balance, balance_add, balance_option)
                        print(f"Saque feito com sucesso: -R${balance_add}\nNovo saldo: R${balance}")
                        continue

                except ValueError as error:
                    print(f"ERROR: {error}")
                    continue

            elif balance_option == 4:
                try:
                    if input("VOCÊ DESEJA ALTERAR O SALDO? ESSA AÇÃO NÃO PODE SER ALTERADA! YES/NO\nResposta: ") == "YES":
                        balance_add = Decimal(input("Novo valor do saldo: R$"))
                        balance_history, balance = available_balance_operations(balance_history, balance, balance_add, balance_option)
                        print(f"Valor alterado com sucesso!\nNovo saldo: R${balance}")
                        continue

                    else:
                        print("ATUALIZAÇÃO DE SALDO ABORTADA!\n")
                        continue

                except ValueError as error:
                    print(f"ERROR: {error}")
                    continue

            elif balance_option == 5:
                return balance_history, balance
            
        except ValueError as error:
            print(f"ERROR: {error}")
            continue

#========================
# Interface menu principal
#========================
def main_menu(balance_history, balance, reserve):
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
                balance_history, balance = balance_menu(balance_history, balance)

            elif value_menu_option == 2:

                if reserve == {}:
                    print("Nenhuma reserva criada!")

                else:
                    print(f"Reservas\n{reserve}")

                reserve_menu(balance_history, balance, reserve)

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
    #balance = 0
    balance_history = []
    reserve = {}

    main_menu(balance_history, balance, reserve)
    
main()