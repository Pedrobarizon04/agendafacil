"""Gera docs/Documentacao_AgendaFacil.pdf a partir de docs/documentacao.html.

Requisitos: Microsoft Edge (já vem no Windows) e PyMuPDF (pip install pymupdf).
Uso: python docs/gerar_pdf.py

1. Imprime o HTML em PDF com o Edge (modo headless).
2. Lê os links do sumário para descobrir em que página caiu cada seção.
3. Preenche os números no sumário e imprime de novo.
4. Numera as páginas no canto superior direito (a partir da introdução, contando capa e sumário).
"""
import re
import subprocess
import sys
from pathlib import Path

import pymupdf

PASTA = Path(__file__).resolve().parent
HTML = PASTA / "documentacao.html"
SAIDA = PASTA / "Documentacao_AgendaFacil.pdf"
EDGE = [
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
]
PRIMEIRA_NUMERADA = 2     # a introdução recebe o número 3 (capa e sumário contam, mas não mostram)


def imprimir(html: Path, pdf: Path):
    edge = next(p for p in EDGE if p.exists())
    subprocess.run(
        [str(edge), "--headless", "--disable-gpu", "--no-pdf-header-footer",
         f"--print-to-pdf={pdf}", html.as_uri()],
        check=True, capture_output=True,
    )


def paginas_do_sumario(pdf: Path, refs: list[str]) -> dict[str, int]:
    with pymupdf.open(pdf) as doc:
        destinos = doc.resolve_names()  # o Edge grava cada id do HTML como destino nomeado
    faltando = [r for r in refs if r not in destinos]
    if faltando:
        sys.exit(f"Seções sem destino no PDF: {faltando}")
    return {ref: destinos[ref]["page"] + 1 for ref in refs}


def numerar(pdf_entrada: Path, pdf_saida: Path):
    cm = 72 / 2.54
    with pymupdf.open(pdf_entrada) as doc:
        for i, pagina in enumerate(doc):
            if i < PRIMEIRA_NUMERADA:
                continue
            texto = str(i + 1)
            largura = pymupdf.get_text_length(texto, fontname="helv", fontsize=10)
            x = pagina.rect.width - 2 * cm - largura
            pagina.insert_text((x, 2 * cm), texto, fontname="helv", fontsize=10)
        doc.save(pdf_saida, garbage=3, deflate=True)


def main():
    fonte = HTML.read_text(encoding="utf-8")
    refs = re.findall(r'class="pg" data-ref="([^"]+)"', fonte)
    temp_html = PASTA / "_temp.html"
    temp_pdf = PASTA / "_temp.pdf"
    try:
        imprimir(HTML, temp_pdf)
        paginas = paginas_do_sumario(temp_pdf, refs)
        preenchido = re.sub(
            r'(class="pg" data-ref="([^"]+)">)\d+(<)',
            lambda m: f"{m.group(1)}{paginas[m.group(2)]}{m.group(3)}",
            fonte,
        )
        temp_html.write_text(preenchido, encoding="utf-8")
        imprimir(temp_html, temp_pdf)
        if paginas_do_sumario(temp_pdf, refs) != paginas:
            sys.exit("A paginação mudou entre as duas impressões; rode de novo.")
        numerar(temp_pdf, SAIDA)
    finally:
        temp_html.unlink(missing_ok=True)
        temp_pdf.unlink(missing_ok=True)
    print("PDF gerado:", SAIDA)
    for ref, pg in paginas.items():
        print(f"  {ref:5} -> página {pg}")


if __name__ == "__main__":
    main()
