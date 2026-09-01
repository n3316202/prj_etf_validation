"""
====================================================================
TQQQ 무한 분할매수 / 피라미딩 전략 최적화
====================================================================

[입력]
data/us_etf/TQQQ_analysis.csv

[가격]
고가 / 저가 / 종가 / 수정주가 사용

====================================================================
전략
====================================================================

① 고정 5% 무한매수
   고점 대비 -5%마다 계속 매수

   예:
   고점 100

   95  -> 매수
   90  -> 매수
   85  -> 매수
   80  -> 매수
   ...

② 고정 10% 무한매수

   90
   80
   70
   60
   ...

③ 고정 20% 무한매수

   80
   60
   40
   20
   ...

④ 일반 개별 하락률 전략

   -5%
   -10%
   -15%
   ...
   -50%

====================================================================
매수
====================================================================

1회 매수금액 = $1,000

자금 제한 없음

즉, 매수할 때마다 $1,000 추가 투입

====================================================================
매도
====================================================================

각 매수분을 독립적으로 관리

+5%
+10%
+15%
...
+300%

중 하나에 도달하면 개별 매도

====================================================================
매도 가격
====================================================================

고가가 목표가를 터치하면

목표가격에 매도했다고 가정

====================================================================
중요
====================================================================

무한매수이므로

초기자금 $1,000
+
추가 투입금

을 별도로 기록한다.

따라서 단순히 "최종자산 / $1,000"으로 수익률을 계산하면
잘못된 결과가 된다.

실제 투자성과는

총투입금 대비 최종자산

으로 계산한다.

====================================================================
Excel 출력
====================================================================

TQQQ_infinite_buy_optimization.xlsx

Sheet
--------------------------------
1. 전략요약
2. 전체결과
3. TOP_수익률
4. TOP_CAGR
5. TOP_MDD
6. 수익률_히트맵
7. CAGR_히트맵
8. MDD_히트맵
9. 거래내역_TOP1
10. 일별전략_TOP1
11. 원본데이터

====================================================================
"""

from pathlib import Path

import numpy as np
import pandas as pd

from openpyxl import load_workbook
from openpyxl.styles import (
    Font,
    PatternFill,
    Alignment,
    Border,
    Side,
)
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.chart import LineChart, Reference
from openpyxl.utils import get_column_letter


# ====================================================================
# 1. 설정
# ====================================================================

INPUT_FILE = Path(
    "us/data/us_etf/analysis/TQQQ_analysis.csv"
)

OUTPUT_DIR = Path(
    "us/data/us_etf/analysis"
)


OUTPUT_FILE = (
    OUTPUT_DIR
    / "TQQQ_infinite_buy_optimization.xlsx"
)


# ====================================================================
# 2. 투자 설정
# ====================================================================

INITIAL_CAPITAL = 1_000.0

BUY_AMOUNT = 1_000.0


# ====================================================================
# 3. 매수 전략
# ====================================================================

BUY_INTERVALS = {

    "5%_무한매수": 0.05,
    "10%_무한매수": 0.10,
    "20%_무한매수": 0.20,

}


# ====================================================================
# 4. 일반 개별 매수조건
# ====================================================================

INDIVIDUAL_BUY_CONDITIONS = [

    x / 100

    for x in range(
        5,
        51,
        5
    )

]


# ====================================================================
# 5. 매도 조건
# ====================================================================

SELL_PROFIT_LIST = [

    x / 100

    for x in range(
        5,
        301,
        5
    )

]


# ====================================================================
# 6. 데이터 로드
# ====================================================================

