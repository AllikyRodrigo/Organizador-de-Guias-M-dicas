"""
Lógica de leitura das guias: separa o PDF do lote em uma página por arquivo
e renomeia cada uma com o número da guia, lido por OCR local (Tesseract).

Regra de renomeação:
  1. O título "GUIA DE CONSULTA" precisa estar visível (tolera erros do OCR);
  2. Deve haver um número de 7 dígitos (campo 2, no topo, ou campo 3, abaixo).

Uso pela linha de comando:  python guias.py lote.pdf
Uso pela interface:         python guias_app.py
"""
import csv
import os
import re
import shutil
import sys
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

import cv2
import fitz  # PyMuPDF
import numpy as np
import pytesseract

TITULO = "GUIA DE CONSULTA"
LIMIAR_TITULO = 0.85                      # 1.0 = idêntico; menor tolera mais erro
REGEX_GUIA = re.compile(r"(?<!\d)\d{7}(?!\d)")  # 7 dígitos (ajuste se mudar)
FRACAO_TOPO = 0.45                        # só o cabeçalho da guia
CFG_TEXTO = "--psm 6"
CFG_DIGITOS = "--psm 6 -c tessedit_char_whitelist=0123456789"


class ErroGuias(Exception):
    """Erro com mensagem amigável para mostrar ao usuário."""


