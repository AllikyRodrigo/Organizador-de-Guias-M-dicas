"""
Interface gráfica: solte o PDF do lote na janela (ou clique em escolher)
e o programa separa e renomeia as guias sozinho.
"""
import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import guias

try:  # arrastar e soltar (opcional: pip install tkinterdnd2)
    from tkinterdnd2 import DND_FILES, TkinterDnD

    JanelaBase = TkinterDnD.Tk
    TEM_DND = True
except Exception:
    JanelaBase = tk.Tk
    TEM_DND = False


class App(JanelaBase):
    def __init__(self):
        super().__init__()
        self.title("Organizador de Guias")
        self.geometry("620x560")
        self.minsize(520, 480)

        self.fila = queue.Queue()
        self.cancelar = threading.Event()
        self.trabalhando = False
        self.pasta_resultado = None

        self._montar()
        self.after(100, self._checar_fila)

        if not guias.TESSERACT:
            messagebox.showerror(
                "Tesseract não encontrado",
                "O Tesseract OCR não está instalado neste computador.\n\n"
                "Instale o programa e abra o aplicativo novamente.",
            )

    def _montar(self):
        pad = {"padx": 16, "pady": 6}
        ttk.Label(self, text="Organizador de Guias", font=("Segoe UI", 16, "bold")).pack(pady=(16, 0))
        ttk.Label(
            self,
            text="Envie o PDF com todas as guias do lote. Cada página será\n"
            "separada e salva com o número da guia.",
            justify="center",
        ).pack(**pad)

        texto_zona = "Solte o PDF aqui\n\nou clique para escolher o arquivo" if TEM_DND else "Clique aqui para escolher o PDF do lote"
        self.zona = tk.Label(
            self, text=texto_zona, font=("Segoe UI", 12), height=6,
            relief="groove", bd=2, bg="#f2f6fb", cursor="hand2",
        )
        self.zona.pack(fill="x", padx=16, pady=8)
        self.zona.bind("<Button-1>", lambda e: self.escolher())
        if TEM_DND:
            self.zona.drop_target_register(DND_FILES)
            self.zona.dnd_bind("<<Drop>>", self._soltou)

        self.status = ttk.Label(self, text="Aguardando o PDF do lote.")
        self.status.pack(**pad)
        self.barra = ttk.Progressbar(self, mode="determinate")
        self.barra.pack(fill="x", padx=16)

        quadro = ttk.Frame(self)
        quadro.pack(fill="both", expand=True, padx=16, pady=8)
        self.log = tk.Text(quadro, height=8, state="disabled", wrap="word", font=("Consolas", 9))
        rolagem = ttk.Scrollbar(quadro, command=self.log.yview)
        self.log.configure(yscrollcommand=rolagem.set)
        self.log.pack(side="left", fill="both", expand=True)
        rolagem.pack(side="right", fill="y")

        botoes = ttk.Frame(self)
        botoes.pack(pady=(0, 16))
        self.b_cancelar = ttk.Button(botoes, text="Cancelar", command=self.cancelar.set, state="disabled")
        self.b_cancelar.pack(side="left", padx=6)
        self.b_abrir = ttk.Button(botoes, text="Abrir pasta do resultado", command=self.abrir_pasta, state="disabled")
        self.b_abrir.pack(side="left", padx=6)

    # ---- entrada do arquivo ----
    def escolher(self):
        if self.trabalhando:
            return
        caminho = filedialog.askopenfilename(title="Escolha o PDF do lote", filetypes=[("PDF", "*.pdf")])
        if caminho:
            self.iniciar(caminho)

    def _soltou(self, evento):
        arquivos = self.tk.splitlist(evento.data)
        if arquivos:
            self.iniciar(arquivos[0])

    # ---- processamento em segundo plano ----
    def iniciar(self, caminho):
        if self.trabalhando:
            return
        if Path(caminho).suffix.lower() != ".pdf":
            messagebox.showwarning("Arquivo inválido", "Selecione um arquivo PDF.")
            return
        self.trabalhando = True
        self.cancelar.clear()
        self.pasta_resultado = None
        self.barra["value"] = 0
        self.status.config(text="Processando...")
        self.b_cancelar.config(state="normal")
        self.b_abrir.config(state="disabled")
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")
        threading.Thread(target=self._trabalho, args=(caminho,), daemon=True).start()

    def _trabalho(self, caminho):
        try:
            res = guias.processar_lote(
                caminho,
                ao_progresso=lambda i, t, m: self.fila.put(("progresso", i, t, m)),
                cancelar=self.cancelar,
            )
            self.fila.put(("fim", res))
        except guias.ErroGuias as e:
            self.fila.put(("erro", str(e)))
        except Exception as e:  # só o tipo do erro, nunca dados da guia
            self.fila.put(("erro", f"Erro inesperado ({type(e).__name__})."))

    def _checar_fila(self):
        try:
            while True:
                item = self.fila.get_nowait()
                if item[0] == "progresso":
                    _, i, total, msg = item
                    self.barra["maximum"] = total
                    self.barra["value"] = i
                    self.status.config(text=f"Processando página {i} de {total}...")
                    self._escrever(msg)
                elif item[0] == "fim":
                    self._finalizar(item[1])
                elif item[0] == "erro":
                    self._terminar()
                    self.status.config(text="Não foi possível concluir.")
                    messagebox.showerror("Erro", item[1])
        except queue.Empty:
            pass
        self.after(100, self._checar_fila)

    def _escrever(self, msg):
        self.log.config(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def _terminar(self):
        self.trabalhando = False
        self.b_cancelar.config(state="disabled")

    def _finalizar(self, r):
        self._terminar()
        self.pasta_resultado = r["pasta"]
        self.b_abrir.config(state="normal")
        resumo = f"{r['ok']} guia(s) reconhecida(s) e {r['revisar']} para revisar."
        if r["cancelado"]:
            resumo = "Cancelado. " + resumo
        self.status.config(text=resumo)
        self._escrever("\n" + resumo)
        if r["revisar"]:
            messagebox.showinfo(
                "Concluído",
                resumo + "\n\nConfira a pasta 'revisar' e renomeie à mão o que faltar.",
            )
        else:
            messagebox.showinfo("Concluído", resumo)

    def abrir_pasta(self):
        if self.pasta_resultado and Path(self.pasta_resultado).exists():
            os.startfile(self.pasta_resultado)  # Windows


if __name__ == "__main__":
    App().mainloop()