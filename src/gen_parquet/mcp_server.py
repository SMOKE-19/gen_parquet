"""stdio MCP server entrypoint for gen-parquet tools."""

from __future__ import annotations

from typing import Any
import argparse

from gen_parquet import mcp_tools


def build_server() -> Any:
    """Build a FastMCP server when the optional MCP SDK is installed."""
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception as exc:  # pragma: no cover - depends on optional dependency.
        raise RuntimeError(
            "The optional MCP SDK is not installed. Install with `pip install gen-parquet[mcp]`."
        ) from exc

    server = FastMCP("gen-parquet")

    @server.tool()
    def generate_type_yaml(
        txt_path: str,
        yaml_path: str | None = None,
        sample_rows: int | None = None,
        comment_values: int = 10,
    ) -> dict[str, Any]:
        return mcp_tools.generate_type_yaml_tool(
            txt_path=txt_path,
            yaml_path=yaml_path,
            sample_rows=sample_rows,
            comment_values=comment_values,
        )

    @server.tool()
    def generate_type_yamls_for_dir(
        txt_dir: str,
        pattern: str = "*.txt",
        sample_rows: int | None = None,
        comment_values: int = 10,
    ) -> dict[str, Any]:
        return mcp_tools.generate_type_yamls_for_dir_tool(
            txt_dir=txt_dir,
            pattern=pattern,
            sample_rows=sample_rows,
            comment_values=comment_values,
        )

    @server.tool()
    def convert_txt_to_parquet(txt_path: str, type_yaml_path: str, output_path: str) -> dict[str, Any]:
        return mcp_tools.convert_txt_to_parquet_tool(
            txt_path=txt_path,
            type_yaml_path=type_yaml_path,
            output_path=output_path,
        )

    @server.tool()
    def add_calculated_columns(logic_yaml_path: str, parquet_path: str, output_path: str) -> dict[str, Any]:
        return mcp_tools.add_calculated_columns_tool(
            logic_yaml_path=logic_yaml_path,
            parquet_path=parquet_path,
            output_path=output_path,
        )

    @server.tool()
    def inspect_parquet(parquet_path: str, max_columns: int = 80) -> dict[str, Any]:
        return mcp_tools.inspect_parquet(parquet_path=parquet_path, max_columns=max_columns)

    @server.tool()
    def summarize_type_yaml(yaml_path: str) -> dict[str, Any]:
        return mcp_tools.summarize_type_yaml(yaml_path=yaml_path)

    @server.tool()
    def summarize_expression_yaml(logic_yaml_path: str) -> dict[str, Any]:
        return mcp_tools.summarize_expression_yaml(logic_yaml_path=logic_yaml_path)

    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the gen-parquet MCP stdio server.")
    parser.parse_args(argv)
    server = build_server()
    server.run()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
