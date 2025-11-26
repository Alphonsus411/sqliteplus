"""Generador de módulos .pyx y lista dinámica de candidatos Cython.

A partir de un reporte JSON de hotspots (p. ej. ``reports/hotspots.json``)
obtiene los módulos Python con más peso de CPU/E/S pura, genera un archivo
``reports/cython_candidates.json`` y crea gemelos ``.pyx`` que mantienen la
API importando el código original como *fallback*.
"""
from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = REPO_ROOT / "reports" / "hotspots.json"
DEFAULT_OUTPUT = REPO_ROOT / "reports" / "cython_candidates.json"


@dataclass
class CandidateModule:
    module: str
    path: Path
    functions: list[ast.FunctionDef | ast.AsyncFunctionDef]
    classes: list[ast.ClassDef]


# --------------------------- Lectura del perfil ---------------------------

def load_profile(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el perfil en {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def extract_candidate_modules(profile: dict, *, limit: int | None) -> list[str]:
    entries: list[dict] = profile.get("overall_hotspots", [])
    modules: list[str] = []
    for entry in entries:
        if not entry.get("is_python") or entry.get("is_io"):
            continue
        file_path = entry.get("file")
        if not file_path or not str(file_path).endswith(".py"):
            continue
        normalized = str(file_path).replace("\\", "/")
        module_path = Path(normalized)
        if "site-packages" in normalized or module_path.parts[0] != "sqliteplus":
            continue
        module_name = ".".join(module_path.with_suffix("").parts)
        if module_name not in modules:
            modules.append(module_name)
        if limit and len(modules) >= limit:
            break
    return modules


# --------------------------- Generación de .pyx ---------------------------

def _format_default(value: ast.AST | None) -> str:
    return "=" + ast.unparse(value) if value is not None else ""


def _format_arg(arg: ast.arg, default: ast.AST | None, *, kwonly: bool) -> str:
    annotation = f": {ast.unparse(arg.annotation)}" if arg.annotation else ""
    suffix = _format_default(default)
    if kwonly and default is None:
        suffix = "=" + ("..." if annotation else "None")
    return f"{arg.arg}{annotation}{suffix}"


def _format_signature(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, list[str]]:
    args = fn.args
    parts: list[str] = []
    call_args: list[str] = []

    positional = list(args.posonlyargs) + list(args.args)
    pos_defaults = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
    for arg, default in zip(positional, pos_defaults, strict=False):
        parts.append(_format_arg(arg, default, kwonly=False))
        call_args.append(arg.arg)

    if args.vararg:
        parts.append("*" + args.vararg.arg)
        call_args.append("*" + args.vararg.arg)
    elif args.kwonlyargs:
        parts.append("*")

    kw_defaults = [None if value is None else value for value in args.kw_defaults]
    for arg, default in zip(args.kwonlyargs, kw_defaults, strict=False):
        parts.append(_format_arg(arg, default, kwonly=True))
        call_args.append(f"{arg.arg}={arg.arg}")

    if args.kwarg:
        parts.append("**" + args.kwarg.arg)
        call_args.append("**" + args.kwarg.arg)

    return ", ".join(parts), call_args


def parse_module(module_name: str) -> CandidateModule:
    module_path = (REPO_ROOT / Path(module_name.replace(".", "/"))).with_suffix(".py")
    if not module_path.exists():
        raise FileNotFoundError(f"No se encontró {module_path}")

    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    functions: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    classes: list[ast.ClassDef] = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                functions.append(node)
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            classes.append(node)

    return CandidateModule(module=module_name, path=module_path, functions=functions, classes=classes)


def render_pyx(candidate: CandidateModule) -> str:
    lines = ["# cython: language_level=3", "from __future__ import annotations", "", "import importlib.util", "import sys"]
    lines.append("from pathlib import Path")
    lines.append("")
    lines.append("def _load_py_fallback():")
    lines.append("    module_name = __name__ + '_pyfallback'")
    lines.append("    py_path = Path(__file__).with_suffix('.py')")
    lines.append("    spec = importlib.util.spec_from_file_location(module_name, py_path)")
    lines.append("    if spec is None or spec.loader is None:")
    lines.append("        raise ImportError(f'No se pudo cargar {py_path} como fallback')")
    lines.append("    module = importlib.util.module_from_spec(spec)")
    lines.append("    sys.modules[module_name] = module")
    lines.append("    spec.loader.exec_module(module)")
    lines.append("    return module")
    lines.append("")
    lines.append("_PY_FALLBACK = _load_py_fallback()")
    lines.append("")

    exports: list[str] = []
    for fn in candidate.functions:
        signature, call_args = _format_signature(fn)
        exports.append(fn.name)
        prefix = "async " if isinstance(fn, ast.AsyncFunctionDef) else ""
        lines.append(f"{prefix}def {fn.name}({signature}):")
        call_expr = ", ".join(call_args)
        if isinstance(fn, ast.AsyncFunctionDef):
            lines.append(f"    return await _PY_FALLBACK.{fn.name}({call_expr})")
        else:
            lines.append(f"    return _PY_FALLBACK.{fn.name}({call_expr})")
        lines.append("")

    for cls in candidate.classes:
        exports.append(cls.name)
        lines.append(f"{cls.name} = _PY_FALLBACK.{cls.name}")

    if exports:
        quoted = ", ".join(f"'{name}'" for name in exports)
        lines.append("")
        lines.append(f"__all__ = [{quoted}]")

    return "\n".join(lines) + "\n"


def write_pyx(candidate: CandidateModule, *, overwrite: bool) -> Path:
    pyx_path = candidate.path.with_suffix(".pyx")
    if pyx_path.exists() and not overwrite:
        return pyx_path
    pyx_path.write_text(render_pyx(candidate), encoding="utf-8")
    return pyx_path


# --------------------------- CLI principal ---------------------------

def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Genera gemelos .pyx desde hotspots JSON")
    parser.add_argument("profile", nargs="?", default=str(DEFAULT_PROFILE), help="Ruta al reporte JSON de hotspots")
    parser.add_argument("--limit", type=int, help="Número máximo de módulos a generar")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Archivo JSON con la lista de candidatos")
    parser.add_argument("--overwrite", action="store_true", help="Sobrescribir .pyx existentes")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    profile_path = Path(args.profile)
    output_path = Path(args.output)

    profile = load_profile(profile_path)
    modules = extract_candidate_modules(profile, limit=args.limit)

    candidates = [parse_module(module_name) for module_name in modules]
    written: list[str] = []
    for candidate in candidates:
        pyx_path = write_pyx(candidate, overwrite=args.overwrite)
        written.append(str(pyx_path.relative_to(REPO_ROOT)))

    payload = {
        "generated_from": str(profile_path),
        "modules": modules,
        "pyx_files": written,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"Candidatos guardados en {output_path} ({len(modules)} módulos)")
    return 0


if __name__ == "__main__":  # pragma: no cover - utilidad de línea de comandos
    raise SystemExit(main())
