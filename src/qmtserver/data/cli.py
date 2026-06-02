from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from typing import Any

from qmtserver.config import load_settings


def configure_data_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
    add_profile_args: Callable[[argparse.ArgumentParser], None],
) -> None:
    data = subparsers.add_parser("data", help="maintain local market data lake files")
    data_subparsers = data.add_subparsers(dest="data_action")
    data_check = data_subparsers.add_parser("check", help="check local data lake file index")
    add_profile_args(data_check)
    data_check.add_argument("--json", action="store_true", help="print machine-readable JSON")
    data_cleanup = data_subparsers.add_parser("cleanup", help="clean orphan local data lake files")
    add_profile_args(data_cleanup)
    data_cleanup.add_argument("--delete", action="store_true", help="delete orphan files")
    data_cleanup.add_argument(
        "--expired-days",
        type=int,
        help="include exports generated at least this many days ago",
    )
    data_cleanup.add_argument("--json", action="store_true", help="print machine-readable JSON")
    data_rebuild = data_subparsers.add_parser(
        "rebuild-index",
        help="rebuild the DuckDB file index from local Parquet files",
    )
    add_profile_args(data_rebuild)
    data_rebuild.add_argument("--execute", action="store_true", help="execute the rebuild")
    data_rebuild.add_argument("--json", action="store_true", help="print machine-readable JSON")
    data_compact = data_subparsers.add_parser(
        "compact",
        help="compact small local Parquet files by symbol/period/adjust",
    )
    add_profile_args(data_compact)
    data_compact.add_argument("--execute", action="store_true", help="execute compaction")
    data_compact.add_argument(
        "--min-files",
        type=int,
        default=2,
        help="minimum files per group before compaction",
    )
    data_compact.add_argument("--json", action="store_true", help="print machine-readable JSON")


def run_data(
    args: argparse.Namespace,
    *,
    service_builder: Callable[[argparse.Namespace], Any] | None = None,
) -> int:
    if args.data_action not in {"check", "cleanup", "rebuild-index", "compact"}:
        return 2
    service = (service_builder or build_data_maintenance_service)(args)
    if args.data_action == "check":
        report = service.check()
    elif args.data_action == "cleanup":
        report = service.cleanup(delete=args.delete, expired_days=args.expired_days)
    elif args.data_action == "compact":
        report = service.compact(execute=args.execute, min_files=args.min_files)
    else:
        report = service.rebuild_index(execute=args.execute)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_data_maintenance(report)
    return 0


def build_data_maintenance_service(args: argparse.Namespace) -> Any:
    from qmtserver.data.backend import create_data_backend
    from qmtserver.data.maintenance import DataMaintenanceService
    from qmtserver.data.repository import DataJobRepository

    settings = load_settings(profile=args.profile)
    backend = create_data_backend(settings)
    backend.initialize()
    return DataMaintenanceService(backend.data_dir, repository=DataJobRepository(backend))


def _print_data_maintenance(report: dict[str, Any]) -> None:
    print("qmtserver market data lake maintenance")
    if report["schema"] == "market.data.cleanup.v1":
        print(f"- dry run: {report['dry_run']}")
        print(f"- delete candidates: {len(report['delete_candidates'])}")
        print(f"- expired export files: {len(report['expired_export_files'])}")
        print(f"- deleted files: {len(report['deleted_files'])}")
        return
    if report["schema"] == "market.data.rebuild_index.v1":
        print(f"- dry run: {report['dry_run']}")
        print(f"- parquet files: {report['parquet_file_count']}")
        print(f"- metadata errors: {report['metadata_error_count']}")
        print(f"- rebuilt files: {report['rebuilt_file_count']}")
        return
    if report["schema"] == "market.data.compaction.v1":
        print(f"- dry run: {report['dry_run']}")
        print(f"- groups: {report['group_count']}")
        print(f"- compacted files: {report['compacted_file_count']}")
        print(f"- deleted source files: {report['deleted_source_count']}")
        return
    health = report["health"]
    print(f"- health: {health['status']}")
    print(f"- registered files: {report['registered_file_count']}")
    print(f"- missing registered files: {len(report['missing_registered_files'])}")
    print(f"- orphan parquet files: {len(report['orphan_parquet_files'])}")
    print(f"- orphan export files: {len(report['orphan_export_files'])}")
    print(f"- metadata mismatches: {len(report['metadata_mismatches'])}")
    print(f"- data dir bytes: {health['data_dir_bytes']}")
