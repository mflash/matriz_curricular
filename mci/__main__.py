#!/usr/bin/env python3
"""
mci — Gerador de Matriz Curricular Interativa (Python)

Uso:
  python mci.py <arquivo-entrada.json> [--links arrows|paths]
  python -m mci  <arquivo-entrada.json> [--links arrows|paths]

O arquivo de saída terá o mesmo nome do arquivo de entrada,
com extensão .html, no mesmo diretório.

Opções:
  --links arrows|paths   Define o estilo visual das ligações
                         arrows = setas clássicas (com ponta)
                         paths  = caminhos estilo Sankey (padrão)
  -h, --help             Exibe esta ajuda

Exemplo:
  python mci.py examples/98AJ.json --links arrows
  => gera examples/98AJ.html
"""

from __future__ import annotations

import os
import sys
from typing import Optional

from .layout import compute_layout
from .parser import ParseError, parse
from .router import compute_routes
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

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--links":
            i += 1
            if i >= len(args) or args[i] not in ("arrows", "paths"):
                print('Erro: --links deve ser "arrows" ou "paths".', file=sys.stderr)
                return 1
            link_style = args[i]
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

    layout = compute_layout(data)
    routes = compute_routes(data, layout)
    html = render_html(data, layout, routes, link_style)

    base, _ = os.path.splitext(input_arg)
    output_path = base + ".html"

    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(html)

    print(f"Gerado: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
