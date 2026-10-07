# Organizador de Guias

Separa um PDF de guias de consulta em uma página por arquivo e renomeia cada uma com o número da guia (7 dígitos), lido por OCR local (Tesseract + OpenCV + PyMuPDF). Tem interface com arrastar e soltar.

Detalhes das regras de leitura e das pastas de saída: [contexto.md](contexto.md).

## Segurança e LGPD

- Os PDFs contêm dados de saúde. **Todo o processamento é local**: nenhuma imagem é enviada para serviços externos.
- O programa não registra dados de paciente em logs. Relatório e mensagens mostram só página, nome de arquivo e motivo.
- **Nunca versione nem compartilhe PDFs de guias.** O `.gitignore` bloqueia `*.pdf`, `*.csv` e as pastas `*_resultado/`.
- Não deixe PDFs e resultados em pastas sincronizadas (OneDrive). Prefira uma pasta local, como `C:\guias`.
- Para testes, use apenas PDFs sintéticos, sem dados reais.

## Requisitos

- Windows 10/11, 64 bits
- Python 3.13
- [Tesseract OCR para Windows](https://github.com/UB-Mannheim/tesseract/wiki), instalado em `C:\Program Files\Tesseract-OCR` (o idioma `eng` basta)

## Instalação (a partir do código)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python guias_app.py
```

Pelo terminal, sem interface: `python guias.py lote.pdf`

## Como usar

1. Solte o PDF do lote na janela (ou escolha o arquivo).
2. Ao lado do PDF é criada a pasta `<nome do lote>_resultado`:
   - `guias\`: arquivos nomeados com o número da guia.
   - `revisar\`: páginas que o OCR não leu com certeza; renomeie à mão.
   - `relatorio.csv`: página, arquivo, pasta, motivo e confiança.
3. O PDF original não é alterado e nenhum arquivo é sobrescrito.

## Gerar o executável (para quem não programa)

O executável **não** fica no repositório (a pasta tem cerca de 600 MB). Gere-o assim, com o Tesseract instalado e o venv ativo:

```powershell
pip install pyinstaller
pyinstaller --noconsole --noconfirm --name OrganizadorDeGuias --collect-all tkinterdnd2 --add-data "C:\Program Files\Tesseract-OCR;Tesseract-OCR" guias_app.py
```

Copie a pasta `dist\OrganizadorDeGuias` **inteira** para o outro computador e abra `OrganizadorDeGuias.exe`. Não é preciso instalar Python nem Tesseract lá.

- O Windows Defender/SmartScreen pode alertar no primeiro uso (falso positivo comum em executáveis do PyInstaller). Use "Mais informações" e "Executar assim mesmo".
- Se a janela não abrir, gere de novo trocando `--noconsole` por `--console` para ver o erro.

## Ajustes (topo do `guias.py`)

- `LIMIAR_TITULO` (0.85): reduza se muitas páginas forem para `sem_titulo` com o título visível.
- `REGEX_GUIA` (`\d{7}`): altere se as guias tiverem outro número de dígitos.
- `FRACAO_TOPO` (0.45): aumente se título ou número ficarem fora do recorte.
