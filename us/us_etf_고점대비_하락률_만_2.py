import pandas as pd
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.chart import LineChart, Reference
from openpyxl.chart.axis import ChartLines


# ============================================================
# 설정
# ============================================================

# analysis 폴더
ANALYSIS_DIR = Path(
    r"D:\VSC0DE_파이썬\prj_etf_validation\us\data\us_etf\analysis"
)

# 분석할 ETF
# TICKERS = [
#     "TQQQ",
#     "QLD",
#     "QQQ",
#     "SPY",
#     "SCHD",
#     "DIA",
#     "DDM",
#     "UDOW",
# ]

# 분석할 ETF
TICKERS = [
    "QQQ",
    "QLD",
    "TQQQ",
    "SPY",
    "SSO",
    "SPXL",
    "SCHD",
    "DIA",
    "DDM",
    "UDOW",
]

# 비교할 ETF
COMPARE_TICKERS = [
    "TQQQ",
    "UDOW",
]

# 결과 파일
OUTPUT_FILE = ANALYSIS_DIR / "ETF_고점대비하락률_비교.xlsx"

# CSV 결과 파일
CSV_FILE = ANALYSIS_DIR / "ETF_고점대비하락률_비교.csv"


# ============================================================
# 색상 / 스타일
# ============================================================

# 최저값
MIN_FILL = PatternFill(
    fill_type="solid",
    fgColor="FFC7CE"
)

MIN_FONT = Font(
    color="9C0006",
    bold=True
)

# 헤더
HEADER_FILL = PatternFill(
    fill_type="solid",
    fgColor="D9EAF7"
)

HEADER_FONT = Font(
    bold=True
)

# 비교 Sheet 제목
TITLE_FILL = PatternFill(
    fill_type="solid",
    fgColor="1F4E78"
)

TITLE_FONT = Font(
    color="FFFFFF",
    bold=True,
    size=14
)

# 요약
SUMMARY_FILL = PatternFill(
    fill_type="solid",
    fgColor="E7E6E6"
)

SUMMARY_FONT = Font(
    bold=True
)

# 최대 낙폭
MAX_DD_FILL = PatternFill(
    fill_type="solid",
    fgColor="FFC7CE"
)

MAX_DD_FONT = Font(
    color="9C0006",
    bold=True
)


# ============================================================
# ETF별 CSV 읽기
# ============================================================

data_list = []

for ticker in TICKERS:

    file_path = ANALYSIS_DIR / f"{ticker}_analysis.csv"

    if not file_path.exists():

        print(f"[경고] 파일 없음: {file_path}")

        continue

    print(f"[읽는 중] {ticker}")

    try:

        df = pd.read_csv(
            file_path,
            encoding="utf-8-sig"
        )

    except UnicodeDecodeError:

        df = pd.read_csv(
            file_path,
            encoding="cp949"
        )

    # --------------------------------------------------------
    # 필수 컬럼 확인
    # --------------------------------------------------------

    required_columns = [
        "날짜",
        "고점_대비_하락률"
    ]

    for column in required_columns:

        if column not in df.columns:

            raise ValueError(
                f"{ticker}_analysis.csv에 "
                f"'{column}' 컬럼이 없습니다."
            )

    # --------------------------------------------------------
    # 날짜 변환
    # --------------------------------------------------------

    df["날짜"] = pd.to_datetime(
        df["날짜"],
        errors="coerce"
    )

    df = df.dropna(
        subset=["날짜"]
    )

    # --------------------------------------------------------
    # 필요한 데이터만 추출
    # --------------------------------------------------------

    temp = df[
        [
            "날짜",
            "고점_대비_하락률"
        ]
    ].copy()

    # --------------------------------------------------------
    # 숫자 변환
    # --------------------------------------------------------

    temp["고점_대비_하락률"] = pd.to_numeric(
        temp["고점_대비_하락률"],
        errors="coerce"
    )

    # --------------------------------------------------------
    # ETF 이름으로 컬럼 변경
    # --------------------------------------------------------

    temp.rename(
        columns={
            "고점_대비_하락률": ticker
        },
        inplace=True
    )

    # --------------------------------------------------------
    # 중복 날짜 제거
    # --------------------------------------------------------

    temp = temp.drop_duplicates(
        subset=["날짜"]
    )

    data_list.append(temp)


