"""
============================================================
TQQQ 10% 하락 매수 → 2배 상승 매도 전략 백테스트
============================================================

입력 파일
------------------------------------------------------------
data/us_etf/TQQQ_analysis.csv

전략
------------------------------------------------------------
1. 초기 투자금: 10,000,000원

2. 현재까지의 최고 수정주가를 추적

3. 현재 수정주가가 최고가 대비 10% 이상 하락하면 매수

   예:
       최고가 = 100
       매수 기준 = 90

4. 매수 후 매수가의 2배가 되면 매도

   예:
       매수가 = 90
       목표가 = 180

5. 매도 후 다시 최고가를 추적

6. 다시 최고가 대비 -10%가 되면 매수

7. 한 번에 하나의 포지션만 보유

8. 마지막 날짜까지 매도되지 않은 포지션은
   미청산으로 처리

출력
------------------------------------------------------------
data/us_etf/analysis/TQQQ_10pct_buy_2x_sell.xlsx

Excel 시트
------------------------------------------------------------
1. 요약
2. 거래내역
3. 일별전략
4. 자산추이
5. 원본데이터
============================================================
"""

from pathlib import Path

import pandas as pd
import numpy as np

from openpyxl import load_workbook
from openpyxl.styles import (
    Font,
    PatternFill,
    Alignment,
    Border,
    Side,
)
from openpyxl.chart import LineChart, Reference
from openpyxl.utils import get_column_letter


# ============================================================
# 사용자 설정
# ============================================================

INPUT_FILE = Path(
    "us/data/us_etf/analysis/TQQQ_analysis.csv"
)

OUTPUT_DIR = Path(
    "data/us_etf/analysis"
)

OUTPUT_FILE = (
    OUTPUT_DIR /
    "TQQQ_10pct_buy_2x_sell.xlsx"
)

# 초기 투자금
INITIAL_CAPITAL = 10_000_000

# 최고가 대비 하락률
BUY_DROP = 0.10

# 매수가 대비 목표 배수
SELL_MULTIPLE = 2.0


# ============================================================
# 데이터 로드
# ============================================================

def load_data():

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"\n입력 파일을 찾을 수 없습니다.\n"
            f"{INPUT_FILE.resolve()}"
        )

    print()
    print("=" * 70)
    print("TQQQ 데이터 로드")
    print("=" * 70)

    df = pd.read_csv(INPUT_FILE)

    required_columns = [
        "날짜",
        "수정주가",
        "고가",
        "저가",
        "종가",
    ]

    for col in required_columns:

        if col not in df.columns:

            raise ValueError(
                f"필수 컬럼이 없습니다: {col}"
            )

    # 날짜
    df["날짜"] = pd.to_datetime(
        df["날짜"]
    )

    # 숫자형 변환
    numeric_columns = [
        "수정주가",
        "고가",
        "저가",
        "종가",
    ]

    for col in numeric_columns:

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    # 결측 제거
    df = df.dropna(
        subset=[
            "날짜",
            "수정주가",
        ]
    )

    # 날짜 정렬
    df = df.sort_values(
        "날짜"
    )

    # 중복 제거
    df = df.drop_duplicates(
        subset=["날짜"],
        keep="last"
    )

    df = df.reset_index(
        drop=True
    )

    print(
        f"분석기간: "
        f"{df['날짜'].iloc[0].date()} ~ "
        f"{df['날짜'].iloc[-1].date()}"
    )

    print(
        f"거래일수: "
        f"{len(df):,}"
    )

    return df


# ============================================================
# 백테스트
# ============================================================