def load_data():

    if not INPUT_FILE.exists():

        raise FileNotFoundError(

            f"\n파일을 찾을 수 없습니다.\n"
            f"{INPUT_FILE.resolve()}\n"

        )

    df = pd.read_csv(
        INPUT_FILE
    )

    required_columns = [

        "날짜",
        "수정주가",
        "고가",
        "저가",
        "종가",

    ]

    missing = [

        col

        for col in required_columns

        if col not in df.columns

    ]

    if missing:

        raise ValueError(

            "필수 컬럼이 없습니다:\n"
            + "\n".join(missing)

        )

    df["날짜"] = pd.to_datetime(
        df["날짜"]
    )

    for col in [

        "수정주가",
        "고가",
        "저가",
        "종가",

    ]:

        df[col] = pd.to_numeric(

            df[col],

            errors="coerce"

        )

    df = df.dropna(

        subset=required_columns

    )

    df = (

        df
        .sort_values("날짜")
        .drop_duplicates(
            "날짜"
        )
        .reset_index(drop=True)

    )

    return df


# ====================================================================
# 7. 백테스트
# ====================================================================

def run_backtest(

    df,
    strategy_name,
    buy_interval,
    sell_profit,

):

    positions = []

    trades = []

    daily_records = []


    # ---------------------------------------------------------------
    # 최고점
    # ---------------------------------------------------------------

    highest_price = None

    highest_date = None


    # ---------------------------------------------------------------
    # 마지막으로 매수한 레벨
    # ---------------------------------------------------------------

    highest_bought_level = 0


    # ---------------------------------------------------------------
    # 누적 투자금
    # ---------------------------------------------------------------

    cumulative_investment = (
        INITIAL_CAPITAL
    )


    # ---------------------------------------------------------------
    # 초기 현금
    # ---------------------------------------------------------------

    cash = INITIAL_CAPITAL


    # ---------------------------------------------------------------
    # Equity
    # ---------------------------------------------------------------

    equity_curve = []


    trade_number = 0


    # =================================================================
    # 날짜별 계산
    # =================================================================

    for i, row in df.iterrows():

        date = row["날짜"]

        high = float(row["고가"])

        low = float(row["저가"])

        close = float(row["종가"])

        adjusted_price = float(
            row["수정주가"]
        )

        actions = []


        # =============================================================
        # 1. 최고점 갱신
        # =============================================================

        if (

            highest_price is None

            or high > highest_price

        ):

            highest_price = high

            highest_date = date

            highest_bought_level = 0


        # =============================================================
        # 2. 기존 포지션 매도
        # =============================================================

        positions_to_remove = []


        for position in positions:

            buy_price = position[
                "매수가"
            ]

            target_price = (

                buy_price
                * (
                    1
                    + sell_profit
                )

            )


            # ---------------------------------------------------------
            # 목표가격 도달
            # ---------------------------------------------------------

            if high >= target_price:

                sell_price = target_price

                shares = position[
                    "수량"
                ]

                buy_amount = position[
                    "매수금액"
                ]

                sell_amount = (

                    shares
                    * sell_price

                )

                profit = (

                    sell_amount
                    - buy_amount

                )

                return_pct = (

                    profit
                    / buy_amount

                ) * 100


                holding_days = (

                    date
                    - position[
                        "매수일"
                    ]

                ).days


                holding_trading_days = (

                    i
                    - position[
                        "매수_index"
                    ]

                )


                cash += sell_amount


                trade_number += 1


                trades.append({

                    "거래번호":
                        trade_number,

                    "전략":
                        strategy_name,

                    "매수간격":
                        buy_interval * 100,

                    "매도조건":
                        sell_profit * 100,

                    "매수레벨":
                        position[
                            "매수레벨"
                        ],

                    "매수일":
                        position[
                            "매수일"
                        ],

                    "매수가":
                        buy_price,

                    "매수금액":
                        buy_amount,

                    "매수주수":
                        shares,

                    "매수时高点":
                        position[
                            "매수기준고점"
                        ],

                    "매수기준고점일":
                        position[
                            "매수기준고점일"
                        ],

                    "매도목표가":
                        target_price,

                    "매도일":
                        date,

                    "매도가":
                        sell_price,

                    "매도금액":
                        sell_amount,

                    "수익금":
                        profit,

                    "수익률":
                        return_pct,

                    "보유기간":
                        holding_days,

                    "보유기간_거래일":
                        holding_trading_days,

                    "상태":
                        "완료",

                })


                actions.append(

                    f"매도 L{position['매수레벨']}"

                )


                positions_to_remove.append(
                    position
                )


        for position in positions_to_remove:

            positions.remove(
                position
            )


        # =============================================================
        # 3. 고점 대비 하락률
        # =============================================================

        drawdown = (

            low
            / highest_price
            - 1

        )


        # =============================================================
        # 4. 매수 가능한 단계 계산
        # =============================================================

        if highest_price > 0:

            max_level = int(

                np.floor(

                    (

                        1
                        - low
                        / highest_price

                    )
                    / buy_interval

                    + 1e-10

                )

            )

        else:

            max_level = 0


        # =============================================================
        # 5. 무한 분할매수
        # =============================================================

        for level in range(

            highest_bought_level + 1,

            max_level + 1

        ):

            buy_price = (

                highest_price

                * (

                    1
                    - buy_interval
                    * level

                )

            )


            if buy_price <= 0:

                break


            # ---------------------------------------------------------
            # 매수금액
            # ---------------------------------------------------------

            buy_amount = BUY_AMOUNT


            # ---------------------------------------------------------
            # 현금 부족하면 추가자금 투입
            # ---------------------------------------------------------

            if cash < buy_amount:

                additional_cash = (

                    buy_amount
                    - cash

                )

                cumulative_investment += (
                    additional_cash
                )

                cash += additional_cash


            # ---------------------------------------------------------
            # 주식 수
            # ---------------------------------------------------------

            shares = (

                buy_amount
                / buy_price

            )


            cash -= buy_amount


            position = {

                "매수일":
                    date,

                "매수가":
                    buy_price,

                "수량":
                    shares,

                "매수금액":
                    buy_amount,

                "매수레벨":
                    level,

                "매수기준고점":
                    highest_price,

                "매수기준고점일":
                    highest_date,

                "매수_index":
                    i,

            }


            positions.append(
                position
            )


            highest_bought_level = level


            actions.append(

                f"매수 L{level}"

            )


        # =============================================================
        # 6. 보유자산
        # =============================================================

        position_value = 0.0

        total_shares = 0.0

        total_cost = 0.0


        for position in positions:

            shares = position[
                "수량"
            ]

            cost = position[
                "매수금액"
            ]

            position_value += (

                shares
                * adjusted_price

            )

            total_shares += shares

            total_cost += cost


        # =============================================================
        # 7. 총자산
        # =============================================================

        total_asset = (

            cash
            + position_value

        )


        # =============================================================
        # 8. 총투입금 대비 수익률
        # =============================================================

        total_return = (

            total_asset
            / cumulative_investment
            - 1

        ) * 100


        # =============================================================
        # 9. 평균매수가
        # =============================================================

        if total_shares > 0:

            avg_buy_price = (

                total_cost
                / total_shares

            )

            unrealized_return = (

                adjusted_price
                / avg_buy_price
                - 1

            ) * 100

        else:

            avg_buy_price = np.nan

            unrealized_return = np.nan


        # =============================================================
        # 10. 일별 기록
        # =============================================================

        daily_records.append({

            "날짜":
                date,

            "수정주가":
                adjusted_price,

            "고가":
                high,

            "저가":
                low,

            "종가":
                close,

            "전략":
                strategy_name,

            "매수간격":
                buy_interval * 100,

            "매도조건":
                sell_profit * 100,

            "전략최고가":
                highest_price,

            "최고가발생일":
                highest_date,

            "고점대비하락률":
                drawdown * 100,

            "매매":
                " / ".join(actions),

            "보유주수":
                total_shares,

            "보유포지션수":
                len(positions),

            "평균매수가":
                avg_buy_price,

            "보유평가금액":
                position_value,

            "현금":
                cash,

            "누적투입금":
                cumulative_investment,

            "총자산":
                total_asset,

            "수익금":
                total_asset
                - cumulative_investment,

            "수익률":
                total_return,

        })


        equity_curve.append(
            total_asset
        )


    # =================================================================
    # 마지막 미청산 포지션
    # =================================================================

    last_date = df[
        "날짜"
    ].iloc[-1]

    last_price = float(

        df[
            "수정주가"
        ].iloc[-1]

    )


    for position in positions:

        buy_price = position[
            "매수가"
        ]

        shares = position[
            "수량"
        ]

        buy_amount = position[
            "매수금액"
        ]

        current_value = (

            shares
            * last_price

        )

        profit = (

            current_value
            - buy_amount

        )

        return_pct = (

            profit
            / buy_amount

        ) * 100


        trade_number += 1


        trades.append({

            "거래번호":
                trade_number,

            "전략":
                strategy_name,

            "매수간격":
                buy_interval * 100,

            "매도조건":
                sell_profit * 100,

            "매수레벨":
                position[
                    "매수레벨"
                ],

            "매수일":
                position[
                    "매수일"
                ],

            "매수가":
                buy_price,

            "매수금액":
                buy_amount,

            "매수주수":
                shares,

            "매수时高点":
                position[
                    "매수기준고점"
                ],

            "매수기준고점일":
                position[
                    "매수기준고점일"
                ],

            "매도목표가":
                buy_price
                * (
                    1
                    + sell_profit
                ),

            "매도일":
                None,

            "매도가":
                None,

            "매도금액":
                None,

            "수익금":
                profit,

            "수익률":
                return_pct,

            "보유기간":
                (

                    last_date
                    - position[
                        "매수일"
                    ]

                ).days,

            "보유기간_거래일":
                (

                    len(df)
                    - 1
                    - position[
                        "매수_index"
                    ]

                ),

            "상태":
                "미청산",

        })


    # =================================================================
    # 최종자산
    # =================================================================

    final_position_value = sum(

        p["수량"]
        * last_price

        for p in positions

    )


    final_asset = (

        cash
        + final_position_value

    )


    total_profit = (

        final_asset
        - cumulative_investment

    )


    total_return = (

        final_asset
        / cumulative_investment
        - 1

    ) * 100


    # =================================================================
    # CAGR
    # =================================================================

    start_date = df[
        "날짜"
    ].iloc[0]

    end_date = df[
        "날짜"
    ].iloc[-1]


    years = (

        end_date
        - start_date

    ).days / 365.25


    if (

        years > 0
        and cumulative_investment > 0

    ):

        cagr = (

            (

                final_asset
                / cumulative_investment

            )
            ** (1 / years)

            - 1

        ) * 100

    else:

        cagr = np.nan


    # =================================================================
    # MDD
    # =================================================================

    equity = pd.Series(
        equity_curve
    )


    running_max = (
        equity.cummax()
    )


    drawdown_series = (

        equity
        / running_max
        - 1

    )


    mdd = (

        drawdown_series.min()
        * 100

    )


    mdd_index = int(

        drawdown_series.idxmin()

    )


    peak_index = int(

        equity[
            :mdd_index + 1
        ].idxmax()

    )


    mdd_start_date = df.loc[
        peak_index,
        "날짜"
    ]


    mdd_low_date = df.loc[
        mdd_index,
        "날짜"
    ]


    peak_value = equity.loc[
        peak_index
    ]


    recovery_date = None


    for idx in range(

        mdd_index,
        len(equity)

    ):

        if (

            equity.iloc[idx]
            >= peak_value

        ):

            recovery_date = df.loc[
                idx,
                "날짜"
            ]

            break


    if recovery_date is not None:

        recovery_days = (

            recovery_date
            - mdd_start_date

        ).days

        recovery_trading_days = (

            df.index[
                df["날짜"]
                == recovery_date
            ][0]

            - peak_index

        )

    else:

        recovery_days = np.nan

        recovery_trading_days = np.nan


    # =================================================================
    # 거래통계
    # =================================================================

    trades_df = pd.DataFrame(
        trades
    )


    completed = (

        trades_df[
            trades_df["상태"]
            == "완료"
        ]

        if len(trades_df)
        else pd.DataFrame()

    )


    unclosed = (

        trades_df[
            trades_df["상태"]
            == "미청산"
        ]

        if len(trades_df)
        else pd.DataFrame()

    )


    completed_count = len(
        completed
    )

    unclosed_count = len(
        unclosed
    )


    if completed_count > 0:

        win_count = len(

            completed[
                completed[
                    "수익금"
                ] > 0
            ]

        )

        win_rate = (

            win_count
            / completed_count
            * 100

        )

        avg_trade_return = (

            completed[
                "수익률"
            ].mean()

        )

        realized_profit = (

            completed[
                "수익금"
            ].sum()

        )

    else:

        win_rate = np.nan

        avg_trade_return = np.nan

        realized_profit = 0


    if unclosed_count > 0:

        unrealized_profit = (

            unclosed[
                "수익금"
            ].sum()

        )

    else:

        unrealized_profit = 0


    max_position_count = max(

        x[
            "보유포지션수"
        ]

        for x in daily_records

    )


    max_shares = max(

        x[
            "보유주수"
        ]

        for x in daily_records

    )


    # =================================================================
    # 결과
    # =================================================================

    result = {

        "전략":
            strategy_name,

        "매수간격":
            buy_interval * 100,

        "매도조건":
            sell_profit * 100,

        "초기자금":
            INITIAL_CAPITAL,

        "1회매수금액":
            BUY_AMOUNT,

        "누적투입금":
            cumulative_investment,

        "최종자산":
            final_asset,

        "총수익금":
            total_profit,

        "총수익률":
            total_return,

        "CAGR":
            cagr,

        "MDD":
            mdd,

        "MDD_시작일":
            mdd_start_date,

        "MDD_저점일":
            mdd_low_date,

        "MDD_회복일":
            recovery_date,

        "MDD회복기간":
            recovery_days,

        "MDD회복기간_거래일":
            recovery_trading_days,

        "총거래기록":
            len(trades_df),

        "완료매도":
            completed_count,

        "미청산포지션":
            unclosed_count,

        "승률":
            win_rate,

        "평균거래수익률":
            avg_trade_return,

        "실현수익":
            realized_profit,

        "미실현수익":
            unrealized_profit,

        "최대보유포지션":
            max_position_count,

        "최대보유주수":
            max_shares,

    }


    return (

        result,
        trades_df,
        pd.DataFrame(
            daily_records
        )

    )


