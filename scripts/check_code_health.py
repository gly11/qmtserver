from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATHS = ("src/qmtserver", "tests")
FILE_WARN_LINES = 300
FILE_REVIEW_LINES = 400
FILE_FAIL_LINES = 500
FUNCTION_WARN_LINES = 50
FUNCTION_REVIEW_LINES = 80


@dataclass(frozen=True)
class FileStat:
    path: Path
    lines: int


@dataclass(frozen=True)
class FunctionStat:
    path: Path
    name: str
    lines: int
    line: int


def main() -> int:
    args = _parse_args()
    files = _collect_files(args.paths)
    file_stats = [_file_stat(path) for path in files]
    function_stats = [
        function for path in files for function in _function_stats(path, _read_text(path))
    ]

    _print_file_report(file_stats)
    _print_function_report(function_stats)

    if args.enforce and _has_enforced_violation(file_stats, function_stats):
        return 1
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report qmtserver code health metrics.")
    parser.add_argument(
        "paths",
        nargs="*",
        default=list(DEFAULT_PATHS),
        help="paths to scan, defaults to src/qmtserver and tests",
    )
    parser.add_argument(
        "--enforce",
        action="store_true",
        help="exit non-zero for hard violations",
    )
    return parser.parse_args()


def _collect_files(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for value in paths:
        path = (ROOT / value).resolve()
        if path.is_file() and path.suffix == ".py":
            files.append(path)
        elif path.is_dir():
            files.extend(sorted(path.rglob("*.py")))
    return sorted(
        {file for file in files if "__pycache__" not in file.parts and ".venv" not in file.parts}
    )


def _file_stat(path: Path) -> FileStat:
    return FileStat(path=path, lines=len(_read_text(path).splitlines()))


def _function_stats(path: Path, source: str) -> list[FunctionStat]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    result: list[FunctionStat] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            end_lineno = node.end_lineno or node.lineno
            result.append(
                FunctionStat(
                    path=path,
                    name=node.name,
                    line=node.lineno,
                    lines=end_lineno - node.lineno + 1,
                )
            )
    return sorted(result, key=lambda item: item.lines, reverse=True)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _print_file_report(stats: list[FileStat]) -> None:
    print("Code health: largest Python files")
    for stat in sorted(stats, key=lambda item: item.lines, reverse=True)[:20]:
        print(f"{stat.lines:4}  {_relative(stat.path)}  {_file_status(stat.lines)}")


def _print_function_report(stats: list[FunctionStat]) -> None:
    print()
    print("Code health: longest functions")
    for stat in sorted(stats, key=lambda item: item.lines, reverse=True)[:20]:
        print(
            f"{stat.lines:4}  {_relative(stat.path)}:{stat.line}  "
            f"{stat.name}  {_function_status(stat.lines)}"
        )


def _file_status(lines: int) -> str:
    if lines > FILE_FAIL_LINES:
        return "FAIL split required"
    if lines > FILE_REVIEW_LINES:
        return "REVIEW split strongly recommended"
    if lines > FILE_WARN_LINES:
        return "WARN watch growth"
    return "OK"


def _function_status(lines: int) -> str:
    if lines > FUNCTION_REVIEW_LINES:
        return "REVIEW split strongly recommended"
    if lines > FUNCTION_WARN_LINES:
        return "WARN consider helper"
    return "OK"


def _has_enforced_violation(
    file_stats: list[FileStat],
    function_stats: list[FunctionStat],
) -> bool:
    return any(stat.lines > FILE_FAIL_LINES for stat in file_stats) or any(
        stat.lines > FUNCTION_REVIEW_LINES for stat in function_stats
    )


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