def run_backtest(df):

    print()
    print("=" * 70)
    print("전략 백테스트")
    print("=" * 70)

    # --------------------------------------------------------
    # 상태 변수
    # --------------------------------------------------------

    cash = float(INITIAL_CAPITAL)

    shares = 0.0

    position = False

    buy_date = None
    buy_price = None
    target_price = None

    trade_number = 0

    trades = []

    daily_records = []

    # --------------------------------------------------------
    # 전략 최고가
    #
    # 포지션이 없을 때만 최고가를 갱신
    # --------------------------------------------------------

    running_high = None
    running_high_date = None

    # --------------------------------------------------------
    # 날짜별 반복
    # --------------------------------------------------------

    for i, row in df.iterrows():

        date = row["날짜"]
        price = float(row["수정주가"])

        # ====================================================
        # 포지션이 없는 경우
        # ====================================================

        if not position:

            # --------------------------------------------
            # 최고가 갱신
            # --------------------------------------------

            if (
                running_high is None
                or price > running_high
            ):

                running_high = price

                running_high_date = date

            # --------------------------------------------
            # 고점 대비 하락률
            # --------------------------------------------

            drawdown_from_high = (
                price / running_high - 1
            )

            # --------------------------------------------
            # 매수 조건
            # --------------------------------------------

            if (
                drawdown_from_high
                <= -BUY_DROP
            ):

                # ----------------------------------------
                # 전액 매수
                # ----------------------------------------

                buy_price = price

                target_price = (
                    buy_price
                    * SELL_MULTIPLE
                )

                shares = (
                    cash / buy_price
                )

                position = True

                buy_date = date

                trade_number += 1

                print(
                    f"[매수 {trade_number}] "
                    f"{date.date()} | "
                    f"가격={buy_price:.4f} | "
                    f"수량={shares:.4f} | "
                    f"목표={target_price:.4f} | "
                    f"고점={running_high:.4f} | "
                    f"하락률={drawdown_from_high:.2%}"
                )

                daily_action = "매수"

            else:

                daily_action = "대기"

        # ====================================================
        # 포지션 보유 중
        # ====================================================

        else:

            # --------------------------------------------
            # 매수 가격 대비 수익률
            # --------------------------------------------

            position_return = (
                price / buy_price - 1
            )

            # --------------------------------------------
            # 목표가 도달 여부
            #
            # 수정주가 기준
            # --------------------------------------------

            if price >= target_price:

                sell_date = date

                sell_price = price

                proceeds = (
                    shares
                    * sell_price
                )

                cost = (
                    shares
                    * buy_price
                )

                profit = (
                    proceeds
                    - cost
                )

                trade_return = (
                    sell_price
                    / buy_price
                    - 1
                )

                holding_days = (
                    sell_date
                    - buy_date
                ).days

                trading_days = (
                    df.loc[
                        (df["날짜"] >= buy_date)
                        &
                        (df["날짜"] <= sell_date)
                    ].shape[0]
                    - 1
                )

                # 현금화
                cash = proceeds

                trades.append({

                    "거래번호":
                        trade_number,

                    "매수일":
                        buy_date,

                    "매수가":
                        buy_price,

                    "매도목표가":
                        target_price,

                    "매도일":
                        sell_date,

                    "매도가":
                        sell_price,

                    "보유기간":
                        holding_days,

                    "보유기간_거래일":
                        trading_days,

                    "수량":
                        shares,

                    "투자금":
                        cost,

                    "매도금액":
                        proceeds,

                    "수익금":
                        profit,

                    "수익률":
                        trade_return * 100,

                    "상태":
                        "완료",
                })

                print(
                    f"[매도 {trade_number}] "
                    f"{date.date()} | "
                    f"가격={sell_price:.4f} | "
                    f"수익률={trade_return:.2%} | "
                    f"수익금={profit:,.0f}원"
                )

                # ----------------------------------------
                # 포지션 초기화
                # ----------------------------------------

                position = False

                buy_date = None
                buy_price = None
                target_price = None
                shares = 0.0

                # ----------------------------------------
                # 중요:
                # 매도 후 해당 가격부터 새로운 고점 추적
                # ----------------------------------------

                running_high = price
                running_high_date = date

                daily_action = "매도"

            else:

                daily_action = "보유"

        # ====================================================
        # 날짜별 기록
        # ====================================================

        # 고점 대비 하락률
        if running_high is not None:

            high_drawdown = (
                price / running_high - 1
            ) * 100

        else:

            high_drawdown = 0.0

        # 매수가 대비 수익률
        if position and buy_price:

            buy_return = (
                price / buy_price - 1
            ) * 100

            current_target = target_price

        else:

            buy_return = None
            current_target = None

        # 평가금액
        if position:

            market_value = (
                shares * price
            )

            total_asset = (
                cash
                - shares * buy_price
                + market_value
            )

            # 전액 투자 구조에서는 사실상 market_value
            total_asset = market_value

        else:

            market_value = 0.0

            total_asset = cash

        # 누적 수익률
        cumulative_return = (
            total_asset
            / INITIAL_CAPITAL
            - 1
        ) * 100

        daily_records.append({

            "날짜":
                date,

            "수정주가":
                price,

            "전략고점":
                running_high,

            "전략고점_발생일":
                running_high_date,

            "고점대비하락률":
                high_drawdown,

            "매매상태":
                daily_action,

            "보유수량":
                shares,

            "매수가":
                buy_price,

            "매도목표가":
                current_target,

            "매수가대비수익률":
                buy_return,

            "평가금액":
                market_value,

            "현금":
                cash
                if not position
                else 0.0,

            "총자산":
                total_asset,

            "누적수익률":
                cumulative_return,

            "거래번호":
                trade_number
                if position
                else None,
        })

    # ========================================================
    # 마지막 날짜 미청산 포지션
    # ========================================================

    if position:

        last_row = df.iloc[-1]

        last_date = last_row["날짜"]

        last_price = float(
            last_row["수정주가"]
        )

        market_value = (
            shares
            * last_price
        )

        unrealized_profit = (
            last_price
            / buy_price
            - 1
        )

        holding_days = (
            last_date
            - buy_date
        ).days

        trading_days = (
            df.loc[
                df["날짜"] >= buy_date
            ].shape[0]
            - 1
        )

        trades.append({

            "거래번호":
                trade_number,

            "매수일":
                buy_date,

            "매수가":
                buy_price,

            "매도목표가":
                target_price,

            "매도일":
                None,

            "매도가":
                None,

            "보유기간":
                holding_days,

            "보유기간_거래일":
                trading_days,

            "수량":
                shares,

            "투자금":
                shares * buy_price,

            "매도금액":
                None,

            "수익금":
                shares
                * (
                    last_price
                    - buy_price
                ),

            "수익률":
                unrealized_profit * 100,

            "상태":
                "미청산",
        })

        print()
        print(
            f"[미청산] "
            f"매수일={buy_date.date()} | "
            f"매수가={buy_price:.4f} | "
            f"현재가={last_price:.4f} | "
            f"수익률={unrealized_profit:.2%}"
        )

    # ========================================================
    # DataFrame
    # ========================================================

    daily_df = pd.DataFrame(
        daily_records
    )

    trades_df = pd.DataFrame(
        trades
    )

    return daily_df, trades_df