# ====================================================================
# 8. 전체 테스트
# ====================================================================

def run_all_tests(df):

    results = []

    total = (

        (
            len(BUY_INTERVALS)
            + len(INDIVIDUAL_BUY_CONDITIONS)
        )
        *
        len(SELL_PROFIT_LIST)

    )


    count = 0


    print()

    print("=" * 90)

    print(
        "TQQQ 매수 / 매도 조건 전체 테스트"
    )

    print("=" * 90)

    print()

    print(
        f"총 테스트 : {total:,}개"
    )

    print()


    # =================================================================
    # A. 무한매수 전략
    # =================================================================

    for strategy_name, interval in (
        BUY_INTERVALS.items()
    ):

        for sell_profit in SELL_PROFIT_LIST:

            count += 1


            print(

                f"\r진행률 : "
                f"{count:,}/{total:,}",

                end=""

            )


            result, _, _ = run_backtest(

                df,

                strategy_name,

                interval,

                sell_profit,

            )


            results.append(
                result
            )


    # =================================================================
    # B. 일반 개별 하락률 전략
    # =================================================================

    for buy_drop in INDIVIDUAL_BUY_CONDITIONS:

        strategy_name = (

            f"고점대비_"
            f"-{buy_drop * 100:.0f}%"

        )


        for sell_profit in SELL_PROFIT_LIST:

            count += 1


            print(

                f"\r진행률 : "
                f"{count:,}/{total:,}",

                end=""

            )


            result, _, _ = run_backtest(

                df,

                strategy_name,

                buy_drop,

                sell_profit,

            )


            results.append(
                result
            )


    print()

    print()


    return pd.DataFrame(
        results
    )


