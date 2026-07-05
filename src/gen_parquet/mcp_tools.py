"""Tool functions exposed by the gen-parquet MCP adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import yaml

from gen_parquet import add_calculated_columns, txt_to_parquet, write_type_yaml, write_type_yamls_for_txt_dir
from gen_parquet.expressions import load_expression_yaml


def generate_type_yaml_tool(
    *,
    txt_path: str,
    yaml_path: str | None = None,
    sample_rows: int | None = None,
    comment_values: int = 10,
) -> dict[str, Any]:
    """Generate one type suggestion YAML file for a TSV text file."""
    try:
        output_path = write_type_yaml(
            txt_path,
            yaml_path,
            sample_rows=sample_rows,
            comment_values=comment_values,
        )
        return {
            "ok": True,
            "txt_path": str(Path(txt_path)),
            "yaml_path": str(output_path),
            "summary": summarize_type_yaml(yaml_path=str(output_path)),
        }
    except Exception as exc:
        return _error_response(exc, txt_path=txt_path, yaml_path=yaml_path)


def generate_type_yamls_for_dir_tool(
    *,
    txt_dir: str,
    pattern: str = "*.txt",
    sample_rows: int | None = None,
    comment_values: int = 10,
) -> dict[str, Any]:
    """Generate type suggestion YAML files for matching TSV text files in a directory."""
    try:
        yaml_paths = write_type_yamls_for_txt_dir(
            txt_dir,
            pattern=pattern,
            sample_rows=sample_rows,
            comment_values=comment_values,
        )
        return {
            "ok": True,
            "txt_dir": str(Path(txt_dir)),
            "pattern": pattern,
            "count": len(yaml_paths),
            "yaml_paths": [str(path) for path in yaml_paths],
        }
    except Exception as exc:
        return _error_response(exc, txt_dir=txt_dir, pattern=pattern)


def convert_txt_to_parquet_tool(
    *,
    txt_path: str,
    type_yaml_path: str,
    output_path: str,
) -> dict[str, Any]:
    """Convert a TSV text file to Parquet using a type YAML file."""
    try:
        parquet_path = txt_to_parquet(txt_path, type_yaml_path, output_path)
        return {
            "ok": True,
            "txt_path": str(Path(txt_path)),
            "type_yaml_path": str(Path(type_yaml_path)),
            "parquet_path": str(parquet_path),
            "parquet": inspect_parquet(parquet_path=str(parquet_path)),
        }
    except Exception as exc:
        return _error_response(exc, txt_path=txt_path, type_yaml_path=type_yaml_path, output_path=output_path)


def add_calculated_columns_tool(
    *,
    logic_yaml_path: str,
    parquet_path: str,
    output_path: str,
) -> dict[str, Any]:
    """Add calculated columns to a Parquet file using expression YAML."""
    try:
        result_path = add_calculated_columns(logic_yaml_path, parquet_path, output_path)
        return {
            "ok": True,
            "logic_yaml_path": str(Path(logic_yaml_path)),
            "input_parquet_path": str(Path(parquet_path)),
            "output_parquet_path": str(result_path),
            "expressions": summarize_expression_yaml(logic_yaml_path=logic_yaml_path),
            "parquet": inspect_parquet(parquet_path=str(result_path)),
        }
    except Exception as exc:
        return _error_response(
            exc,
            logic_yaml_path=logic_yaml_path,
            parquet_path=parquet_path,
            output_path=output_path,
        )


def inspect_parquet(*, parquet_path: str, max_columns: int = 80) -> dict[str, Any]:
    """Return a compact Parquet schema summary."""
    try:
        metadata = pq.read_metadata(parquet_path)
        schema = metadata.schema.to_arrow_schema()
        fields = [
            {"name": field.name, "type": str(field.type), "nullable": field.nullable}
            for field in schema
        ]
        return {
            "ok": True,
            "parquet_path": str(Path(parquet_path)),
            "rows": metadata.num_rows,
            "columns": len(schema),
            "row_groups": metadata.num_row_groups,
            "schema": fields[:max_columns],
            "schema_truncated": len(fields) > max_columns,
        }
    except Exception as exc:
        return _error_response(exc, parquet_path=parquet_path)


def summarize_type_yaml(*, yaml_path: str) -> dict[str, Any]:
    """Summarize a generated type YAML file."""
    try:
        payload = yaml.safe_load(Path(yaml_path).read_text(encoding="utf-8")) or {}
        types = payload.get("types") or {}
        exclude_cols = payload.get("exclude_cols") or []
        type_counts = {
            str(type_name): len(columns or [])
            for type_name, columns in types.items()
            if isinstance(columns, list) or columns is None
        }
        return {
            "ok": True,
            "yaml_path": str(Path(yaml_path)),
            "type_counts": type_counts,
            "exclude_cols": exclude_cols,
        }
    except Exception as exc:
        return _error_response(exc, yaml_path=yaml_path)


def summarize_expression_yaml(*, logic_yaml_path: str) -> dict[str, Any]:
    """Summarize calculated-column expression YAML."""
    try:
        expressions = load_expression_yaml(logic_yaml_path)
        return {
            "ok": True,
            "logic_yaml_path": str(Path(logic_yaml_path)),
            "count": len(expressions),
            "columns": [name for name, _ in expressions],
        }
    except Exception as exc:
        return _error_response(exc, logic_yaml_path=logic_yaml_path)


def _error_response(exc: Exception, **context: Any) -> dict[str, Any]:
    return {
        "ok": False,
        "error_type": type(exc).__name__,
        "error_message": str(exc),
        "context": {key: value for key, value in context.items() if value is not None},
    }
