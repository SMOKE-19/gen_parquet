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
uv run pytest
uv run ruff check .
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

## 구조

```text
gen_parquet/
├── pyproject.toml
├── src/gen_parquet/
│   ├── __init__.py
│   ├── cli.py
│   └── core.py
├── tests/
│   └── test_core.py
├── examples/
└── scripts/
```

## 라이선스

이 프로젝트는 MIT License로 배포됩니다. 자세한 내용은 [LICENSE](LICENSE)를 확인하세요.
