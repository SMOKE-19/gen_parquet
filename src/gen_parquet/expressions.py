"""Calculated column expression helpers."""

from __future__ import annotations

from pathlib import Path
import re

import yaml


def load_expression_yaml(yaml_path: str | Path) -> list[tuple[str, str]]:
    """Load calculated-column expression YAML."""
    path = Path(yaml_path)
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        if isinstance(payload.get("expressions"), list):
            items = payload["expressions"]
        elif isinstance(payload.get("layers"), list):
            items = []
            for layer in payload["layers"]:
                if isinstance(layer, dict) and isinstance(layer.get("expressions"), list):
                    items.extend(layer["expressions"])
        else:
            raise ValueError(f"Expression YAML must contain 'expressions' or 'layers': {path}")
    else:
        raise ValueError(f"Expression YAML must be a list or mapping: {path}")

    expressions: list[tuple[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        column_name = str(
            item.get("column_name")
            or item.get("name")
            or item.get("result_column")
            or item.get("column")
            or ""
        ).strip()
        expression = str(
            item.get("sql_expression")
            or item.get("expression")
            or item.get("expr")
            or item.get("sql")
            or ""
        ).strip()
        if column_name and expression:
            expressions.append((column_name, expression))
    if not expressions:
        raise ValueError(f"Expression YAML has no expressions: {path}")
    return expressions


def normalize_expression_for_duckdb(expression: str) -> str:
    """Normalize a bracket-column expression into DuckDB-compatible SQL."""
    result: list[str] = []
    index = 0
    while index < len(expression):
        char = expression[index]
        if char == "'":
            literal, index = _read_single_quoted_literal(expression, index)
            result.append(literal)
            continue
        if char == '"':
            literal, index = _read_double_quoted_segment(expression, index)
            result.append(_double_quoted_to_sql_string(literal))
            continue
        if char == "[":
            identifier, index = _read_bracket_identifier(expression, index)
            result.append(_sql_identifier(identifier))
            continue
        if char.isalpha() or char == "_":
            identifier, next_index = _read_identifier(expression, index)
            cursor = _skip_spaces(expression, next_index)
            if cursor < len(expression) and expression[cursor] == "(":
                inner_text, end_index = _read_parenthesized(expression, cursor)
                args = [
                    normalize_expression_for_duckdb(arg)
                    for arg in _split_top_level_arguments(inner_text)
                ]
                rewritten_call = _rewrite_function_call_for_duckdb(identifier, args)
                result.append(rewritten_call)
                index = end_index
                continue
            result.append(identifier)
            index = next_index
            continue
        result.append(char)
        index += 1
    return "".join(result)


def _rewrite_function_call_for_duckdb(function_name: str, args: list[str]) -> str:
    lowered = function_name.strip().lower()
    if lowered in {"sum", "avg", "average", "count", "uniquecount", "max", "min"}:
        return _rewrite_row_level_aggregate(function_name, args)
    if lowered == "dateadd" and len(args) == 3:
        unit = _normalize_date_part_literal(args[0])
        return f"date_add({args[2]}, ({args[1]}) * INTERVAL 1 {unit})"
    if lowered == "datediff" and len(args) == 3:
        unit = _normalize_date_part_literal(args[0])
        return f"date_diff('{unit}', {args[1]}, {args[2]})"
    if lowered == "datepart" and len(args) == 2:
        unit = _normalize_date_part_literal(args[0])
        return f"date_part('{unit}', {args[1]})"
    if lowered == "charindex" and len(args) == 2:
        return f"position({args[0]} IN {args[1]})"
    if lowered == "charindex" and len(args) == 3:
        remainder = f"substr({args[1]}, {args[2]})"
        relative = f"position({args[0]} IN {remainder})"
        return (
            "CASE "
            f"WHEN {args[2]} <= 1 THEN position({args[0]} IN {args[1]}) "
            f"WHEN {relative} = 0 THEN 0 "
            f"ELSE {relative} + {args[2]} - 1 "
            "END"
        )
    if lowered == "isnull" and len(args) == 1:
        return f"({args[0]} IS NULL)"
    if lowered == "if" and len(args) == 3:
        return f"(CASE WHEN {args[0]} THEN {args[1]} ELSE {args[2]} END)"
    if lowered == "rxextract" and len(args) in {2, 3}:
        return f"regexp_extract({', '.join(args)})"
    if lowered == "rxreplace" and len(args) in {3, 4}:
        return f"regexp_replace({', '.join(args)})"

    cast_targets = {
        "integer": "INTEGER",
        "longinteger": "BIGINT",
        "real": "DOUBLE",
        "single": "REAL",
        "decimal": "DECIMAL",
        "string": "VARCHAR",
        "date": "DATE",
        "datetime": "TIMESTAMP",
        "time": "TIME",
        "boolean": "BOOLEAN",
    }
    cast_target = cast_targets.get(lowered)
    if cast_target is not None and len(args) == 1:
        return f"TRY_CAST({args[0]} AS {cast_target})"
    return f"{function_name}({', '.join(args)})"


def _rewrite_row_level_aggregate(function_name: str, args: list[str]) -> str:
    lowered = function_name.strip().lower()
    if not args:
        return f"{function_name}()"
    if lowered == "sum":
        additions = " + ".join(f"coalesce({arg}, 0)" for arg in args)
        checks = " OR ".join(f"{arg} IS NOT NULL" for arg in args)
        return f"(CASE WHEN {checks} THEN {additions} ELSE NULL END)"
    if lowered in {"avg", "average"}:
        numerator = " + ".join(f"coalesce({arg}, 0)" for arg in args)
        denominator = " + ".join(f"(CASE WHEN {arg} IS NULL THEN 0 ELSE 1 END)" for arg in args)
        return (
            "(CASE "
            f"WHEN ({denominator}) = 0 THEN NULL "
            f"ELSE ({numerator})::DOUBLE / ({denominator}) "
            "END)"
        )
    if lowered == "count":
        return "(" + " + ".join(f"(CASE WHEN {arg} IS NULL THEN 0 ELSE 1 END)" for arg in args) + ")"
    if lowered == "uniquecount":
        return f"len(list_distinct(list_filter([{', '.join(args)}], x -> x IS NOT NULL)))"
    if lowered == "max":
        return f"greatest({', '.join(args)})"
    if lowered == "min":
        return f"least({', '.join(args)})"
    return f"{function_name}({', '.join(args)})"


def _split_top_level_arguments(text: str) -> list[str]:
    args: list[str] = []
    start = 0
    index = 0
    depth = 0
    while index < len(text):
        char = text[index]
        if char == "'":
            _, index = _read_single_quoted_literal(text, index)
            continue
        if char == '"':
            _, index = _read_double_quoted_segment(text, index)
            continue
        if char == "[":
            _, index = _read_bracket_identifier(text, index)
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == "," and depth == 0:
            args.append(text[start:index].strip())
            start = index + 1
        index += 1
    tail = text[start:].strip()
    if tail:
        args.append(tail)
    return args


def _read_parenthesized(expression: str, start: int) -> tuple[str, int]:
    depth = 0
    index = start
    while index < len(expression):
        char = expression[index]
        if char == "'":
            _, index = _read_single_quoted_literal(expression, index)
            continue
        if char == '"':
            _, index = _read_double_quoted_segment(expression, index)
            continue
        if char == "[":
            _, index = _read_bracket_identifier(expression, index)
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return expression[start + 1:index], index + 1
        index += 1
    raise ValueError(f"Unclosed parenthesis in expression: {expression}")


def _read_identifier(expression: str, start: int) -> tuple[str, int]:
    match = re.match(r"[A-Za-z_][A-Za-z0-9_]*", expression[start:])
    if match is None:
        raise ValueError(f"Expected identifier at index {start}: {expression}")
    return match.group(0), start + len(match.group(0))


def _read_bracket_identifier(expression: str, start: int) -> tuple[str, int]:
    chars: list[str] = []
    index = start + 1
    while index < len(expression):
        char = expression[index]
        if char == "]":
            if index + 1 < len(expression) and expression[index + 1] == "]":
                chars.append("]")
                index += 2
                continue
            return "".join(chars), index + 1
        chars.append(char)
        index += 1
    raise ValueError(f"Unclosed bracket identifier in expression: {expression}")


def _read_single_quoted_literal(expression: str, start: int) -> tuple[str, int]:
    index = start + 1
    while index < len(expression):
        if expression[index] == "'":
            if index + 1 < len(expression) and expression[index + 1] == "'":
                index += 2
                continue
            return expression[start:index + 1], index + 1
        index += 1
    raise ValueError(f"Unclosed single-quoted literal in expression: {expression}")


def _read_double_quoted_segment(expression: str, start: int) -> tuple[str, int]:
    index = start + 1
    while index < len(expression):
        if expression[index] == '"':
            if index + 1 < len(expression) and expression[index + 1] == '"':
                index += 2
                continue
            return expression[start:index + 1], index + 1
        index += 1
    raise ValueError(f"Unclosed double-quoted segment in expression: {expression}")


def _double_quoted_to_sql_string(value: str) -> str:
    inner = value[1:-1].replace('""', '"')
    return "'" + inner.replace("'", "''") + "'"


def _normalize_date_part_literal(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == "'" and stripped[-1] == "'":
        stripped = stripped[1:-1].replace("''", "'")
    return stripped.strip().lower()


def _skip_spaces(expression: str, index: int) -> int:
    while index < len(expression) and expression[index].isspace():
        index += 1
    return index


def _sql_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'
