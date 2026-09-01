"""
============================================================
compare_spy_qqq_tqqq.py
============================================================

SPY / QQQ / TQQQ 비교 분석

입력:
    data/us_etf/SPY_analysis.csv
    data/us_etf/QQQ_analysis.csv
    data/us_etf/TQQQ_analysis.csv

출력:
    data/us_etf/analysis/SPY_QQQ_TQQQ_comparison.xlsx

주요 분석
------------------------------------------------------------
1. 최종 투자금액
2. 총수익률
3. CAGR
4. MDD
5. MDD 시작일
6. MDD 저점일
7. MDD 회복일
8. MDD 회복기간
9. MDD 회복 거래일
10. 연도별 수익률
11. 월별 수익률
12. 누적수익률
13. Drawdown
14. 변동성
15. 승률
16. 최고/최악 연도
17. Excel 차트
============================================================
"""

from pathlib import Path
import pandas as pd
import numpy as np

from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.chart import LineChart, Reference
from openpyxl.chart import BarChart
from openpyxl.utils import get_column_letter


# ============================================================
# 설정
# ============================================================

DATA_DIR = Path("us/data/us_etf/analysis")
OUTPUT_DIR = DATA_DIR / "analysis"

OUTPUT_FILE = OUTPUT_DIR / "SPY_QQQ_TQQQ_comparison.xlsx"

INITIAL_INVESTMENT = 10_000_000

ETF_FILES = {
    "SPY": DATA_DIR / "SPY_analysis.csv",
    "QQQ": DATA_DIR / "QQQ_analysis.csv",
    "TQQQ": DATA_DIR / "TQQQ_analysis.csv",
}


# ============================================================
# CSV 읽기
# ============================================================

def load_etf_csv(path: Path, ticker: str):

    if not path.exists():
        raise FileNotFoundError(
            f"\n파일을 찾을 수 없습니다.\n"
            f"ETF: {ticker}\n"
            f"경로: {path.resolve()}"
        )

    print(f"[로드] {ticker}: {path}")

    df = pd.read_csv(path)

    if "날짜" not in df.columns:
        raise ValueError(
            f"{ticker} CSV에 '날짜' 컬럼이 없습니다."
        )

    if "수정주가" not in df.columns:
        raise ValueError(
            f"{ticker} CSV에 '수정주가' 컬럼이 없습니다."
        )

    df["날짜"] = pd.to_datetime(df["날짜"])

    df["수정주가"] = pd.to_numeric(
        df["수정주가"],
        errors="coerce"
    )

    df = df.dropna(
        subset=["날짜", "수정주가"]
    )

    df = df.sort_values("날짜")
    df = df.drop_duplicates("날짜")

    df = df.set_index("날짜")

    return df


# ============================================================
# 데이터 로드
# ============================================================

def load_all_data():

    data = {}

    for ticker, path in ETF_FILES.items():
        data[ticker] = load_etf_csv(path, ticker)

    return data


# ============================================================
# 공통 기간 데이터
# ============================================================

def create_price_dataframe(data):

    prices = pd.concat(
        {
            ticker: df["수정주가"]
            for ticker, df in data.items()
        },
        axis=1
    )

    prices = prices.sort_index()

    # 세 ETF 모두 존재하는 날짜만 사용
    prices = prices.dropna()

    return prices


# ============================================================
# MDD 계산
# ============================================================

def calculate_drawdown(series):

    running_max = series.cummax()

    drawdown = (
        series / running_max - 1
    ) * 100

    return drawdown


# ============================================================
# MDD 상세 분석
# ============================================================

def calculate_mdd_details(series):

    running_max = series.cummax()

    drawdown = series / running_max - 1

    mdd_value = drawdown.min()

    mdd_date = drawdown.idxmin()

    peak_date = series.loc[
        :mdd_date
    ].idxmax()

    # 회복일
    peak_value = series.loc[peak_date]

    recovery_data = series.loc[mdd_date:]

    recovery_dates = recovery_data[
        recovery_data >= peak_value
    ]

    if len(recovery_dates) > 0:

        recovery_date = recovery_dates.index[0]

        calendar_days = (
            recovery_date - peak_date
        ).days

        trading_days = (
            series.loc[
                peak_date:recovery_date
            ].shape[0] - 1
        )

    else:

        recovery_date = None
        calendar_days = None
        trading_days = None

    return {
        "MDD": mdd_value * 100,
        "MDD_시작일": peak_date,
        "MDD_저점일": mdd_date,
        "회복일": recovery_date,
        "회복기간": calendar_days,
        "회복기간_거래일": trading_days,
    }