def localizar_tesseract():
    """Procura o Tesseract: embutido no .exe, no PATH ou nas pastas padrão."""
    candidatos = []
    base = getattr(sys, "_MEIPASS", None)  # pasta interna do PyInstaller
    if base:
        embutido = Path(base) / "Tesseract-OCR"
        if (embutido / "tesseract.exe").is_file():
            os.environ["TESSDATA_PREFIX"] = str(embutido / "tessdata")
            candidatos.append(str(embutido / "tesseract.exe"))
    candidatos += [
        shutil.which("tesseract"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for c in candidatos:
        if c and Path(c).is_file():
            return c
    return None


TESSERACT = localizar_tesseract()
if TESSERACT:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT


def pagina_para_img(page, dpi=300):
    pix = page.get_pixmap(dpi=dpi)
    img = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, pix.n)
    codigo = cv2.COLOR_RGB2BGR if pix.n == 3 else cv2.COLOR_RGBA2BGR
    return cv2.cvtColor(img, codigo)


def gerar_variantes(img):
    """Várias versões do cabeçalho: ajuda quando a foto tem qualidade baixa."""
    topo = img[: int(img.shape[0] * FRACAO_TOPO)]
    cinza = cv2.GaussianBlur(cv2.cvtColor(topo, cv2.COLOR_BGR2GRAY), (3, 3), 0)

    otsu = cv2.threshold(cinza, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    adaptativa = cv2.adaptiveThreshold(
        cinza, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 35, 15
    )
    ampliada = cv2.resize(cinza, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
    ampliada = cv2.threshold(ampliada, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    return [otsu, adaptativa, ampliada]


def normalizar(txt):
    txt = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z ]", " ", txt.upper())


def tem_titulo(variantes):
    """True se 'GUIA DE CONSULTA' aparece (comparação aproximada, 3 palavras)."""
    for v in variantes:
        palavras = normalizar(pytesseract.image_to_string(v, config=CFG_TEXTO)).split()
        for i in range(len(palavras) - 2):
            trecho = " ".join(palavras[i : i + 3])
            if SequenceMatcher(None, trecho, TITULO).ratio() >= LIMIAR_TITULO:
                return True
    return False


def ler_numeros(variantes):
    votos = Counter()
    for v in variantes:
        txt = pytesseract.image_to_string(v, config=CFG_DIGITOS)
        votos.update(REGEX_GUIA.findall(txt))
    return votos


def analisar(img):
    """Retorna (numero | None, motivo, confianca)."""
    variantes = gerar_variantes(img)
    if not tem_titulo(variantes):
        return None, "sem_titulo", ""
    votos = ler_numeros(variantes)
    if not votos:
        return None, "sem_numero", ""
    ranking = votos.most_common()
    if len(ranking) > 1 and ranking[0][1] == ranking[1][1]:
        return None, "numeros_conflitantes", ""
    numero, qtd = ranking[0]
    return numero, "ok", ("alta" if qtd >= 2 else "media")


def salvar_pagina(doc, indice, destino):
    novo = fitz.open()
    novo.insert_pdf(doc, from_page=indice, to_page=indice)
    novo.save(destino)
    novo.close()


def pasta_resultado(pdf):
    """<nome do lote>_resultado, sem misturar com execuções anteriores."""
    base = pdf.parent / f"{pdf.stem}_resultado"
    n = 2
    while base.exists():
        base = pdf.parent / f"{pdf.stem}_resultado_{n}"
        n += 1
    return base


def processar_lote(caminho_pdf, ao_progresso=None, cancelar=None):
    """
    Processa o lote inteiro.
    ao_progresso(atual, total, mensagem) é chamado a cada página.
    cancelar: threading.Event; se ativado, para entre uma página e outra.
    Retorna dict com ok, revisar, pasta e cancelado.
    """
    if not TESSERACT:
        raise ErroGuias(
            "O Tesseract OCR não foi encontrado neste computador. "
            "Instale o programa e abra o aplicativo novamente."
        )
    pdf = Path(caminho_pdf).resolve()
    if not pdf.is_file() or pdf.suffix.lower() != ".pdf":
        raise ErroGuias("Selecione um arquivo PDF válido.")
    try:
        doc = fitz.open(pdf)
    except Exception:
        raise ErroGuias("Não foi possível abrir este PDF. O arquivo pode estar corrompido ou protegido.")
    if doc.page_count == 0:
        raise ErroGuias("O PDF não tem páginas.")

    base = pasta_resultado(pdf)
    saida, revisar = base / "guias", base / "revisar"
    saida.mkdir(parents=True)
    revisar.mkdir()

    total = doc.page_count
    ok = rev = 0
    cancelado = False
    linhas = [("pagina", "arquivo", "pasta", "motivo", "confianca")]

    for i in range(total):
        if cancelar is not None and cancelar.is_set():
            cancelado = True
            break
        try:
            numero, motivo, confianca = analisar(pagina_para_img(doc[i]))
        except Exception:
            numero, motivo, confianca = None, "erro_leitura", ""

        if numero:
            destino = saida / f"{numero}.pdf"
            if destino.exists():  # nunca sobrescrever
                motivo = "duplicada"
                destino = revisar / f"duplicada_{i + 1:03d}_{numero}.pdf"
        else:
            destino = revisar / f"pagina_{i + 1:03d}_{motivo}.pdf"

        salvar_pagina(doc, i, destino)
        if destino.parent == saida:
            ok += 1
        else:
            rev += 1
        linhas.append((i + 1, destino.name, destino.parent.name, motivo, confianca))
        if ao_progresso:  # sem dados de paciente: só página e nome do arquivo
            ao_progresso(i + 1, total, f"pág {i + 1}/{total}: {destino.parent.name}/{destino.name}")

    doc.close()
    with open(base / "relatorio.csv", "w", newline="", encoding="utf-8-sig") as f:
        csv.writer(f, delimiter=";").writerows(linhas)

    return {"ok": ok, "revisar": rev, "pasta": base, "cancelado": cancelado}


def main(caminho_pdf):
    try:
        r = processar_lote(caminho_pdf, ao_progresso=lambda i, t, m: print(m))
    except ErroGuias as e:
        sys.exit(str(e))
    print(f"\nConcluído: {r['ok']} reconhecidas, {r['revisar']} para revisar.")
    print(f"Resultado em: {r['pasta']}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uso: python guias.py lote.pdf")
    main(sys.argv[1])