# ====================================================================
# 9. TOP 결과
# ====================================================================

def make_top_tables(
    results_df
):

    top_return = (

        results_df

        .sort_values(
            "총수익률",
            ascending=False
        )

        .head(30)

        .copy()

    )


    top_cagr = (

        results_df

        .sort_values(
            "CAGR",
            ascending=False
        )

        .head(30)

        .copy()

    )


    top_mdd = (

        results_df

        .sort_values(
            "MDD",
            ascending=False
        )

        .head(30)

        .copy()

    )


    return (

        top_return,
        top_cagr,
        top_mdd

    )


# ====================================================================
# 10. 전략별 최고 결과
# ====================================================================

def make_strategy_summary(
    results_df
):

    rows = []


    for strategy in (
        results_df["전략"].unique()
    ):

        temp = results_df[
            results_df["전략"]
            == strategy
        ]


        best = temp.loc[
            temp[
                "총수익률"
            ].idxmax()
        ]


        rows.append({

            "전략":
                strategy,

            "최고수익률_매도조건":
                best[
                    "매도조건"
                ],

            "최종자산":
                best[
                    "최종자산"
                ],

            "누적투입금":
                best[
                    "누적투입금"
                ],

            "총수익금":
                best[
                    "총수익금"
                ],

            "총수익률":
                best[
                    "총수익률"
                ],

            "CAGR":
                best[
                    "CAGR"
                ],

            "MDD":
                best[
                    "MDD"
                ],

            "완료매도":
                best[
                    "완료매도"
                ],

            "미청산포지션":
                best[
                    "미청산포지션"
                ],

        })


    return pd.DataFrame(
        rows
    )