# ============================================================
# ETF 기본 분석
# ============================================================

def analyze_etf(series):

    start_date = series.index.min()
    end_date = series.index.max()

    start_price = series.iloc[0]
    end_price = series.iloc[-1]

    total_return = (
        end_price / start_price - 1
    )

    years = (
        end_date - start_date
    ).days / 365.25

    if years > 0:
        cagr = (
            end_price / start_price
        ) ** (1 / years) - 1
    else:
        cagr = np.nan

    # 일간 수익률
    daily_return = series.pct_change().dropna()

    # 변동성
    volatility = (
        daily_return.std() * np.sqrt(252)
    )

    # 상승일 비율
    win_rate = (
        (daily_return > 0).mean()
    )

    # MDD
    mdd = calculate_mdd_details(series)

    # 1,000만원 투자
    final_value = (
        INITIAL_INVESTMENT
        * end_price
        / start_price
    )

    return {
        "시작일": start_date,
        "종료일": end_date,
        "투자기간_년": years,
        "초기투자금": INITIAL_INVESTMENT,
        "최종금액": final_value,
        "총수익률": total_return * 100,
        "CAGR": cagr * 100,
        "시작가격": start_price,
        "종료가격": end_price,
        "연평균변동성": volatility * 100,
        "승률": win_rate * 100,

        **mdd,
    }


# ============================================================
# 연도별 수익률
# ============================================================

def calculate_yearly_returns(prices):

    yearly = {}

    for ticker in prices.columns:

        series = prices[ticker]

        yearly_price = series.resample("YE").last()

        yearly_return = yearly_price.pct_change() * 100

        # 첫 해는 시작가격 기준
        first_year = series.index[0].year

        first_value = series.iloc[0]

        first_year_end = yearly_price.iloc[0]

        yearly_return.iloc[0] = (
            first_year_end / first_value - 1
        ) * 100

        yearly[ticker] = yearly_return

    result = pd.DataFrame(yearly)

    result.index = result.index.year

    result.index.name = "연도"

    return result


# ============================================================
# 월별 수익률
# ============================================================

def calculate_monthly_returns(prices):

    monthly = {}

    for ticker in prices.columns:

        series = prices[ticker]

        monthly_price = series.resample("ME").last()

        monthly_return = (
            monthly_price.pct_change() * 100
        )

        first_value = series.iloc[0]

        first_month_end = monthly_price.iloc[0]

        monthly_return.iloc[0] = (
            first_month_end / first_value - 1
        ) * 100

        monthly[ticker] = monthly_return

    result = pd.DataFrame(monthly)

    result.index.name = "월"

    return result


# ============================================================
# 누적수익률
# ============================================================

def calculate_cumulative_returns(prices):

    result = prices.copy()

    for ticker in result.columns:

        result[ticker] = (
            result[ticker]
            / result[ticker].iloc[0]
            * 100
        )

    return result


# ============================================================
# Drawdown
# ============================================================

def calculate_all_drawdowns(prices):

    result = pd.DataFrame(index=prices.index)

    for ticker in prices.columns:

        result[ticker] = calculate_drawdown(
            prices[ticker]
        )

    return result


# ============================================================
# 최고 / 최악 연도
# ============================================================

def calculate_best_worst_year(yearly_returns):

    rows = []

    for ticker in yearly_returns.columns:

        series = yearly_returns[ticker].dropna()

        best_year = series.idxmax()
        worst_year = series.idxmin()

        rows.append({
            "ETF": ticker,
            "최고연도": best_year,
            "최고연도수익률": series.max(),
            "최악연도": worst_year,
            "최악연도수익률": series.min(),
        })

    return pd.DataFrame(rows)


# ============================================================
# Excel 스타일
# ============================================================

