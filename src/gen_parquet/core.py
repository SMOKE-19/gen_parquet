"""TSV text to YAML schema and Parquet conversion helpers."""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from gen_parquet.expressions import load_expression_yaml, normalize_expression_for_duckdb

SUPPORTED_TYPES = ("boolean", "integer", "float", "date", "datetime", "string")
NULL_VALUES = {"", "null", "none", "na", "n/a", "nan"}


def package_name() -> str:
    """Return the import package name."""
    return "gen_parquet"


def write_type_yaml(
    txt_path: str | Path,
    yaml_path: str | Path | None = None,
    *,
    sample_rows: int | None = None,
    comment_values: int = 10,
    encoding: str = "utf-8",
) -> Path:
    """Suggest column types for a TSV ``.txt`` file and write a type-list YAML file.

    By default, every row is scanned. Set ``sample_rows`` to a positive integer to limit
    type inference for very large files.
    """
    source = Path(txt_path)
    target = Path(yaml_path) if yaml_path is not None else source.with_suffix(".yaml")

    header, samples = _collect_samples(source, sample_rows=sample_rows, encoding=encoding)
    suggested = {type_name: [] for type_name in SUPPORTED_TYPES}
    for column in header:
        suggested[_suggest_type(samples[column])].append(column)

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        _render_type_yaml(suggested, samples, comment_values=comment_values),
        encoding=encoding,
    )
    return target


def txt_to_parquet(
    txt_path: str | Path,
    type_yaml_path: str | Path,
    output_path: str | Path,
    *,
    encoding: str = "utf-8",
) -> Path:
    """Convert a TSV ``.txt`` file to Parquet using a type-list YAML file."""
    source = Path(txt_path)
    schema_path = Path(type_yaml_path)
    target = Path(output_path)

    header = _read_header(source, encoding=encoding)
    column_types, exclude_cols = _load_type_yaml(schema_path)
    output_header = [column for column in header if column not in exclude_cols]
    missing = [column for column in output_header if column not in column_types]
    extra = [
        column for column in set(column_types) | exclude_cols if column not in header
    ]
    if missing:
        raise ValueError(f"Columns missing from YAML: {missing}")
    if extra:
        raise ValueError(f"Columns in YAML but not txt header: {extra}")

    values: dict[str, list[Any]] = {column: [] for column in output_header}
    with source.open("r", encoding=encoding, newline="") as file_obj:
        reader = csv.reader(file_obj, delimiter="\t")
        next(reader)
        for line_number, row in enumerate(reader, start=2):
            if len(row) != len(header):
                raise ValueError(
                    f"Line {line_number} has {len(row)} fields, expected {len(header)}"
                )
            for column, raw_value in zip(header, row, strict=True):
                if column in exclude_cols:
                    continue
                values[column].append(_cast_value(raw_value, column_types[column], column, line_number))

    arrays = [
        pa.array(values[column], type=_arrow_type(column_types[column]))
        for column in output_header
    ]
    table = pa.Table.from_arrays(arrays, names=output_header)
    target.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, target)
    return target


def write_type_yamls_for_txt_dir(
    txt_dir: str | Path,
    *,
    pattern: str = "*.txt",
    sample_rows: int | None = None,
    comment_values: int = 10,
    encoding: str = "utf-8",
) -> list[Path]:
    """Write one YAML file next to each matching TSV text file in a directory."""
    directory = Path(txt_dir)
    return [
        write_type_yaml(
            txt_path,
            sample_rows=sample_rows,
            comment_values=comment_values,
            encoding=encoding,
        )
        for txt_path in sorted(directory.glob(pattern))
    ]