# ============================================================
# 데이터 확인
# ============================================================

if not data_list:

    raise ValueError(
        "읽을 수 있는 ETF analysis CSV 파일이 없습니다."
    )


# ============================================================
# 날짜 기준 병합
# ============================================================

result = data_list[0]

for df in data_list[1:]:

    result = pd.merge(
        result,
        df,
        on="날짜",
        how="outer"
    )


# ============================================================
# 날짜순 정렬
# ============================================================

result = result.sort_values(
    by="날짜"
).reset_index(
    drop=True
)


# ============================================================
# 숫자 반올림
# ============================================================

for ticker in TICKERS:

    if ticker in result.columns:

        result[ticker] = pd.to_numeric(
            result[ticker],
            errors="coerce"
        )

        result[ticker] = result[ticker].round(2)


# ============================================================
# CSV 저장
# ============================================================

csv_result = result.copy()

csv_result["날짜"] = csv_result[
    "날짜"
].dt.strftime("%Y-%m-%d")

csv_result.to_csv(
    CSV_FILE,
    index=False,
    encoding="utf-8-sig"
)


# ============================================================
# Excel 저장
# ============================================================

with pd.ExcelWriter(
    OUTPUT_FILE,
    engine="openpyxl",
    date_format="yyyy-mm-dd"
) as writer:

    # ========================================================
    # 전체 Sheet
    # ========================================================

    result.to_excel(
        writer,
        sheet_name="전체",
        index=False
    )

    # ========================================================
    # 연도별 Sheet
    # ========================================================

    years = sorted(
        result["날짜"]
        .dt.year
        .dropna()
        .unique()
    )

    for year in years:

        yearly_data = result[
            result["날짜"].dt.year == year
        ].copy()

        yearly_data = yearly_data.sort_values(
            by="날짜"
        )

        yearly_data.to_excel(
            writer,
            sheet_name=str(year),
            index=False
        )


# ============================================================
# Excel 불러오기
# ============================================================

wb = load_workbook(
    OUTPUT_FILE
)


# ============================================================
# 기존 Sheet 서식
# ============================================================