def style_sheet(ws):

    thin = Side(
        style="thin",
        color="D9D9D9"
    )

    border = Border(
        left=thin,
        right=thin,
        top=thin,
        bottom=thin
    )

    # 헤더
    for cell in ws[1]:

        cell.font = Font(
            bold=True,
            color="FFFFFF"
        )

        cell.fill = PatternFill(
            "solid",
            fgColor="1F4E78"
        )

        cell.alignment = Alignment(
            horizontal="center",
            vertical="center"
        )

        cell.border = border

    # 전체 셀
    for row in ws.iter_rows():

        for cell in row:

            cell.border = border

            cell.alignment = Alignment(
                vertical="center"
            )

    # 컬럼 너비
    for column_cells in ws.columns:

        max_length = 0

        column_letter = get_column_letter(
            column_cells[0].column
        )

        for cell in column_cells:

            if cell.value is not None:

                max_length = max(
                    max_length,
                    len(str(cell.value))
                )

        ws.column_dimensions[
            column_letter
        ].width = min(
            max(max_length + 2, 12),
            30
        )

    ws.freeze_panes = "A2"

    ws.auto_filter.ref = ws.dimensions


# ============================================================
# 숫자 포맷
# ============================================================

def apply_number_formats(ws):

    headers = {
        cell.value: cell.column
        for cell in ws[1]
    }

    percentage_columns = [
        "총수익률",
        "CAGR",
        "연평균변동성",
        "승률",
        "MDD",
    ]

    money_columns = [
        "초기투자금",
        "최종금액",
    ]

    for header in percentage_columns:

        if header in headers:

            col = headers[header]

            for row in range(2, ws.max_row + 1):

                ws.cell(
                    row=row,
                    column=col
                ).number_format = "0.00"

    for header in money_columns:

        if header in headers:

            col = headers[header]

            for row in range(2, ws.max_row + 1):

                ws.cell(
                    row=row,
                    column=col
                ).number_format = "#,##0"


# ============================================================
# Excel 저장
# ============================================================

