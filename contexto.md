# Contexto: Organizador de Guias (faturamento)

## Objetivo
Eliminar o trabalho manual de abrir cada guia de consulta no PDF24, ler o número e renomear o arquivo. O usuário solta o PDF do lote numa janela e o programa separa uma página por arquivo e renomeia cada uma com o número da guia, lido por OCR local.

## Fluxo de trabalho

**Antes (manual)**
1. Fotografar as guias em lote
2. Gerar o PDF do lote
3. Abrir no PDF24, dividir e renomear guia por guia
4. Salvar os arquivos individuais
5. Anexar no portal INNOVA do faturamento, um por um

**Agora**
1. Fotografar as guias em lote (manual)
2. Gerar o PDF do lote (manual)
3. Soltar o PDF na janela do **Organizador de Guias** (substitui o PDF24 e a digitação dos nomes)
4. Conferir a pasta `revisar` e renomear à mão o que o OCR não leu com certeza
5. Anexar no INNOVA os arquivos da pasta `guias` (manual)

## Arquivos do projeto
| Arquivo | Função |
|---|---|
| `guias.py` | Lógica: leitura por OCR, separação e renomeação. Também roda pelo terminal (`python guias.py lote.pdf`). |
| `guias_app.py` | Interface gráfica (janela com arrastar e soltar, barra de progresso e botão para abrir o resultado). |
| `contexto.md` | Este documento. |

## Regras de renomeação
- Gera 3 versões do cabeçalho da página (Otsu, adaptativa e ampliada) para tolerar fotos de qualidade baixa.
- **Regra 1:** o título "GUIA DE CONSULTA" precisa estar visível (comparação aproximada). Sem título, vai para revisão.
- **Regra 2:** precisa haver um número de 7 dígitos, do campo 2 (topo) ou do campo 3 (abaixo). Cada versão da imagem "vota" no número lido.
- Confiança **alta** (lido 2 vezes ou mais) ou **média** (lido 1 vez, sem concorrente). Números diferentes empatados vão para revisão.
- Cada página gera exatamente um arquivo; nenhuma guia se perde. O PDF original não é alterado. Nunca sobrescreve arquivos.

## Pastas de saída
Para cada lote é criada, ao lado do PDF, a pasta `<nome do lote>_resultado` (se já existir, vira `_2`, `_3`...):

| Pasta / arquivo | Conteúdo | Ação |
|---|---|---|
| `guias\` | Número lido e confirmado. Nome = número da guia (ex.: `0000000.pdf`) | Anexar no INNOVA |
| `revisar\` | `pagina_XXX_motivo.pdf` ou `duplicada_XXX_NUMERO.pdf` | Conferir e renomear à mão |
| `relatorio.csv` | Página, arquivo, pasta, motivo e confiança (sem dados de paciente) | Conferir as de confiança média |

Motivos possíveis em `revisar`: `sem_titulo`, `sem_numero`, `numeros_conflitantes`, `duplicada`, `erro_leitura`.

## Ambiente de desenvolvimento
- Windows 11, VS Code, PowerShell, Python 3.13 com `.venv`
- Tesseract OCR em `C:\Program Files\Tesseract-OCR\tesseract.exe`
- Bibliotecas: `pymupdf`, `pytesseract`, `opencv-python`, `numpy`, `tkinterdnd2` (arrastar e soltar)
- Pasta de trabalho recomendada: `C:\guias` (fora do OneDrive)

## Como rodar
**Interface:**
```powershell
cd C:\guias
.\.venv\Scripts\Activate.ps1
python guias_app.py
```
**Terminal:** `python guias.py lote.pdf`

## Distribuição para quem não programa
Gerar um executável com PyInstaller, com o Tesseract embutido (a pessoa não instala nada):
```powershell
pip install pyinstaller tkinterdnd2
pyinstaller --noconsole --name OrganizadorDeGuias --collect-all tkinterdnd2 --add-data "C:\Program Files\Tesseract-OCR;Tesseract-OCR" guias_app.py
```
A pasta `dist\OrganizadorDeGuias` é copiada inteira para os outros computadores; o programa é o `OrganizadorDeGuias.exe` dentro dela.

## Segurança e LGPD
- Os PDFs contêm dados de saúde. Todo o processamento é local (Tesseract), sem enviar imagens para APIs de nuvem ou sites.
- Manter `.venv` e PDFs das guias fora do OneDrive.
- Log, relatório e mensagens de erro mostram só página, nome de arquivo e motivo, nunca dados de paciente.
- Não versionar (Git) nem compartilhar PDFs de guias.

## Status
- Lógica testada com um lote sintético (guias legíveis, uma com desfoque, uma duplicada, uma sem título e uma em branco): todas classificadas corretamente.
- A interface foi escrita e compilada, mas ainda não foi aberta e testada no Windows.
- Próximo passo: testar com um lote real de 5 a 10 guias e medir quantas vão para `revisar`.

## Ajustes possíveis (topo do `guias.py`)
- `LIMIAR_TITULO` (0.85): baixar se muitas páginas forem para `sem_titulo` com o título visível.
- `REGEX_GUIA` (`\d{7}`): trocar se as guias tiverem outro número de dígitos.
- `FRACAO_TOPO` (0.45): aumentar se título ou número ficarem fora do recorte.

## Ideia futura
Automatizar o anexo no portal INNOVA com Playwright. Depende de o portal ter upload em lote, API ou só interface por guia (ainda não verificado).