def format_sheet(ws):

    # --------------------------------------------------------
    # 헤더
    # --------------------------------------------------------

    for cell in ws[1]:

        cell.fill = HEADER_FILL

        cell.font = HEADER_FONT

        cell.alignment = Alignment(
            horizontal="center",
            vertical="center"
        )

    # --------------------------------------------------------
    # 헤더 위치 찾기
    # --------------------------------------------------------

    header_map = {}

    for cell in ws[1]:

        header_map[cell.value] = cell.column

    # --------------------------------------------------------
    # 날짜 컬럼
    # --------------------------------------------------------

    date_col = header_map.get("날짜")

    if date_col:

        for row in range(
            2,
            ws.max_row + 1
        ):

            cell = ws.cell(
                row=row,
                column=date_col
            )

            cell.alignment = Alignment(
                horizontal="center",
                vertical="center"
            )

            cell.number_format = "yyyy-mm-dd"

    # --------------------------------------------------------
    # 현재 데이터 마지막 행
    # --------------------------------------------------------

    last_data_row = ws.max_row

    # --------------------------------------------------------
    # ETF별 최소값 표시
    # --------------------------------------------------------

    for ticker in TICKERS:

        if ticker not in header_map:

            continue

        col = header_map[ticker]

        values = []

        for row in range(
            2,
            last_data_row + 1
        ):

            cell = ws.cell(
                row=row,
                column=col
            )

            if cell.value is None:

                continue

            try:

                value = float(cell.value)

                values.append(
                    (row, value)
                )

            except (
                ValueError,
                TypeError
            ):

                continue

        if not values:

            continue

        # 최소값
        min_value = min(
            value
            for row, value in values
        )

        # 최소값 셀 강조
        for row, value in values:

            if value == min_value:

                cell = ws.cell(
                    row=row,
                    column=col
                )

                cell.fill = MIN_FILL

                cell.font = MIN_FONT

                cell.alignment = Alignment(
                    horizontal="center",
                    vertical="center"
                )

    # --------------------------------------------------------
    # 최소값 요약행
    # --------------------------------------------------------

    summary_row = last_data_row + 1

    if date_col:

        summary_date_cell = ws.cell(
            row=summary_row,
            column=date_col
        )

        summary_date_cell.value = "최저값"

        summary_date_cell.fill = SUMMARY_FILL

        summary_date_cell.font = SUMMARY_FONT

        summary_date_cell.alignment = Alignment(
            horizontal="center",
            vertical="center"
        )

    for ticker in TICKERS:

        if ticker not in header_map:

            continue

        col = header_map[ticker]

        values = []

        for row in range(
            2,
            last_data_row + 1
        ):

            cell = ws.cell(
                row=row,
                column=col
            )

            if cell.value is None:

                continue

            try:

                values.append(
                    float(cell.value)
                )

            except (
                ValueError,
                TypeError
            ):

                continue

        if not values:

            continue

        min_value = min(values)

        summary_cell = ws.cell(
            row=summary_row,
            column=col
        )

        summary_cell.value = min_value

        summary_cell.fill = MIN_FILL

        summary_cell.font = MIN_FONT

        summary_cell.alignment = Alignment(
            horizontal="center",
            vertical="center"
        )

        summary_cell.number_format = "0.00"

    # --------------------------------------------------------
    # 컬럼 너비
    # --------------------------------------------------------

    if date_col:

        ws.column_dimensions[
            get_column_letter(date_col)
        ].width = 14

    for ticker in TICKERS:

        if ticker in header_map:

            col = header_map[ticker]

            ws.column_dimensions[
                get_column_letter(col)
            ].width = 12

    # --------------------------------------------------------
    # 틀 고정
    # --------------------------------------------------------

    ws.freeze_panes = "B2"

    # --------------------------------------------------------
    # 자동 필터
    # --------------------------------------------------------

    if last_data_row >= 2:

        ws.auto_filter.ref = (
            f"A1:"
            f"{get_column_letter(ws.max_column)}"
            f"{last_data_row}"
        )


# ============================================================
# 기존 Sheet에 서식 적용
# ============================================================

for ws in wb.worksheets:

    format_sheet(ws)


# ============================================================
# TQQQ vs UDOW 비교 Sheet 생성
# ============================================================

if "TQQQ_vs_UDOW" in wb.sheetnames:

    del wb["TQQQ_vs_UDOW"]


ws = wb.create_sheet(
    "TQQQ_vs_UDOW"
)


# ============================================================
# 비교 데이터 준비
# ============================================================

compare = result[
    [
        "날짜",
        "TQQQ",
        "UDOW"
    ]
].copy()


# 결측치 제거
compare = compare.dropna(
    subset=[
        "TQQQ",
        "UDOW"
],
    how="all"
)


# ------------------------------------------------------------
# 낙폭 차이
# ------------------------------------------------------------

compare["TQQQ_UDOW_차이"] = (
    compare["TQQQ"]
    -
    compare["UDOW"]
)


# ============================================================
# 최대 낙폭 계산
# ============================================================

tqqq_data = compare[
    ["날짜", "TQQQ"]
].dropna()


udow_data = compare[
    ["날짜", "UDOW"]
].dropna()


# ------------------------------------------------------------
# TQQQ 최대 낙폭
# ------------------------------------------------------------

tqqq_min_idx = tqqq_data[
    "TQQQ"
].idxmin()

tqqq_max_dd = tqqq_data.loc[
    tqqq_min_idx,
    "TQQQ"
]

tqqq_max_dd_date = tqqq_data.loc[
    tqqq_min_idx,
    "날짜"
]


# ------------------------------------------------------------
# UDOW 최대 낙폭
# ------------------------------------------------------------

udow_min_idx = udow_data[
    "UDOW"
].idxmin()

udow_max_dd = udow_data.loc[
    udow_min_idx,
    "UDOW"
]

udow_max_dd_date = udow_data.loc[
    udow_min_idx,
    "날짜"
]


# ============================================================
# Sheet 제목
# ============================================================

ws["A1"] = "TQQQ vs UDOW 고점 대비 하락률 비교"

