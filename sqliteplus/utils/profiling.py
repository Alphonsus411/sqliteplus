from __future__ import annotations

import cProfile
import os
import sys
import time
from pathlib import Path
from typing import Optional, Protocol

try:
    import cython  # type: ignore  # noqa: F401
except Exception:  # pragma: no cover - depende de compilación opcional
    cython = None  # type: ignore


class _Callable(Protocol):
    def __call__(self) -> object: ...


def _resolve_output_dir(env_var: str, default: Path) -> Path:
    custom = os.environ.get(env_var)
    return Path(custom).expanduser() if custom else default


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _profile_with_cprofile(name: str, callable_: _Callable, output_dir: Path) -> object:
    profiler = cProfile.Profile()
    start = time.perf_counter()
    profiler.enable()
    result = callable_()
    profiler.disable()
    duration = time.perf_counter() - start

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    output_dir = _ensure_dir(output_dir)
    stats_path = output_dir / f"{name}-{timestamp}.prof"
    text_path = output_dir / f"{name}-{timestamp}.txt"

    profiler.dump_stats(str(stats_path))

    try:
        import pstats

        with text_path.open("w", encoding="utf-8") as fp:
            ps = pstats.Stats(profiler, stream=fp)
            ps.sort_stats("cumtime").print_stats(50)
            fp.write(f"\nTiempo total: {duration:.4f}s\n")
    except Exception:
        text_path.write_text(
            "No se pudo renderizar el resumen de pstats; utiliza `.prof` con snakeviz o `python -m pstats`.",
            encoding="utf-8",
        )

    print(f"Perfil cProfile guardado en {stats_path}")
    return result


def _profile_with_pyinstrument(name: str, callable_: _Callable, output_dir: Path) -> object:
    try:
        from pyinstrument import Profiler
    except ModuleNotFoundError as exc:  # pragma: no cover - depende de extra opcional
        raise RuntimeError(
            "pyinstrument no está instalado; ejecuta `pip install pyinstrument` para habilitar el muestreo."
        ) from exc

    profiler = Profiler()
    profiler.start()
    result = callable_()
    profiler.stop()

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    output_dir = _ensure_dir(output_dir)
    html_path = output_dir / f"{name}-{timestamp}.html"
    text_path = output_dir / f"{name}-{timestamp}.txt"

    html_path.write_text(profiler.output_html(), encoding="utf-8")
    text_path.write_text(profiler.output_text(unicode=True, color=False), encoding="utf-8")
    print(f"Perfil pyinstrument guardado en {html_path}")
    return result


def run_with_optional_profiling(
    entrypoint: str,
    callable_: _Callable,
    *,
    mode_env: str = "SQLITEPLUS_PROFILE_ENTRYPOINT",
    output_env: str = "SQLITEPLUS_PROFILE_OUTPUT",
    default_output: Optional[Path] = None,
) -> object:
    mode = os.environ.get(mode_env, "").strip().lower()
    if not mode:
        return callable_()

    output_dir = default_output or Path(__file__).resolve().parents[2] / "reports" / "profile" / "entrypoints"
    output_dir = _resolve_output_dir(output_env, output_dir)

    if mode == "cprofile":
        return _profile_with_cprofile(entrypoint, callable_, output_dir)
    if mode in {"pyinstrument", "sampling"}:
        return _profile_with_pyinstrument(entrypoint, callable_, output_dir)

    raise RuntimeError(
        f"Modo de perfilado desconocido '{mode}'. Usa 'cprofile' o 'pyinstrument'."
    )


def install_api_profiler(app) -> None:
    mode = os.environ.get("SQLITEPLUS_PROFILE_API", "").strip().lower()
    if not mode:
        return

    output_dir = _resolve_output_dir(
        "SQLITEPLUS_PROFILE_API_OUTPUT",
        Path(__file__).resolve().parents[2] / "reports" / "profile" / "api",
    )
    _ensure_dir(output_dir)

    if mode in {"pyinstrument", "sampling"}:
        app.add_middleware(PyInstrumentMiddleware, output_dir=output_dir)
    elif mode == "cprofile":
        print("SQLITEPLUS_PROFILE_API=cprofile no está soportado; usa 'pyinstrument'.", file=sys.stderr)
    else:
        print(
            f"SQLITEPLUS_PROFILE_API='{mode}' no es válido. Opciones: pyinstrument/sampling.",
            file=sys.stderr,
        )


class PyInstrumentMiddleware:
    def __init__(self, app, *, output_dir: Path):
        self.app = app
        self.output_dir = Path(output_dir)

    async def __call__(self, scope, receive, send):
        if scope.get("type") not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return

        try:
            from pyinstrument import Profiler
        except ModuleNotFoundError:  # pragma: no cover - depende de extra opcional
            await self.app(scope, receive, send)
            return

        profiler = Profiler()
        profiler.start()
        try:
            await self.app(scope, receive, send)
        finally:
            profiler.stop()
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            html_path = self.output_dir / f"api-{timestamp}.html"
            txt_path = self.output_dir / f"api-{timestamp}.txt"
            html_path.write_text(profiler.output_html(), encoding="utf-8")
            txt_path.write_text(profiler.output_text(unicode=True, color=False), encoding="utf-8")
            print(f"Perfil API pyinstrument guardado en {html_path}")