def save_excel(
    summary,
    yearly_returns,
    monthly_returns,
    cumulative_returns,
    drawdowns,
    best_worst,
    original_data
):

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    print()
    print("=" * 70)
    print("Excel 파일 생성")
    print("=" * 70)

    with pd.ExcelWriter(
        OUTPUT_FILE,
        engine="openpyxl"
    ) as writer:

        # --------------------------------------------
        # 종합비교
        # --------------------------------------------

        summary.to_excel(
            writer,
            sheet_name="종합비교",
            index=False
        )

        # --------------------------------------------
        # 연도별
        # --------------------------------------------

        yearly_returns.to_excel(
            writer,
            sheet_name="연도별수익률"
        )

        # --------------------------------------------
        # 월별
        # --------------------------------------------

        monthly_returns.to_excel(
            writer,
            sheet_name="월별수익률"
        )

        # --------------------------------------------
        # 누적수익률
        # --------------------------------------------

        cumulative_returns.to_excel(
            writer,
            sheet_name="누적수익률"
        )

        # --------------------------------------------
        # Drawdown
        # --------------------------------------------

        drawdowns.to_excel(
            writer,
            sheet_name="Drawdown"
        )

        # --------------------------------------------
        # 최고/최악
        # --------------------------------------------

        best_worst.to_excel(
            writer,
            sheet_name="최고최악연도",
            index=False
        )

        # --------------------------------------------
        # 원본
        # --------------------------------------------

        for ticker, df in original_data.items():

            df.to_excel(
                writer,
                sheet_name=f"원본_{ticker}"
            )

    # ========================================================
    # Excel 후처리
    # ========================================================

    wb = load_workbook(
        OUTPUT_FILE
    )

    # 모든 시트 스타일
    for ws in wb.worksheets:

        style_sheet(ws)

    # 숫자 포맷
    apply_number_formats(
        wb["종합비교"]
    )

    # ========================================================
    # 누적수익률 차트
    # ========================================================

    ws = wb["누적수익률"]

    chart = LineChart()

    chart.title = (
        "SPY vs QQQ vs TQQQ 누적수익률"
    )

    chart.y_axis.title = "지수"
    chart.x_axis.title = "날짜"

    data = Reference(
        ws,
        min_col=2,
        max_col=4,
        min_row=1,
        max_row=ws.max_row
    )

    dates = Reference(
        ws,
        min_col=1,
        min_row=2,
        max_row=ws.max_row
    )

    chart.add_data(
        data,
        titles_from_data=True
    )

    chart.set_categories(dates)

    chart.height = 10
    chart.width = 22

    ws.add_chart(
        chart,
        "F2"
    )

    # ========================================================
    # Drawdown 차트
    # ========================================================

    ws = wb["Drawdown"]

    chart = LineChart()

    chart.title = (
        "SPY vs QQQ vs TQQQ Drawdown"
    )

    chart.y_axis.title = "Drawdown (%)"
    chart.x_axis.title = "날짜"

    data = Reference(
        ws,
        min_col=2,
        max_col=4,
        min_row=1,
        max_row=ws.max_row
    )

    dates = Reference(
        ws,
        min_col=1,
        min_row=2,
        max_row=ws.max_row
    )

    chart.add_data(
        data,
        titles_from_data=True
    )

    chart.set_categories(dates)

    chart.height = 10
    chart.width = 22

    ws.add_chart(
        chart,
        "F2"
    )

    # ========================================================
    # 연도별 수익률 차트
    # ========================================================

    ws = wb["연도별수익률"]

    chart = BarChart()

    chart.title = (
        "SPY / QQQ / TQQQ 연도별 수익률"
    )

    chart.y_axis.title = "수익률 (%)"
    chart.x_axis.title = "연도"

    data = Reference(
        ws,
        min_col=2,
        max_col=4,
        min_row=1,
        max_row=ws.max_row
    )

    categories = Reference(
        ws,
        min_col=1,
        min_row=2,
        max_row=ws.max_row
    )

    chart.add_data(
        data,
        titles_from_data=True
    )

    chart.set_categories(
        categories
    )

    chart.height = 10
    chart.width = 22

    ws.add_chart(
        chart,
        "F2"
    )

    # ========================================================
    # 종합비교 강조
    # ========================================================

    ws = wb["종합비교"]

    for row in range(2, ws.max_row + 1):

        for col in range(1, ws.max_column + 1):

            cell = ws.cell(
                row=row,
                column=col
            )

            if cell.value == "TQQQ":

                cell.font = Font(
                    bold=True
                )

    wb.save(
        OUTPUT_FILE
    )

    print()
    print(f"완료:")
    print(OUTPUT_FILE.resolve())


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("SPY / QQQ / TQQQ 비교 분석")
    print("=" * 70)

    # 1. 데이터 로드
    data = load_all_data()

    # 2. 공통 날짜 기준 가격
    prices = create_price_dataframe(
        data
    )

    if prices.empty:

        raise ValueError(
            "SPY / QQQ / TQQQ의 공통 날짜 데이터가 없습니다."
        )

    print()
    print(
        f"공통 분석기간: "
        f"{prices.index.min().date()} ~ "
        f"{prices.index.max().date()}"
    )

    print(
        f"공통 거래일 수: "
        f"{len(prices):,}"
    )

    # 3. ETF별 분석
    summary_rows = []

    for ticker in prices.columns:

        print(
            f"[분석] {ticker}"
        )

        result = analyze_etf(
            prices[ticker]
        )

        result["ETF"] = ticker

        summary_rows.append(
            result
        )

    summary = pd.DataFrame(
        summary_rows
    )

    # ETF를 첫 번째 컬럼으로
    columns = [
        "ETF",
        "시작일",
        "종료일",
        "투자기간_년",
        "초기투자금",
        "최종금액",
        "총수익률",
        "CAGR",
        "시작가격",
        "종료가격",
        "연평균변동성",
        "승률",
        "MDD",
        "MDD_시작일",
        "MDD_저점일",
        "회복일",
        "회복기간",
        "회복기간_거래일",
    ]

    summary = summary[
        columns
    ]

    # 4. 연도별
    yearly_returns = (
        calculate_yearly_returns(
            prices
        )
    )

    # 5. 월별
    monthly_returns = (
        calculate_monthly_returns(
            prices
        )
    )

    # 6. 누적수익률
    cumulative_returns = (
        calculate_cumulative_returns(
            prices
        )
    )

    # 7. Drawdown
    drawdowns = (
        calculate_all_drawdowns(
            prices
        )
    )

    # 8. 최고/최악 연도
    best_worst = (
        calculate_best_worst_year(
            yearly_returns
        )
    )

    # 9. Excel 저장
    save_excel(
        summary=summary,
        yearly_returns=yearly_returns,
        monthly_returns=monthly_returns,
        cumulative_returns=cumulative_returns,
        drawdowns=drawdowns,
        best_worst=best_worst,
        original_data=data,
    )


# ============================================================
# 실행
# ============================================================

if __name__ == "__main__":
    main()