ws["A1"].fill = TITLE_FILL

ws["A1"].font = TITLE_FONT

ws["A1"].alignment = Alignment(
    horizontal="center",
    vertical="center"
)

ws.merge_cells(
    "A1:F1"
)

ws.row_dimensions[1].height = 25


# ============================================================
# 최대 낙폭 요약
# ============================================================

ws["A3"] = "최대 낙폭 비교"

ws["A3"].fill = SUMMARY_FILL

ws["A3"].font = SUMMARY_FONT


summary_headers = [
    "ETF",
    "최대 낙폭",
    "발생일"
]


for col, header in enumerate(
    summary_headers,
    start=1
):

    cell = ws.cell(
        row=4,
        column=col
    )

    cell.value = header

    cell.fill = HEADER_FILL

    cell.font = HEADER_FONT

    cell.alignment = Alignment(
        horizontal="center",
        vertical="center"
    )


# TQQQ
ws["A5"] = "TQQQ"

ws["B5"] = tqqq_max_dd

ws["C5"] = tqqq_max_dd_date


# UDOW
ws["A6"] = "UDOW"

ws["B6"] = udow_max_dd

ws["C6"] = udow_max_dd_date


# ------------------------------------------------------------
# 최대 낙폭 서식
# ------------------------------------------------------------

for cell in [
    ws["B5"],
    ws["B6"]
]:

    cell.fill = MAX_DD_FILL

    cell.font = MAX_DD_FONT

    cell.number_format = "0.00"


for cell in [
    ws["C5"],
    ws["C6"]
]:

    cell.number_format = "yyyy-mm-dd"


# ============================================================
# 최대 낙폭 차이
# ============================================================

ws["E3"] = "최대 낙폭 차이"

ws["E3"].fill = SUMMARY_FILL

ws["E3"].font = SUMMARY_FONT


ws["E4"] = "TQQQ 최대 낙폭"

ws["F4"] = tqqq_max_dd

ws["E5"] = "UDOW 최대 낙폭"

ws["F5"] = udow_max_dd

ws["E6"] = "차이"

ws["F6"] = (
    tqqq_max_dd
    -
    udow_max_dd
)


for cell in [
    ws["F4"],
    ws["F5"],
    ws["F6"]
]:

    cell.number_format = "0.00"


ws["F6"].fill = MAX_DD_FILL

ws["F6"].font = MAX_DD_FONT


# ============================================================
# 비교 데이터 시작
# ============================================================

DATA_START_ROW = 9


headers = [
    "날짜",
    "TQQQ",
    "UDOW",
    "TQQQ-UDOW"
]


for col, header in enumerate(
    headers,
    start=1
):

    cell = ws.cell(
        row=DATA_START_ROW,
        column=col
    )

    cell.value = header

    cell.fill = HEADER_FILL

    cell.font = HEADER_FONT

    cell.alignment = Alignment(
        horizontal="center",
        vertical="center"
    )


# ============================================================
# 비교 데이터 입력
# ============================================================

for row_idx, row_data in enumerate(
    compare.itertuples(index=False),
    start=DATA_START_ROW + 1
):

    # 날짜
    ws.cell(
        row=row_idx,
        column=1
    ).value = row_data[0]

    # TQQQ
    ws.cell(
        row=row_idx,
        column=2
    ).value = row_data[1]

    # UDOW
    ws.cell(
        row=row_idx,
        column=3
    ).value = row_data[2]

    # 차이
    ws.cell(
        row=row_idx,
        column=4
    ).value = row_data[3]


# ============================================================
# 비교 데이터 서식
# ============================================================

last_row = (
    DATA_START_ROW
    +
    len(compare)
)


for row in range(
    DATA_START_ROW + 1,
    last_row + 1
):

    # 날짜
    ws.cell(
        row=row,
        column=1
    ).number_format = "yyyy-mm-dd"

    # 숫자
    for col in [2, 3, 4]:

        ws.cell(
            row=row,
            column=col
        ).number_format = "0.00"


# ============================================================
# 최대 낙폭 발생일 강조
# ============================================================

