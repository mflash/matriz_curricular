#!/usr/bin/env python3
"""
mci — Gerador de Matriz Curricular Interativa (Python)

Uso:
    python mci.py <arquivo-entrada.json> [--links arrows|paths] [--row-gap N] [--vertical-clearance N]
    python -m mci  <arquivo-entrada.json> [--links arrows|paths] [--row-gap N] [--vertical-clearance N]

O arquivo de saída terá o mesmo nome do arquivo de entrada,
com extensão .html, no mesmo diretório.

Opções:
  --links arrows|paths   Define o estilo visual das ligações
                         arrows = setas clássicas (com ponta)
                         paths  = caminhos estilo Sankey (padrão)
    --row-gap N            Define o espaçamento vertical entre disciplinas (padrão: 24)
    --vertical-clearance N Define a separação mínima entre segmentos verticais de setas (padrão: 6)
  -h, --help             Exibe esta ajuda

Exemplo:
  python mci.py examples/98AJ.json --links arrows
  => gera examples/98AJ.html
"""

from __future__ import annotations

import os
import sys
from typing import Optional

from .layout import ROW_GAP, compute_layout
from .parser import ParseError, parse
from .router import MIN_VERTICAL_CLEARANCE, compute_routes
from .template import render_html


def _print_usage() -> None:
    print(__doc__.strip())


def main() -> int:
    args = sys.argv[1:]

    if not args or "-h" in args or "--help" in args:
        _print_usage()
        return 0

    input_arg: Optional[str] = None
    link_style = "paths"
    row_gap = ROW_GAP
    vertical_clearance = MIN_VERTICAL_CLEARANCE

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--links":
            i += 1
            if i >= len(args) or args[i] not in ("arrows", "paths"):
                print('Erro: --links deve ser "arrows" ou "paths".', file=sys.stderr)
                return 1
            link_style = args[i]
        elif arg == "--row-gap":
            i += 1
            if i >= len(args):
                print("Erro: --row-gap requer um valor inteiro.", file=sys.stderr)
                return 1
            try:
                row_gap = int(args[i])
            except ValueError:
                print("Erro: --row-gap deve ser um inteiro.", file=sys.stderr)
                return 1
            if row_gap < 0:
                print(
                    "Erro: --row-gap deve ser maior ou igual a zero.", file=sys.stderr
                )
                return 1
        elif arg == "--vertical-clearance":
            i += 1
            if i >= len(args):
                print(
                    "Erro: --vertical-clearance requer um valor numérico.",
                    file=sys.stderr,
                )
                return 1
            try:
                vertical_clearance = float(args[i])
            except ValueError:
                print("Erro: --vertical-clearance deve ser numérico.", file=sys.stderr)
                return 1
            if vertical_clearance < 0:
                print(
                    "Erro: --vertical-clearance deve ser maior ou igual a zero.",
                    file=sys.stderr,
                )
                return 1
        elif arg.startswith("-"):
            print(f'Erro: opção desconhecida "{arg}".', file=sys.stderr)
            return 1
        else:
            if input_arg is not None:
                print("Erro: mais de um arquivo de entrada fornecido.", file=sys.stderr)
                return 1
            input_arg = arg
        i += 1

    if not input_arg:
        print("Erro: arquivo de entrada não especificado.", file=sys.stderr)
        _print_usage()
        return 1

    if not os.path.isfile(input_arg):
        print(f"Erro: arquivo não encontrado: {input_arg}", file=sys.stderr)
        return 1

    with open(input_arg, "r", encoding="utf-8") as fh:
        raw = fh.read()

    try:
        data = parse(raw)
    except ParseError as e:
        print(f"Erro de validação: {e}", file=sys.stderr)
        return 1

    layout = compute_layout(data, row_gap=row_gap)
    routes = compute_routes(
        data,
        layout,
        row_gap=row_gap,
        vertical_clearance=vertical_clearance,
    )
    html = render_html(data, layout, routes, link_style, row_gap=row_gap)

    base, _ = os.path.splitext(input_arg)
    output_path = base + ".html"

    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(html)

    print(f"Gerado: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
