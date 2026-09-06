import customtkinter

# Função que vai ser chamada pelo botão
def button_callback():
    print("button pressed") # print no terminal (não na interface)

app = customtkinter.CTk()
app.title("my app") # Cabeçalho da aba
app.geometry("400x150") # Define o tamanho da tela

button = customtkinter.CTkButton(app, text="my button", command=button_callback) # Criação do botão
button.grid(row=0, column=0, padx=20, pady=20) # Define o formato do botão

app.mainloop()  # inicia a interface