def add_calculated_columns(
    logic_yaml_path: str | Path,
    parquet_path: str | Path,
    output_path: str | Path | None = None,
) -> Path:
    """Add calculated columns from expression YAML to a Parquet file."""
    import duckdb

    source = Path(parquet_path)
    logic_path = Path(logic_yaml_path)
    target = Path(output_path) if output_path is not None else source.with_suffix(".calculated.parquet")

    expressions = load_expression_yaml(logic_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    connection = duckdb.connect(database=":memory:")
    try:
        connection.execute("CREATE TABLE working AS SELECT * FROM read_parquet(?)", [str(source)])
        for column_name, expression in expressions:
            normalized = normalize_expression_for_duckdb(expression)
            existing_columns = set(_duckdb_table_columns(connection))
            select_prefix = (
                f"SELECT * EXCLUDE ({_sql_identifier(column_name)})"
                if column_name in existing_columns
                else "SELECT *"
            )
            connection.execute(
                "CREATE OR REPLACE TABLE working AS "
                f"{select_prefix}, ({normalized}) AS {_sql_identifier(column_name)} "
                "FROM working"
            )
        connection.execute("COPY working TO ? (FORMAT PARQUET)", [str(target)])
    finally:
        connection.close()

    return target


def _read_header(txt_path: Path, *, encoding: str) -> list[str]:
    with txt_path.open("r", encoding=encoding, newline="") as file_obj:
        reader = csv.reader(file_obj, delimiter="\t")
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ValueError(f"TXT file is empty: {txt_path}") from exc

    if any(column == "" for column in header):
        raise ValueError(f"TXT header contains an empty column name: {txt_path}")

    duplicates = sorted(column for column, count in Counter(header).items() if count > 1)
    if duplicates:
        raise ValueError(f"TXT header contains duplicate columns: {duplicates}")
    return header


def _duckdb_table_columns(connection: Any) -> list[str]:
    rows = connection.execute("DESCRIBE working").fetchall()
    return [str(row[0]) for row in rows]


def _sql_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _collect_samples(
    txt_path: Path,
    *,
    sample_rows: int | None,
    encoding: str,
) -> tuple[list[str], dict[str, list[str]]]:
    header = _read_header(txt_path, encoding=encoding)
    samples: dict[str, list[str]] = {column: [] for column in header}

    with txt_path.open("r", encoding=encoding, newline="") as file_obj:
        reader = csv.reader(file_obj, delimiter="\t")
        next(reader)
        for line_number, row in enumerate(reader, start=2):
            if len(row) != len(header):
                raise ValueError(
                    f"Line {line_number} has {len(row)} fields, expected {len(header)}"
                )
            for column, value in zip(header, row, strict=True):
                if not _is_null(value) and (
                    sample_rows is None or len(samples[column]) < sample_rows
                ):
                    samples[column].append(value)
            if sample_rows is not None and all(
                len(column_samples) >= sample_rows for column_samples in samples.values()
            ):
                break

    return header, samples


def _suggest_type(values: Iterable[str]) -> str:
    non_null = [value for value in values if not _is_null(value)]
    if not non_null:
        return "string"
    if all(_parse_boolean(value) is not None for value in non_null):
        return "boolean"
    if all(_parse_integer(value) is not None for value in non_null):
        return "integer"
    if all(_parse_float(value) is not None for value in non_null):
        return "float"
    if all(_parse_date(value) is not None for value in non_null):
        return "date"
    if all(_parse_datetime(value) is not None for value in non_null):
        return "datetime"
    return "string"


def _render_type_yaml(
    suggested: dict[str, list[str]],
    samples: dict[str, list[str]],
    *,
    comment_values: int,
) -> str:
    lines = [
        "# Column type suggestions for a tab-separated .txt file.",
        "# Move column names between type lists before converting to Parquet.",
        "# Uncomment exclude_cols entries to omit columns even if they also appear under types.",
        "# exclude_cols:",
        "#   - \"column_to_skip\"",
        "types:",
    ]
    for type_name in SUPPORTED_TYPES:
        columns = suggested[type_name]
        if not columns:
            lines.append(f"  {type_name}: []")
            continue
        lines.append(f"  {type_name}:")
        for column in columns:
            preview = ", ".join(_yaml_comment_value(value) for value in samples[column][:comment_values])
            lines.append(f"    # samples: {preview}" if preview else "    # samples: <no non-empty values>")
            lines.append(f"    - {_yaml_scalar(column)}")
    lines.append("")
    return "\n".join(lines)


def _load_type_yaml(type_yaml_path: Path) -> tuple[dict[str, str], set[str]]:
    data = yaml.safe_load(type_yaml_path.read_text(encoding="utf-8")) or {}
    exclude_cols = _load_exclude_cols(data)
    types = data.get("types")
    if not isinstance(types, dict):
        raise ValueError("YAML must contain a top-level 'types' mapping")

    column_types: dict[str, str] = {}
    for type_name, columns in types.items():
        if type_name not in SUPPORTED_TYPES:
            raise ValueError(f"Unsupported type in YAML: {type_name}")
        if columns is None:
            continue
        if not isinstance(columns, list):
            raise ValueError(f"YAML type '{type_name}' must be a list")
        for column in columns:
            if not isinstance(column, str):
                raise ValueError(f"YAML column names must be strings: {column!r}")
            if column in exclude_cols:
                continue
            if column in column_types:
                raise ValueError(f"Column appears in multiple YAML type lists: {column}")
            column_types[column] = type_name
    return column_types, exclude_cols


def _load_exclude_cols(data: dict[str, Any]) -> set[str]:
    raw_exclude_cols = data.get("exclude_cols", [])
    if raw_exclude_cols is None:
        return set()
    if not isinstance(raw_exclude_cols, list):
        raise ValueError("YAML 'exclude_cols' must be a list")
    exclude_cols: set[str] = set()
    for column in raw_exclude_cols:
        if not isinstance(column, str):
            raise ValueError(f"YAML exclude_cols entries must be strings: {column!r}")
        exclude_cols.add(column)
    return exclude_cols


def _cast_value(value: str, type_name: str, column: str, line_number: int) -> Any:
    if _is_null(value):
        return None
    parsers = {
        "boolean": _parse_boolean,
        "integer": _cast_integer,
        "float": _cast_float,
        "date": _parse_date,
        "datetime": _parse_datetime,
        "string": str,
    }
    parsed = parsers[type_name](value)
    if parsed is None:
        return None
    return parsed


def _arrow_type(type_name: str) -> pa.DataType:
    return {
        "boolean": pa.bool_(),
        "integer": pa.int64(),
        "float": pa.float64(),
        "date": pa.date32(),
        "datetime": pa.timestamp("us"),
        "string": pa.string(),
    }[type_name]


def _is_null(value: str) -> bool:
    return value.strip().lower() in NULL_VALUES


def _parse_boolean(value: str) -> bool | None:
    lowered = value.strip().lower()
    if lowered in {"true", "t", "yes", "y", "1"}:
        return True
    if lowered in {"false", "f", "no", "n", "0"}:
        return False
    return None


def _parse_integer(value: str) -> int | None:
    try:
        if value.strip() != str(int(value.strip())):
            return None
        return int(value.strip())
    except ValueError:
        return None


def _parse_float(value: str) -> float | None:
    stripped = value.strip()
    if "." not in stripped and "e" not in stripped.lower():
        return None
    try:
        return float(stripped)
    except ValueError:
        return None


def _cast_integer(value: str) -> int | None:
    stripped = value.strip()
    if "." in stripped or "e" in stripped.lower():
        return None
    try:
        return int(stripped)
    except ValueError:
        return None


def _cast_float(value: str) -> float | None:
    try:
        return float(value.strip())
    except ValueError:
        return None


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        return None


def _parse_datetime(value: str) -> datetime | None:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed


def _yaml_scalar(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _yaml_comment_value(value: str) -> str:
    return value.replace("\n", "\\n").replace("\r", "\\r")
