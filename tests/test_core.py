import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from gen_parquet.core import add_calculated_columns, package_name, txt_to_parquet, write_type_yaml


def test_package_name() -> None:
    assert package_name() == "gen_parquet"


def test_write_type_yaml_and_convert_to_parquet(tmp_path) -> None:
    txt_path = tmp_path / "table.txt"
    txt_path.write_text(
        "\t".join(["id", "name", "score", "active", "created_on", "created_at"]) + "\n"
        "1\talice\t10.5\ttrue\t2026-01-01\t2026-01-01T10:30:00\n"
        "2\tbob\t20.25\tfalse\t2026-01-02\t2026-01-02T10:30:00\n",
        encoding="utf-8",
    )

    yaml_path = write_type_yaml(txt_path)

    yaml_text = yaml_path.read_text(encoding="utf-8")
    assert "integer:" in yaml_text
    assert "float:" in yaml_text
    assert "boolean:" in yaml_text
    assert "date:" in yaml_text
    assert "datetime:" in yaml_text
    assert "# exclude_cols:" in yaml_text
    assert "# samples: 1, 2" in yaml_text
    assert '- "id"' in yaml_text

    parquet_path = txt_to_parquet(txt_path, yaml_path, tmp_path / "table.parquet")

    table = pq.read_table(parquet_path)
    assert table.column_names == ["id", "name", "score", "active", "created_on", "created_at"]
    assert table.to_pydict()["id"] == [1, 2]
    assert table.to_pydict()["active"] == [True, False]


def test_duplicate_columns_raise(tmp_path) -> None:
    txt_path = tmp_path / "duplicate.txt"
    txt_path.write_text("id\tid\n1\t2\n", encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate columns"):
        write_type_yaml(txt_path)


def test_type_yaml_uses_all_rows_by_default(tmp_path) -> None:
    txt_path = tmp_path / "all_rows.txt"
    rows = ["value", *["1" for _ in range(1000)], "not_a_number"]
    txt_path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    yaml_path = write_type_yaml(txt_path)

    yaml_text = yaml_path.read_text(encoding="utf-8")
    assert "  string:\n    # samples: " in yaml_text
    assert '- "value"' in yaml_text


def test_null_and_numbers_stay_numeric(tmp_path) -> None:
    txt_path = tmp_path / "null_numbers.txt"
    txt_path.write_text("amount\n \nNULL\n10\n20\n", encoding="utf-8")

    yaml_path = write_type_yaml(txt_path)

    yaml_text = yaml_path.read_text(encoding="utf-8")
    assert "  integer:\n    # samples: 10, 20\n    - \"amount\"" in yaml_text


def test_leading_zero_code_stays_string(tmp_path) -> None:
    txt_path = tmp_path / "codes.txt"
    txt_path.write_text("postal_code\n00001\n00002\n", encoding="utf-8")

    yaml_path = write_type_yaml(txt_path)

    yaml_text = yaml_path.read_text(encoding="utf-8")
    assert "  string:\n    # samples: 00001, 00002\n    - \"postal_code\"" in yaml_text


def test_exclude_cols_omit_columns_even_when_typed(tmp_path) -> None:
    txt_path = tmp_path / "exclude.txt"
    yaml_path = tmp_path / "exclude.yaml"
    txt_path.write_text("id\tname\tskip_me\n1\talice\t10\n2\tbob\t20\n", encoding="utf-8")
    yaml_path.write_text(
        """
exclude_cols:
  - skip_me
types:
  integer:
    - id
    - skip_me
  string:
    - name
""",
        encoding="utf-8",
    )

    parquet_path = txt_to_parquet(txt_path, yaml_path, tmp_path / "exclude.parquet")

    table = pq.read_table(parquet_path)
    assert table.column_names == ["id", "name"]
    assert table.to_pydict() == {"id": [1, 2], "name": ["alice", "bob"]}


def test_forced_cast_keeps_compatible_values_and_nulls_incompatible_values(tmp_path) -> None:
    txt_path = tmp_path / "forced_cast.txt"
    yaml_path = tmp_path / "forced_cast.yaml"
    txt_path.write_text("mixed\n1\nabc\n002\n3.5\nNULL\n", encoding="utf-8")
    yaml_path.write_text(
        """
types:
  integer:
    - mixed
  boolean: []
  float: []
  date: []
  datetime: []
  string: []
""",
        encoding="utf-8",
    )

    parquet_path = txt_to_parquet(txt_path, yaml_path, tmp_path / "forced_cast.parquet")

    table = pq.read_table(parquet_path)
    assert table.to_pydict()["mixed"] == [1, None, 2, None, None]


def test_add_calculated_columns_from_expression_logic_yaml(tmp_path) -> None:
    parquet_path = tmp_path / "input.parquet"
    logic_yaml_path = tmp_path / "logic.yaml"
    output_path = tmp_path / "output.parquet"
    table = pa.table(
        {
            "amount": [50, 125, None],
            "name": ["alice", "bob", "carol"],
            "raw_number": ["1", "bad", "003"],
        }
    )
    pq.write_table(table, parquet_path)
    logic_yaml_path.write_text(
        """
expressions:
  - column_name: amount_band
    sql_expression: CASE WHEN [amount] >= 100 THEN 'HIGH' ELSE 'LOW' END
  - column_name: risk_flag
    sql_expression: If([amount_band] = 'HIGH', 'Y', 'N')
  - column_name: parsed_number
    sql_expression: Integer([raw_number])
""",
        encoding="utf-8",
    )

    calculated_path = add_calculated_columns(logic_yaml_path, parquet_path, output_path)

    result = pq.read_table(calculated_path).to_pydict()
    assert result["amount_band"] == ["LOW", "HIGH", "LOW"]
    assert result["risk_flag"] == ["N", "Y", "N"]
    assert result["parsed_number"] == [1, None, 3]
