'''
Features:
    Adicionar despesas;
    Criar confirmação pra opção Alterar saldo;
    Transformar o saldo em balance_history(list) e deixar balance como float padrão;
    Adicionar movimento das reservas;
    Adicionar import pandas
    Adicionar import decimal
    Poder sacar e adicionar valores nas reservas já criadas.
'''

#========================
# Adicionar nova reserva
#========================
def add_new_reserve(balance, reserve, reserve_balance, reserve_name):
    '''
        Adiciona uma nova reserva definindo nome e valor, 
        subtraindo o valor do saldo para a nova reserva:
            nome: string, valor: float
            Subtrai saldo: saldo = saldo - (valor da reserva)
    '''
    balance_value = balance[-1]

    if balance[-1] < reserve_balance or reserve_balance < 0:
        return None
    
    balance_value -= reserve_balance
    balance.append(balance_value)
    reserve[reserve_name] = reserve_balance
    return balance, reserve

#========================
# Modificações de saldo
#========================
def available_balance_operations(balance, balance_add, balance_option):
    '''
        Adiciona e atualiza o saldo:
            Adicionar saldo: saldo + novo saldo
            Atualizar saldo: saldo = novo saldo
    '''
    if balance_option == 2:
        balance_add += balance[-1]
        balance.append(balance_add)

    elif balance_option == 3:
        balance.append(balance_add)

    return balance, balance_add

#========================
# Interface IO reserve
#========================
def reserve_menu(balance, reserve):
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
                print(f"\nReservas:\n{reserve}\n")
                continue
            
            elif reserve_option == 2:
                reserve_name = input("Digite um nome para a nova reserva: ")

                if reserve_name in reserve:
                    print("Já existe uma reserva com esse nome!")
                    continue
                
                try:
                    reserve_balance = float(input("Digite o valor da reserva: "))
                    add_new_reserve_result = add_new_reserve(balance, reserve, reserve_balance, reserve_name)
                    if add_new_reserve_result is None:
                        print("Você não tem esse valor para adicionar na caixinha\nOBS: Verifique o valor do balance\n")
                        continue
                    else:
                        balance, reserve = add_new_reserve_result
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
# Interface IO balance
#========================
def balance_menu(balance):
    '''
        Menu de reservas, trás as opções:
            1 - Ver extrato:
                    mostrar extrato do movimento do saldo
            2 - Adicionar saldo:
                    chama available_balance_operations() pra adicionar o saldo
            3 - Atualizar o valor do saldo
                    chama available_balance_operations() pra atualizar o saldo
            4 - Voltar:
                Voltar ao menu principal
    '''
    while True:
        print("--MENU SALDO--")
        try:
            balance_option = int(input("1 - Ver extrato\n2 - Adicionar saldo\n3 - Atualizar o valor do saldo\n4 - Voltar\nResposta: "))

            if balance_option == 1:
                print("\n--EXTRATO--")

                for balance_extract in range(len(balance)):
                    print(f"{balance_extract}º valor: R${balance[balance_extract]}\n")

            elif balance_option == 2:
                try:
                    balance_add = float(input("Adicione o valor: R$"))
                    available_balance_operations(balance, balance_add, balance_option)
                    print(f"Valor adicionado com sucesso!: +R${balance_add}\n")

                except Exception as error:
                    print(f"ERROR: {error}")
                    continue

                return balance
        
            elif balance_option == 4:
                break
            
        except ValueError as error:
            print(f"ERROR: {error}")
            continue

#========================
# Interface IO main menu
#========================
def main_menu(balance, reserve):
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
        print(f"\nSaldo disponível: R${balance[-1]}")

        try:
            value_menu_option = int(input("Opções:\n1 - Saldo\n2 - Reservas\n3 - exit\nResposta: "))

            if value_menu_option == 1:
                balance_menu(balance)

            elif value_menu_option == 2:

                if reserve == {}:
                    print("Nenhuma reserva criada!")

                else:
                    print(f"Reservas\n{reserve}")

                reserve_menu(balance, reserve)

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
    balance = [0]
    reserve = {}
    main_menu(balance, reserve)
    
main()