# ====================================================================
# 11. 히트맵
# ====================================================================

def make_heatmap(
    results_df,
    strategy,
    column
):

    temp = results_df[
        results_df["전략"]
        == strategy
    ]


    return (

        temp

        .pivot(

            index="매수간격",

            columns="매도조건",

            values=column

        )

    )


# ====================================================================
# 12. Excel 스타일
# ====================================================================

def style_sheet(ws):

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
        bottom=thin

    )


    for cell in ws[1]:

        cell.fill = (
            header_fill
        )

        cell.font = (
            header_font
        )

        cell.alignment = Alignment(

            horizontal="center",
            vertical="center"

        )


    for row in ws.iter_rows():

        for cell in row:

            cell.border = border


    for col_cells in ws.columns:

        max_length = 0

        col_letter = (
            get_column_letter(
                col_cells[0].column
            )
        )


        for cell in col_cells:

            if cell.value is not None:

                max_length = max(

                    max_length,

                    len(
                        str(
                            cell.value
                        )
                    )

                )


        ws.column_dimensions[
            col_letter
        ].width = min(

            max(
                max_length + 2,
                12
            ),

            30

        )


    ws.freeze_panes = "A2"


# ====================================================================
# 13. Excel 숫자 포맷
# ====================================================================

def format_excel(wb):

    usd_columns = [

        "초기자금",
        "1회매수금액",
        "누적투입금",
        "최종자산",
        "총수익금",
        "실현수익",
        "미실현수익",
        "매수가",
        "매수금액",
        "매도목표가",
        "매도가",
        "매도금액",
        "수익금",
        "수정주가",
        "고가",
        "저가",
        "종가",
        "전략최고가",
        "평균매수가",
        "보유평가금액",
        "현금",
        "총자산",

    ]


    percent_columns = [

        "매수간격",
        "매도조건",
        "총수익률",
        "CAGR",
        "MDD",
        "승률",
        "평균거래수익률",
        "고점대비하락률",

    ]


    for ws in wb.worksheets:

        headers = {

            cell.value:
                cell.column

            for cell in ws[1]

        }


        for name in usd_columns:

            if name not in headers:

                continue


            col = headers[name]


            for row in range(
                2,
                ws.max_row + 1
            ):

                ws.cell(
                    row,
                    col
                ).number_format = (
                    '$#,##0.00'
                )


        for name in percent_columns:

            if name not in headers:

                continue


            col = headers[name]


            for row in range(
                2,
                ws.max_row + 1
            ):

                ws.cell(
                    row,
                    col
                ).number_format = (
                    '0.00"%"'
                )