for row in range(
    DATA_START_ROW + 1,
    last_row + 1
):

    date_value = ws.cell(
        row=row,
        column=1
    ).value

    tqqq_value = ws.cell(
        row=row,
        column=2
    ).value

    udow_value = ws.cell(
        row=row,
        column=3
    ).value

    # TQQQ 최대 낙폭
    if (
        pd.notna(tqqq_value)
        and tqqq_value == tqqq_max_dd
    ):

        ws.cell(
            row=row,
            column=2
        ).fill = MAX_DD_FILL

        ws.cell(
            row=row,
            column=2
        ).font = MAX_DD_FONT

    # UDOW 최대 낙폭
    if (
        pd.notna(udow_value)
        and udow_value == udow_max_dd
    ):

        ws.cell(
            row=row,
            column=3
        ).fill = MAX_DD_FILL

        ws.cell(
            row=row,
            column=3
        ).font = MAX_DD_FONT


# ============================================================
# 그래프 1
# TQQQ vs UDOW 고점 대비 하락률
# ============================================================

chart1 = LineChart()

chart1.title = (
    "TQQQ vs UDOW 고점 대비 하락률"
)

chart1.style = 2

chart1.y_axis.title = "고점 대비 하락률 (%)"

chart1.x_axis.title = "날짜"

chart1.height = 9

chart1.width = 20


# TQQQ + UDOW
data = Reference(
    ws,
    min_col=2,
    max_col=3,
    min_row=DATA_START_ROW,
    max_row=last_row
)

# 날짜
categories = Reference(
    ws,
    min_col=1,
    min_row=DATA_START_ROW + 1,
    max_row=last_row
)


chart1.add_data(
    data,
    titles_from_data=True
)

chart1.set_categories(
    categories
)


# 0선 기준선
chart1.y_axis.majorGridlines = ChartLines()


# 위치
ws.add_chart(
    chart1,
    "F9"
)


# ============================================================
# 그래프 2
# TQQQ - UDOW 낙폭 차이
# ============================================================

chart2 = LineChart()

chart2.title = (
    "TQQQ - UDOW 낙폭 차이"
)

chart2.style = 10

chart2.y_axis.title = (
    "낙폭 차이 (%p)"
)

chart2.x_axis.title = "날짜"

chart2.height = 9

chart2.width = 20


# 차이 데이터
difference_data = Reference(
    ws,
    min_col=4,
    max_col=4,
    min_row=DATA_START_ROW,
    max_row=last_row
)

chart2.add_data(
    difference_data,
    titles_from_data=True
)

chart2.set_categories(
    categories
)

chart2.y_axis.majorGridlines = ChartLines()


ws.add_chart(
    chart2,
    "F28"
)


# ============================================================
# 컬럼 너비
# ============================================================

ws.column_dimensions["A"].width = 14

ws.column_dimensions["B"].width = 14

ws.column_dimensions["C"].width = 14

ws.column_dimensions["D"].width = 16

ws.column_dimensions["E"].width = 18

ws.column_dimensions["F"].width = 14


# ============================================================
# 틀 고정
# ============================================================

ws.freeze_panes = "A10"


# ============================================================
# 자동 필터
# ============================================================

ws.auto_filter.ref = (
    f"A{DATA_START_ROW}:D{last_row}"
)


# ============================================================
# Excel 저장
# ============================================================

wb.save(
    OUTPUT_FILE
)


# ============================================================
# 완료 메시지
# ============================================================

print()
print("=" * 70)
print("Excel 생성 완료")
print("=" * 70)

print()

print(
    f"파일 : {OUTPUT_FILE}"
)

print()

print(
    "TQQQ vs UDOW 비교 Sheet 생성 완료"
)

print()

print(
    f"TQQQ 최대 낙폭 : "
    f"{tqqq_max_dd:.2f}% "
    f"({tqqq_max_dd_date:%Y-%m-%d})"
)

print(
    f"UDOW 최대 낙폭 : "
    f"{udow_max_dd:.2f}% "
    f"({udow_max_dd_date:%Y-%m-%d})"
)

print()

print(
    "생성된 그래프"
)

print(
    "1. TQQQ vs UDOW 고점 대비 하락률"
)

print(
    "2. TQQQ - UDOW 낙폭 차이"
)

print()
print("=" * 70)

