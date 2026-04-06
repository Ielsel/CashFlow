'''
Adicionar despesas
Mudar a função "Alterar saldo" pra "Atualizar saldo" pra poder fazer o cálculo de ganho de investimento líquido
Transformar o saldo em lista pra ter os dados da movimentação do saldo
Adicionar movimento saldo <-> reserva
Poder sacar valores das reservas
'''

# adicionar nova reserva
def new_reserve(balance, reserve):

    reserve_name = input("Digite um nome para a nova reserva: ")

    if reserve_name in reserve:
        print("Já existe uma reserva com esse nome")
        return balance, reserve

    try:
        reserve_balance = float(input("Digite o valor da reserva: "))
    except ValueError:
        print("ERRO: VALOR INVÁLIDO")
        return balance, reserve

    if balance < reserve_balance or reserve_balance < 0:
        print("Você não tem esse valor para adicionar na caixinha\nOBS: Verifique o valor do balance")
        return balance, reserve
    
    balance -= reserve_balance
    reserve[reserve_name] = reserve_balance
    return balance, reserve

# modificações de saldo
def modify_balance(balance):
    balance_before = balance

    try:
        balance_option = int(input("1 - Alterar valor do saldo\n2 - Adicionar saldo"))
    except ValueError:
        print("ERRO: VALOR INVÁLIDO")
        return balance

    if balance_option == 1:
        balance = float(input("Novo saldo: R$"))
    elif balance_option == 2:
        balance_add = float(input("Valor do saldo adicionado: R$"))
        balance += balance_add

    balance_after = balance
    print(f"Valor adicionado: R${balance_after}\nDiferença de valor: R${balance_after - balance_before}\n")
    return balance_after

# Função de gestão de opções
def answer_options():
    balance = 0
    reserve = {}

    while True:
        print(f"\nSaldo disponível: R${balance}")
        try:
            main_option = int(input("Opções:\n1 - Saldo\n2 - Reservas\n3 - exit\n"))
        except ValueError:
            print("ERRO: VALOR INVÁLIDO")
            continue

        if main_option == 1:
                balance = modify_balance(balance)
    
        elif main_option == 2:
            if reserve == {}:
                print("Nenhuma reserva criada!")
            else:
                print(f"Reservas\n{reserve}")

            try:
                new_reserve_option = int(input("Deseja adicionar uma nova reserva? 1/s 2/n "))
            except ValueError:
                print("ERRO: VALOR INVÁLIDO")
                continue

            if new_reserve_option == 1:
                balance, reserve = new_reserve(balance, reserve)

        elif main_option == 3:
            break

# função principal
def main():
    print("\n...Iniciando projeto CashFlow")
    answer_options()
    
main()