# ============================================================
# 요약 계산
# ============================================================

def create_summary(
    df,
    daily_df,
    trades_df
):

    start_date = df["날짜"].iloc[0]
    end_date = df["날짜"].iloc[-1]

    years = (
        end_date - start_date
    ).days / 365.25

    final_asset = (
        daily_df["총자산"].iloc[-1]
    )

    total_profit = (
        final_asset
        - INITIAL_CAPITAL
    )

    total_return = (
        final_asset
        / INITIAL_CAPITAL
        - 1
    )

    if years > 0:

        cagr = (
            final_asset
            / INITIAL_CAPITAL
        ) ** (1 / years) - 1

    else:

        cagr = np.nan

    # --------------------------------------------------------
    # 전략 자산 MDD
    # --------------------------------------------------------

    asset = daily_df["총자산"]

    running_max = asset.cummax()

    drawdown = (
        asset / running_max - 1
    )

    strategy_mdd = (
        drawdown.min()
        * 100
    )

    # --------------------------------------------------------
    # 완료 거래
    # --------------------------------------------------------

    completed = trades_df[
        trades_df["상태"] == "완료"
    ]

    unclosed = trades_df[
        trades_df["상태"] == "미청산"
    ]

    completed_count = len(
        completed
    )

    unclosed_count = len(
        unclosed
    )

    # --------------------------------------------------------
    # 거래 수익
    # --------------------------------------------------------

    if completed_count > 0:

        avg_trade_return = (
            completed["수익률"]
            .mean()
        )

        max_trade_return = (
            completed["수익률"]
            .max()
        )

        min_trade_return = (
            completed["수익률"]
            .min()
        )

        avg_holding_days = (
            completed["보유기간"]
            .mean()
        )

        total_realized_profit = (
            completed["수익금"]
            .sum()
        )

    else:

        avg_trade_return = np.nan
        max_trade_return = np.nan
        min_trade_return = np.nan
        avg_holding_days = np.nan
        total_realized_profit = 0

    # --------------------------------------------------------
    # 요약
    # --------------------------------------------------------

    summary = pd.DataFrame({

        "항목": [

            "분석 시작일",
            "분석 종료일",
            "투자기간(년)",

            "초기 투자금",
            "최종 자산",
            "총 수익금",
            "총 수익률",
            "CAGR",

            "매수 조건",
            "매도 조건",

            "총 거래 횟수",
            "완료 거래",
            "미청산 거래",

            "평균 거래 수익률",
            "최고 거래 수익률",
            "최저 거래 수익률",

            "평균 보유기간(일)",

            "실현 수익금",
            "전략 MDD",
        ],

        "값": [

            start_date,
            end_date,
            years,

            INITIAL_CAPITAL,
            final_asset,
            total_profit,
            total_return * 100,
            cagr * 100,

            f"고점 대비 -{BUY_DROP:.0%}",
            f"매수가 × {SELL_MULTIPLE:.1f}",

            len(trades_df),
            completed_count,
            unclosed_count,

            avg_trade_return,
            max_trade_return,
            min_trade_return,

            avg_holding_days,

            total_realized_profit,
            strategy_mdd,
        ]
    })

    return summary


