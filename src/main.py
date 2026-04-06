# adicionar nova reserva
def add_reservation(saldo, reservation):

    reservation_name = input("Digite um nome para a nova reserva: ")

    if reservation_name in reservation:
        print("Já existe uma reserva com esse nome")
        return saldo, reservation

    try:
        reservation_value = float(input("Digite o valor da reserva: "))
    except ValueError:
        print("ERRO: VALOR INVÁLIDO")
        return saldo, reservation

    if saldo < reservation_value or reservation_value < 0:
        print("Você não tem esse valor para adicionar na caixinha\nOBS: Verifique o valor do saldo")
        return saldo, reservation
    
    saldo -= reservation_value
    reservation[reservation_name] = reservation_value
    return saldo, reservation

# modificações de saldo
def modify_saldo(saldo):
    saldo_before = saldo

    try:
        saldo_option = int(input("1 - Alterar valor do saldo\n2 - Adicionar saldo"))
    except ValueError:
        print("ERRO: VALOR INVÁLIDO")
        return saldo

    if saldo_option == 1:
        saldo = float(input("Novo saldo: R$"))
    elif saldo_option == 2:
        saldo_add = float(input("Valor do saldo adicionado: R$"))
        saldo += saldo_add

    saldo_after = saldo
    print(f"Valor adicionado: R${saldo_after}\nDiferença de valor: R${saldo_after - saldo_before}\n")
    return saldo_after

# Função de gestão de opções
def answer_options():
    saldo = 0
    reservation = {}

    while True:
        print(f"\nSaldo disponível: R${saldo}")
        try:
            main_option = int(input("Opções:\n1 - Saldo\n2 - Reservas\n3 - exit\n"))
        except ValueError:
            print("ERRO: VALOR INVÁLIDO")
            continue

        if main_option == 1:
                saldo = modify_saldo(saldo)
    
        elif main_option == 2:
            if reservation == {}:
                print("Nenhuma reserva criada!")
            else:
                print(f"Reservas\n{reservation}")

            try:
                new_reservation = int(input("Deseja adicionar uma nova reserva? 1/s 2/n "))
            except ValueError:
                print("ERRO: VALOR INVÁLIDO")
                continue

            if new_reservation == 1:
                saldo, reservation = add_reservation(saldo, reservation)

        elif main_option == 3:
            break

# função principal
def main():
    print("\n...Iniciando projeto CashFlow")
    answer_options()
    
main()