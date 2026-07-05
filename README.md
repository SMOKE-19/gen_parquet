# gen-parquet

TSV 형식의 `.txt` 테이블을 타입 지정 YAML과 Parquet 파일로 변환하는 Python 패키지입니다.
YAML 기반 계산 컬럼 추가도 지원합니다.

## 주요 기능

- 탭 구분 `.txt` 파일의 컬럼 타입 제안 YAML 생성
- 타입별 리스트 구조의 YAML을 사용한 Parquet 변환
- `exclude_cols`를 통한 출력 제외 컬럼 지정
- YAML에서 타입을 직접 옮겨 지정하는 강제 캐스팅
- `expressions` 또는 `layers` YAML을 사용한 계산 컬럼 추가

## 설치와 검증

```bash
uv sync
uv run gen-parquet
uv run ruff check .
```

GitHub Actions의 `Build wheel` 워크플로는 `main` push, pull request, 수동 실행에서 wheel을
빌드하고 `gen-parquet-wheel` artifact로 업로드합니다. `v*` 태그를 푸시하면 GitHub Release를
생성하고 wheel 파일을 release asset으로 업로드합니다.

Release wheel을 내려받아 가상환경에 설치할 수도 있습니다.

```bash
python -m venv .venv
. .venv/bin/activate
pip install gen_parquet-0.1.0-py3-none-any.whl
```

## 기본 사용

```python
from gen_parquet import txt_to_parquet, write_type_yaml

yaml_path = write_type_yaml("input.txt")
txt_to_parquet("input.txt", yaml_path, "output.parquet")
```

타입 제안은 기본적으로 전체 행을 스캔하며, null 값은 제외하고 non-null 값 기준으로 판단합니다.
`null + 숫자` 조합은 숫자 타입으로 제안됩니다. category 타입은 자동 생성하지 않습니다.

생성된 YAML에는 주석 처리된 `exclude_cols` 예시가 포함됩니다. 주석을 풀어 컬럼명을 넣으면
해당 컬럼이 `types` 아래에 있더라도 Parquet 출력에서 제외됩니다.

YAML에서 컬럼을 다른 타입 목록으로 옮기면 그 타입으로 강제 캐스팅합니다. 캐스팅 가능한 값은
변환하고, 호환되지 않는 non-null 값은 에러 대신 null로 저장합니다.

## 계산 컬럼

```python
from gen_parquet import add_calculated_columns

add_calculated_columns("expression_logic.yaml", "input.parquet", "output.calculated.parquet")
```

YAML은 `expressions` 또는 `layers` 키를 지원하며, 각 항목은 `column_name`과
`sql_expression`을 사용합니다. 컬럼 참조는 `[column_name]` 형태를 사용할 수 있으며,
내부적으로 DuckDB SQL로 변환해 계산합니다.

## 스크립트

- `scripts/generate_type_yamls.py`: 상단 `TXT_DIR`를 수정해 폴더 안의 `.txt`별 YAML 생성
- `scripts/convert_txt_to_parquet.py`: 상단 `TXT_PATH`, `TYPE_YAML_PATH`, `OUTPUT_PATH`를 수정해 Parquet 변환
- `scripts/add_calculated_columns.py`: 상단 `LOGIC_YAML_PATH`, `PARQUET_PATH`, `OUTPUT_PATH`를 수정해 계산 컬럼 추가

wheel을 설치한 가상환경에서는 다음 console script를 사용할 수 있습니다.

```bash
gen-parquet-type-yamls ./examples
gen-parquet-convert input.txt input.yaml output.parquet
gen-parquet-add-cols expression_logic.yaml input.parquet output.calculated.parquet
```

## MCP 서버

MCP stdio 서버는 optional dependency로 분리되어 있습니다.

```bash
pip install "gen-parquet[mcp]"
gen-parquet-mcp
```

로컬 개발 환경에서는 다음처럼 실행할 수 있습니다.

```bash
uv sync --extra mcp
uv run gen-parquet-mcp
```

## OpenCode에서 MCP 연결

OpenCode는 stdio command로 MCP 서버를 실행할 수 있습니다. wheel을 설치한 가상환경을 사용할
경우 OpenCode 설정의 MCP 서버 command를 해당 가상환경의 `gen-parquet-mcp`로 지정합니다.

예시:

```json
{
  "mcp": {
    "gen-parquet": {
      "type": "local",
      "command": ".venv/bin/gen-parquet-mcp",
      "enabled": true
    }
  }
}
```

개발 checkout을 직접 연결할 때는 `uv run`을 command로 둘 수 있습니다.

```json
{
  "mcp": {
    "gen-parquet-dev": {
      "type": "local",
      "command": "uv",
      "args": ["run", "gen-parquet-mcp"],
      "enabled": true
    }
  }
}
```

OpenCode에서 tool이 보이면 `inspect_parquet`, `generate_type_yaml`,
`convert_txt_to_parquet`, `add_calculated_columns` 순서로 작은 예제 파일부터 호출해 연결을
확인합니다.

제공 tool:

- `generate_type_yaml`
- `generate_type_yamls_for_dir`
- `convert_txt_to_parquet`
- `add_calculated_columns`
- `inspect_parquet`
- `summarize_type_yaml`
- `summarize_expression_yaml`

## MCP 서버 개발 가이드

MCP 서버 기능을 수정할 때는 아래 파일을 기준으로 작업합니다.

- `src/gen_parquet/mcp_server.py`: OpenCode/MCP client에 노출할 tool 이름, 인자, docstring 등록
- `src/gen_parquet/mcp_tools.py`: tool이 실제로 호출하는 Python 함수, 응답 dict, 에러 처리 구현
- `src/gen_parquet/core.py`: TSV/YAML/Parquet 변환 핵심 로직 수정
- `src/gen_parquet/expressions.py`: 계산 컬럼 expression YAML 파싱과 DuckDB SQL 변환 로직 수정
- `pyproject.toml`: `mcp` optional dependency 또는 `gen-parquet-mcp` entrypoint 변경
- `README.md`: OpenCode 연결 방법, 제공 tool 목록, 개발 시 수정 파일 목록 갱신

새 MCP tool을 추가할 때는 먼저 `mcp_tools.py`에 JSON-safe dict를 반환하는 함수를 만들고,
그 다음 `mcp_server.py`의 `build_server()` 안에서 `@server.tool()`로 등록합니다. tool이 새
의존성을 필요로 하면 `pyproject.toml`의 기본 dependency 또는 `[project.optional-dependencies].mcp`
중 맞는 위치에 추가하고 `uv lock`을 다시 실행합니다.

수정 후 최소 확인:

```bash
uv lock
uv sync --extra mcp
uv run ruff check .
uv run gen-parquet-mcp --help
uv build --wheel
```

## 구조

```text
gen_parquet/
├── pyproject.toml
├── src/gen_parquet/
│   ├── __init__.py
│   ├── cli.py
│   ├── core.py
│   ├── expressions.py
│   ├── mcp_server.py
│   └── mcp_tools.py
├── examples/
└── scripts/
```

## 라이선스

이 프로젝트는 MIT License로 배포됩니다. 자세한 내용은 [LICENSE](LICENSE)를 확인하세요.