# ====================================================================
# 14. Excel 저장
# ====================================================================

def save_excel(

    df,
    results_df,
    strategy_summary,
    top_return,
    top_cagr,
    top_mdd,
    best_trades,
    best_daily,

):

    OUTPUT_DIR.mkdir(

        parents=True,

        exist_ok=True

    )


    # ---------------------------------------------------------------
    # 히트맵
    # ---------------------------------------------------------------

    heatmap_5 = make_heatmap(

        results_df,
        "5%_무한매수",
        "총수익률"

    )


    heatmap_10 = make_heatmap(

        results_df,
        "10%_무한매수",
        "총수익률"

    )


    heatmap_20 = make_heatmap(

        results_df,
        "20%_무한매수",
        "총수익률"

    )


    # ---------------------------------------------------------------
    # 저장
    # ---------------------------------------------------------------

    with pd.ExcelWriter(

        OUTPUT_FILE,

        engine="openpyxl"

    ) as writer:

        strategy_summary.to_excel(

            writer,
            sheet_name="전략요약",
            index=False

        )


        results_df.to_excel(

            writer,
            sheet_name="전체결과",
            index=False

        )


        top_return.to_excel(

            writer,
            sheet_name="TOP_수익률",
            index=False

        )


        top_cagr.to_excel(

            writer,
            sheet_name="TOP_CAGR",
            index=False

        )


        top_mdd.to_excel(

            writer,
            sheet_name="TOP_MDD",
            index=False

        )


        heatmap_5.to_excel(

            writer,
            sheet_name="5%_히트맵"

        )


        heatmap_10.to_excel(

            writer,
            sheet_name="10%_히트맵"

        )


        heatmap_20.to_excel(

            writer,
            sheet_name="20%_히트맵"

        )


        best_trades.to_excel(

            writer,
            sheet_name="거래내역_TOP1",
            index=False

        )


        best_daily.to_excel(

            writer,
            sheet_name="일별전략_TOP1",
            index=False

        )


        df.to_excel(

            writer,
            sheet_name="원본데이터",
            index=False

        )


    # ---------------------------------------------------------------
    # Workbook
    # ---------------------------------------------------------------

    wb = load_workbook(
        OUTPUT_FILE
    )


    for ws in wb.worksheets:

        style_sheet(ws)


    format_excel(wb)


    # ---------------------------------------------------------------
    # 히트맵 색상
    # ---------------------------------------------------------------

    for sheet_name in [

        "5%_히트맵",
        "10%_히트맵",
        "20%_히트맵",

    ]:

        ws = wb[
            sheet_name
        ]


        if ws.max_row >= 2:

            end_col = (
                get_column_letter(
                    ws.max_column
                )
            )


            ws.conditional_formatting.add(

                f"B2:{end_col}{ws.max_row}",

                ColorScaleRule(

                    start_type="min",

                    start_color="F8696B",

                    mid_type="percentile",

                    mid_value=50,

                    mid_color="FFEB84",

                    end_type="max",

                    end_color="63BE7B",

                )

            )


    # ---------------------------------------------------------------
    # TOP1 총자산 차트
    # ---------------------------------------------------------------

    ws = wb[
        "일별전략_TOP1"
    ]


    headers = {

        cell.value:
            cell.column

        for cell in ws[1]

    }


    if "총자산" in headers:

        chart = LineChart()


        chart.title = (
            "TOP1 전략 총자산"
        )


        chart.y_axis.title = (
            "USD"
        )


        chart.x_axis.title = (
            "Date"
        )


        data = Reference(

            ws,

            min_col=headers[
                "총자산"
            ],

            max_col=headers[
                "총자산"
            ],

            min_row=1,

            max_row=ws.max_row

        )


        categories = Reference(

            ws,

            min_col=headers[
                "날짜"
            ],

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

            "X2"

        )


    wb.save(
        OUTPUT_FILE
    )


