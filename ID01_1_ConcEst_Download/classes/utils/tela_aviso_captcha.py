"""Tela de aviso para resolução manual de captcha.

Exibe uma janela sempre visível (topmost) que pausa a automação até o
usuário resolver o captcha no navegador e clicar em "Continuar".
"""

import logging
import tkinter as tk
from tkinter import ttk

logger = logging.getLogger(__name__)

TITULO_PADRAO = "Ação manual necessária"
MENSAGEM_PADRAO = (
    "Resolva o captcha ou token no navegador.\n\n"
    "Depois , clique em "
    "'Continuar' para liberar o robô."
)


class CaptchaNaoConfirmadoError(Exception):
    """Levantada quando o usuário fecha a janela sem confirmar."""


def aguardar_resolucao_captcha(
    titulo: str = TITULO_PADRAO,
    mensagem: str = MENSAGEM_PADRAO,
) -> None:
    """Bloqueia a execução até o usuário confirmar que resolveu o captcha.

    Args:
        titulo: Título da janela.
        mensagem: Texto exibido ao usuário.

    Raises:
        CaptchaNaoConfirmadoError: Se a janela for fechada pelo "X"
            sem clicar em "Continuar".
    """
    confirmado = False

    def _confirmar() -> None:
        nonlocal confirmado
        confirmado = True
        janela.destroy()

    janela = tk.Tk()
    janela.title(titulo)
    janela.resizable(False, False)
    janela.attributes("-topmost", True)
    janela.protocol("WM_DELETE_WINDOW", janela.destroy)

    quadro = ttk.Frame(janela, padding=20)
    quadro.pack(fill="both", expand=True)

    ttk.Label(
        quadro,
        text=mensagem,
        justify="center",
        wraplength=360,
        font=("Segoe UI", 11),
    ).pack(pady=(0, 15))

    botao = ttk.Button(quadro, text="Continuar", command=_confirmar)
    botao.pack(ipadx=20, ipady=4)
    botao.focus_set()

    # Posiciona no canto superior direito para não cobrir o captcha.
    janela.update_idletasks()
    largura = janela.winfo_width()
    pos_x = janela.winfo_screenwidth() - largura - 20
    janela.geometry(f"+{pos_x}+20")

    logger.info("Aguardando o usuário resolver o captcha manualmente.")
    janela.mainloop()

    if not confirmado:
        logger.error("Janela de captcha fechada sem confirmação.")
        raise CaptchaNaoConfirmadoError(
            "O usuário fechou a janela sem confirmar o captcha."
        )

    logger.info("Captcha confirmado pelo usuário. Robô liberado.")