# ============================================================
# Excel 스타일
# ============================================================

def style_worksheet(ws):

    header_fill = PatternFill(
        fill_type="solid",
        fgColor="1F4E78"
    )

    header_font = Font(
        bold=True,
        color="FFFFFF"
    )

    thin = Side(
        style="thin",
        color="D9D9D9"
    )

    border = Border(
        left=thin,
        right=thin,
        top=thin,
        bottom=thin,
    )

    # 헤더
    for cell in ws[1]:

        cell.fill = header_fill
        cell.font = header_font

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

        column_letter = (
            get_column_letter(
                column_cells[0].column
            )
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
# Excel 숫자 포맷
# ============================================================

def format_excel_numbers(wb):

    # --------------------------------------------------------
    # 요약
    # --------------------------------------------------------

    ws = wb["요약"]

    for row in range(
        2,
        ws.max_row + 1
    ):

        label = ws.cell(
            row=row,
            column=1
        ).value

        value_cell = ws.cell(
            row=row,
            column=2
        )

        if label in [
            "초기 투자금",
            "최종 자산",
            "총 수익금",
            "실현 수익금",
        ]:

            value_cell.number_format = (
                '#,##0"원"'
            )

        elif label in [
            "총 수익률",
            "CAGR",
            "평균 거래 수익률",
            "최고 거래 수익률",
            "최저 거래 수익률",
            "전략 MDD",
        ]:

            value_cell.number_format = (
                '0.00"%"'
            )

    # --------------------------------------------------------
    # 거래내역
    # --------------------------------------------------------

    ws = wb["거래내역"]

    headers = {
        cell.value: cell.column
        for cell in ws[1]
    }

    for col_name in [
        "매수가",
        "매도목표가",
        "매도가",
    ]:

        if col_name in headers:

            col = headers[col_name]

            for row in range(
                2,
                ws.max_row + 1
            ):

                ws.cell(
                    row=row,
                    column=col
                ).number_format = "0.0000"

    for col_name in [
        "투자금",
        "매도금액",
        "수익금",
    ]:

        if col_name in headers:

            col = headers[col_name]

            for row in range(
                2,
                ws.max_row + 1
            ):

                ws.cell(
                    row=row,
                    column=col
                ).number_format = (
                    '#,##0"원"'
                )

    if "수익률" in headers:

        col = headers["수익률"]

        for row in range(
            2,
            ws.max_row + 1
        ):

            ws.cell(
                row=row,
                column=col
            ).number_format = '0.00"%"'

    # --------------------------------------------------------
    # 일별전략
    # --------------------------------------------------------

    ws = wb["일별전략"]

    headers = {
        cell.value: cell.column
        for cell in ws[1]
    }

    for col_name in [
        "수정주가",
        "전략고점",
        "매수가",
        "매도목표가",
    ]:

        if col_name in headers:

            col = headers[col_name]

            for row in range(
                2,
                ws.max_row + 1
            ):

                ws.cell(
                    row=row,
                    column=col
                ).number_format = "0.0000"

    for col_name in [
        "고점대비하락률",
        "매수가대비수익률",
        "누적수익률",
    ]:

        if col_name in headers:

            col = headers[col_name]

            for row in range(
                2,
                ws.max_row + 1
            ):

                ws.cell(
                    row=row,
                    column=col
                ).number_format = '0.00"%"'

    for col_name in [
        "평가금액",
        "현금",
        "총자산",
    ]:

        if col_name in headers:

            col = headers[col_name]

            for row in range(
                2,
                ws.max_row + 1
            ):

                ws.cell(
                    row=row,
                    column=col
                ).number_format = (
                    '#,##0"원"'
                )


# ============================================================
# Excel 생성
# ============================================================

def save_excel(
    original_df,
    summary_df,
    trades_df,
    daily_df,
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

        # ----------------------------------------------------
        # 요약
        # ----------------------------------------------------

        summary_df.to_excel(
            writer,
            sheet_name="요약",
            index=False
        )

        # ----------------------------------------------------
        # 거래내역
        # ----------------------------------------------------

        trades_df.to_excel(
            writer,
            sheet_name="거래내역",
            index=False
        )

        # ----------------------------------------------------
        # 일별 전략
        # ----------------------------------------------------

        daily_df.to_excel(
            writer,
            sheet_name="일별전략",
            index=False
        )

        # ----------------------------------------------------
        # 자산추이
        # ----------------------------------------------------

        asset_df = daily_df[
            [
                "날짜",
                "수정주가",
                "총자산",
                "누적수익률",
                "매매상태",
            ]
        ].copy()

        asset_df.to_excel(
            writer,
            sheet_name="자산추이",
            index=False
        )

        # ----------------------------------------------------
        # 원본 데이터
        # ----------------------------------------------------

        original_df.to_excel(
            writer,
            sheet_name="원본데이터",
            index=False
        )

    # ========================================================
    # OpenPyXL 후처리
    # ========================================================

    wb = load_workbook(
        OUTPUT_FILE
    )

    # 모든 시트 스타일
    for ws in wb.worksheets:

        style_worksheet(ws)

    # 숫자 포맷
    format_excel_numbers(
        wb
    )

    # ========================================================
    # 자산추이 차트
    # ========================================================

    ws = wb["자산추이"]

    chart = LineChart()

    chart.title = (
        "TQQQ 10% 하락 매수 → 2배 매도 전략"
    )

    chart.y_axis.title = "자산"
    chart.x_axis.title = "날짜"

    data = Reference(
        ws,
        min_col=3,
        max_col=3,
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
        "G2"
    )

    # ========================================================
    # 매매상태 색상
    # ========================================================

    ws = wb["일별전략"]

    headers = {
        cell.value: cell.column
        for cell in ws[1]
    }

    status_col = headers.get(
        "매매상태"
    )

    if status_col:

        for row in range(
            2,
            ws.max_row + 1
        ):

            cell = ws.cell(
                row=row,
                column=status_col
            )

            if cell.value == "매수":

                cell.fill = PatternFill(
                    "solid",
                    fgColor="C6EFCE"
                )

                cell.font = Font(
                    bold=True
                )

            elif cell.value == "매도":

                cell.fill = PatternFill(
                    "solid",
                    fgColor="FFC7CE"
                )

                cell.font = Font(
                    bold=True
                )

            elif cell.value == "보유":

                cell.fill = PatternFill(
                    "solid",
                    fgColor="FFF2CC"
                )

    # ========================================================
    # 거래내역 완료 / 미청산 색상
    # ========================================================

    ws = wb["거래내역"]

    headers = {
        cell.value: cell.column
        for cell in ws[1]
    }

    status_col = headers.get(
        "상태"
    )

    if status_col:

        for row in range(
            2,
            ws.max_row + 1
        ):

            cell = ws.cell(
                row=row,
                column=status_col
            )

            if cell.value == "완료":

                cell.fill = PatternFill(
                    "solid",
                    fgColor="C6EFCE"
                )

            elif cell.value == "미청산":

                cell.fill = PatternFill(
                    "solid",
                    fgColor="FFF2CC"
                )

    # ========================================================
    # 저장
    # ========================================================

    wb.save(
        OUTPUT_FILE
    )

    print()
    print("Excel 생성 완료")
    print(
        f"파일: {OUTPUT_FILE.resolve()}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("TQQQ 전략 백테스트")
    print("=" * 70)

    print()
    print(
        f"초기 투자금 : "
        f"{INITIAL_CAPITAL:,.0f}원"
    )

    print(
        f"매수 조건   : "
        f"고점 대비 -{BUY_DROP:.0%}"
    )

    print(
        f"매도 조건   : "
        f"매수가 × {SELL_MULTIPLE:.1f}"
    )

    # --------------------------------------------------------
    # 1. 데이터 로드
    # --------------------------------------------------------

    df = load_data()

    # --------------------------------------------------------
    # 2. 백테스트
    # --------------------------------------------------------

    daily_df, trades_df = (
        run_backtest(df)
    )

    # --------------------------------------------------------
    # 3. 요약
    # --------------------------------------------------------

    summary_df = create_summary(
        df,
        daily_df,
        trades_df
    )

    # --------------------------------------------------------
    # 4. 결과 출력
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("백테스트 결과")
    print("=" * 70)

    for _, row in summary_df.iterrows():

        print(
            f"{row['항목']:25s} : "
            f"{row['값']}"
        )

    # --------------------------------------------------------
    # 5. Excel 저장
    # --------------------------------------------------------

    save_excel(
        original_df=df,
        summary_df=summary_df,
        trades_df=trades_df,
        daily_df=daily_df,
    )

    print()
    print("=" * 70)
    print("모든 작업 완료")
    print("=" * 70)


# ============================================================
# 실행
# ============================================================

if __name__ == "__main__":

    main()

