from __future__ import annotations
import argparse, json
from pathlib import Path
from .compiler import SelmaDataCompiler
from .forge import SelmaForge
from .sandbox import VirtualSandbox

def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="selma-compile")
    p.add_argument("--output", type=Path, help="Output directory.")
    sub = p.add_subparsers(dest="command", required=True)
    for cmd in ("compile", "explain", "needs"):
        s = sub.add_parser(cmd)
        s.add_argument("roots", nargs="+", help="Selma project roots/files to scan.")
    f = sub.add_parser("forge")
    f.add_argument("workspace", help="Primary Selma workspace.")
    f.add_argument("roots", nargs="*", help="Optional additional Selma roots.")
    s = sub.add_parser("sandbox")
    s.add_argument("--cwd", type=Path)
    s.add_argument("--timeout", type=int, default=45)
    s.add_argument("command_args", nargs=argparse.REMAINDER)
    return p

def main() -> int:
    args = parser().parse_args()
    if args.command == "forge":
        roots = [args.workspace, *args.roots]
        result = SelmaForge(Path(args.workspace), args.output).run(roots)
        print(json.dumps({"snapshot": result["snapshot"], "delegated_tasks": len(result["tasks"])}, indent=2))
        return 0
    if args.command == "sandbox":
        if not args.command_args:
            raise SystemExit("sandbox requires a command after --")
        cmd = args.command_args[1:] if args.command_args and args.command_args[0] == "--" else args.command_args
        result = VirtualSandbox(args.timeout).run(cmd, cwd=args.cwd)
        print(json.dumps(result.to_dict(), indent=2))
        return result.returncode or 0
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
