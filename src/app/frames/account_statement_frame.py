import customtkinter as ctk
import pandas as pd
from ..tools import cash_format

# todo: Melhorar a aparência geral do código usando o claude.ai

class account_statement_frame(ctk.CTkFrame):
    def __init__(self, master, app,**kwargs):
        super().__init__(master, **kwargs)

        self.app = app

        # Título
        self.title_menu = ctk.CTkLabel(self, text="Extrato")
        self.title_menu.grid(row=0, column=0, padx=20, pady=20, columnspan=2)

        self.statement_box = ctk.CTkTextbox(self, width=400, height=200)
        self.statement_box.grid(row=8, column=0, columnspan=2, padx=20, pady=10)

        # Voltar pro menu de saldo
        self.btn_exit = ctk.CTkButton(self, text="Voltar", command=self.app.show_balance)
        self.btn_exit.grid(row=6, column=0, columnspan=2, padx=20, pady=20)

        self.display_account_statement()
        
    #===========
    # Funções
    #===========
    def display_account_statement(self):
        self.statement_box.configure(state="normal")
        self.statement_box.delete("1.0", "end")

        if self.app.account_statement == []:
            self.statement_box.insert("end", "Sem extrato disponível!")
        else:
            df = pd.DataFrame(self.app.account_statement)

            df["Valor"] = df["Valor"].apply(lambda x: f"R${str(cash_format(x)).replace('.', ',')}")
            df["Saldo"] = df["Saldo"].apply(lambda x: f"R${str(cash_format(x)).replace('.', ',')}")

            self.statement_box.insert("end", df.to_string(index=False, col_space=15))

        self.statement_box.configure(state="disabled")