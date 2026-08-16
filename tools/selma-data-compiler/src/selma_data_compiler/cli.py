from __future__ import annotations
import argparse, json
from pathlib import Path
from .compiler import SelmaDataCompiler

def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="selma-compile")
    p.add_argument("--output", type=Path, help="Compiler output directory.")
    sub = p.add_subparsers(dest="command", required=True)
    for cmd in ("compile", "explain", "needs"):
        s = sub.add_parser(cmd)
        s.add_argument("roots", nargs="+", help="Selma project roots/files to scan.")
    return p

def main() -> int:
    args = parser().parse_args()
    result = SelmaDataCompiler(args.output).compile(args.roots)
    if args.command == "compile":
        m = result["manifest"]
        print(json.dumps({"output_dir": result["output_dir"], "counts": m["counts"], "domains": m["domains"]}, indent=2))
    elif args.command == "explain":
        print(json.dumps({"roots": result["manifest"]["roots"], "domains": result["manifest"]["domains"], "dependency_map": result["dependency_map"], "conflicts": result["conflicts"]}, indent=2))
    else:
        print(json.dumps(result["needs"], indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