# ====================================================================
# 15. Main
# ====================================================================

def main():

    print()

    print("=" * 90)

    print(
        "TQQQ 무한 분할매수 전략 최적화"
    )

    print("=" * 90)

    print()


    print(
        f"초기자금       : "
        f"${INITIAL_CAPITAL:,.2f}"
    )


    print(
        f"1회 매수금액   : "
        f"${BUY_AMOUNT:,.2f}"
    )


    print(
        "추가자금        : 무한"
    )


    print(
        "매도조건        : +5% ~ +300%"
    )


    print()


    df = load_data()


    print(

        f"분석기간 : "
        f"{df['날짜'].iloc[0].date()} "
        f"~ "
        f"{df['날짜'].iloc[-1].date()}"

    )


    print(

        f"거래일수 : "
        f"{len(df):,}"

    )


    print()


    # =================================================================
    # 전체 테스트
    # =================================================================

    results_df = run_all_tests(
        df
    )


    # =================================================================
    # TOP
    # =================================================================

    (

        top_return,
        top_cagr,
        top_mdd

    ) = make_top_tables(
        results_df
    )


    # =================================================================
    # 전략 요약
    # =================================================================

    strategy_summary = (
        make_strategy_summary(
            results_df
        )
    )


    # =================================================================
    # 최고 수익률 전략
    # =================================================================

    best_row = (

        results_df

        .sort_values(

            "총수익률",

            ascending=False

        )

        .iloc[0]

    )


    best_interval = (

        best_row[
            "매수간격"
        ]
        / 100

    )


    best_sell = (

        best_row[
            "매도조건"
        ]
        / 100

    )


    best_strategy = best_row[
        "전략"
    ]


    _, best_trades, best_daily = (
        run_backtest(

            df,

            best_strategy,

            best_interval,

            best_sell,

        )
    )


    # =================================================================
    # Excel
    # =================================================================

    save_excel(

        df,

        results_df,

        strategy_summary,

        top_return,

        top_cagr,

        top_mdd,

        best_trades,

        best_daily,

    )


    # =================================================================
    # 출력
    # =================================================================

    print()

    print("=" * 90)

    print(
        "★ 최고 총수익률 전략"
    )

    print("=" * 90)

    print()


    print(
        f"전략       : "
        f"{best_strategy}"
    )


    print(
        f"매수간격   : "
        f"{best_row['매수간격']:.0f}%"
    )


    print(
        f"매도조건   : "
        f"+{best_row['매도조건']:.0f}%"
    )


    print(
        f"누적투입금 : "
        f"${best_row['누적투입금']:,.2f}"
    )


    print(
        f"최종자산   : "
        f"${best_row['최종자산']:,.2f}"
    )


    print(
        f"총수익금   : "
        f"${best_row['총수익금']:,.2f}"
    )


    print(
        f"총수익률   : "
        f"{best_row['총수익률']:.2f}%"
    )


    print(
        f"CAGR       : "
        f"{best_row['CAGR']:.2f}%"
    )


    print(
        f"MDD        : "
        f"{best_row['MDD']:.2f}%"
    )


    print(
        f"완료매도   : "
        f"{int(best_row['완료매도'])}"
    )


    print(
        f"미청산     : "
        f"{int(best_row['미청산포지션'])}"
    )


    print()


    print("=" * 90)

    print(
        "수익률 TOP 20"
    )

    print("=" * 90)


    print(

        results_df

        .sort_values(

            "총수익률",

            ascending=False

        )

        .head(20)

        [[

            "전략",
            "매수간격",
            "매도조건",
            "누적투입금",
            "최종자산",
            "총수익금",
            "총수익률",
            "CAGR",
            "MDD",
            "완료매도",
            "미청산포지션",

        ]]

        .to_string(
            index=False
        )

    )


    print()

    print("=" * 90)

    print(
        "Excel 저장 완료"
    )

    print("=" * 90)

    print()

    print(
        OUTPUT_FILE.resolve()
    )


# ====================================================================
# 실행
# ====================================================================

if __name__ == "__main__":

    main()