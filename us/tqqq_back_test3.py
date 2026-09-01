"""
====================================================================
TQQQ 피라미딩 / 분할매수 전략 최적화
====================================================================

전략
--------------------------------------------------------------------
초기자금                 : $1,000
1회 매수금액             : $1,000

매수조건
--------------------------------------------------------------------
최고점 대비 -5%
최고점 대비 -10%
최고점 대비 -15%
...
최고점 대비 -50%

매도조건
--------------------------------------------------------------------
각 매수분별로 독립 관리

매수가 대비

+5%
+10%
+15%
...
+300%

도달 시 해당 매수분만 개별 매도


예
--------------------------------------------------------------------
고점 = $100

매수조건 = -10%

$90  -> $1,000 매수
$80  -> $1,000 매수
$70  -> $1,000 매수

매도조건 = +50%

$90 -> $135
$80 -> $120
$70 -> $105

각각의 매수분이 목표가격에 도달하면 개별 매도.


주의
--------------------------------------------------------------------
모든 계산은 USD

환율 없음
수수료 없음
세금 없음

소수점 주식 매수 허용


출력
--------------------------------------------------------------------
data/us_etf/analysis/TQQQ_parameter_optimization.xlsx


Excel Sheet
--------------------------------------------------------------------
1. 최적조건
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
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.chart import LineChart, Reference
from openpyxl.utils import get_column_letter


# ====================================================================
# 1. 파일 설정
# ====================================================================

INPUT_FILE = Path(
    "us/data/us_etf/analysis/TQQQ_analysis.csv"
)

OUTPUT_DIR = Path(
    "us/data/us_etf/analysis"
)

OUTPUT_FILE = (
    OUTPUT_DIR /
    "TQQQ_parameter_optimization.xlsx"
)


# ====================================================================
# 2. 투자금 설정
# ====================================================================

INITIAL_CAPITAL = 1_000.0

BUY_AMOUNT = 1_000.0


# ====================================================================
# 3. 매수조건
# ====================================================================
#
# 최고점 대비 하락폭
#
# -5%
# -10%
# ...
# -50%
#
# ====================================================================

BUY_DROP_LIST = [

    x / 100

    for x in range(
        5,
        51,
        5
    )

]


# ====================================================================
# 4. 매도조건
# ====================================================================
#
# +5%
# +10%
# ...
# +300%
#
# 5% 간격
#
# 총 60개
#
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
# 5. 데이터 로드
# ====================================================================

def load_data():

    if not INPUT_FILE.exists():

        raise FileNotFoundError(

            "\n파일을 찾을 수 없습니다.\n\n"

            f"{INPUT_FILE.resolve()}\n\n"

            "INPUT_FILE 경로를 확인하세요."

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

            "\n필수 컬럼이 없습니다:\n"

            + "\n".join(missing)

        )

    df["날짜"] = pd.to_datetime(
        df["날짜"],
        errors="coerce"
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

    df = df.sort_values(
        "날짜"
    )

    df = df.drop_duplicates(

        subset=["날짜"],

        keep="last"

    )

    df = df.reset_index(
        drop=True
    )

    return df


# ====================================================================
# 6. 단일 전략 백테스트
# ====================================================================

def run_backtest(

    df,

    buy_drop,

    sell_profit,

):

    cash = INITIAL_CAPITAL

    positions = []

    trades = []

    daily_records = []

    highest_price = None

    highest_date = None

    highest_bought_level = 0

    trade_number = 0

    equity_curve = []


    # =================================================================
    # 날짜별 계산
    # =================================================================

    for i, row in df.iterrows():

        date = row["날짜"]

        high = float(
            row["고가"]
        )

        low = float(
            row["저가"]
        )

        close = float(
            row["종가"]
        )

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
            # 고가가 목표가 이상이면 매도
            # ---------------------------------------------------------

            if high >= target_price:

                sell_price = (
                    target_price
                )

                shares = position[
                    "수량"
                ]

                buy_amount = position[
                    "매수금액"
                ]

                sell_amount = (

                    sell_price
                    * shares

                )

                profit = (

                    sell_amount
                    - buy_amount

                )

                return_pct = (

                    sell_amount
                    / buy_amount
                    - 1

                ) * 100


                holding_days = (

                    date
                    - position["매수일"]

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

                    "매수조건":
                        buy_drop * 100,

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

                    "매수기준고점":
                        position[
                            "매수_고점"
                        ],

                    "매수기준고점일":
                        position[
                            "매수_고점_발생일"
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

                    f"매도 L"
                    f"{position['매수레벨']}"

                )


                positions_to_remove.append(
                    position
                )


        # -------------------------------------------------------------
        # 매도 포지션 제거
        # -------------------------------------------------------------

        for position in positions_to_remove:

            positions.remove(
                position
            )


        # =============================================================
        # 3. 고점 대비 하락률
        # =============================================================

        if highest_price > 0:

            drawdown = (

                low
                / highest_price
                - 1

            )

            max_level = int(

                np.floor(

                    (

                        1
                        - low
                        / highest_price

                    )

                    / buy_drop

                    + 1e-10

                )

            )

        else:

            drawdown = 0.0

            max_level = 0


        max_level = max(

            0,
            max_level

        )


        # =============================================================
        # 4. 신규 분할매수
        # =============================================================

        for level in range(

            highest_bought_level + 1,

            max_level + 1

        ):

            buy_price = (

                highest_price

                * (

                    1
                    - buy_drop
                    * level

                )

            )


            buy_amount = BUY_AMOUNT


            # ---------------------------------------------------------
            # 현금 부족
            # ---------------------------------------------------------

            if cash < buy_amount:

                continue


            # ---------------------------------------------------------
            # 소수점 주식
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

                "매수_고점":
                    highest_price,

                "매수_고점_발생일":
                    highest_date,

                "매수_index":
                    i,

            }


            positions.append(
                position
            )


            highest_bought_level = (
                level
            )


            actions.append(

                f"매수 L{level}"

            )


        # =============================================================
        # 5. 현재 보유자산 계산
        # =============================================================

        position_value = 0.0

        unrealized_profit = 0.0

        total_shares = 0.0

        total_cost = 0.0


        for position in positions:

            shares = position[
                "수량"
            ]

            cost = position[
                "매수금액"
            ]

            value = (

                adjusted_price
                * shares

            )

            position_value += value

            total_cost += cost

            unrealized_profit += (

                value
                - cost

            )

            total_shares += shares


        # =============================================================
        # 6. 총자산
        # =============================================================

        total_asset = (

            cash
            + position_value

        )


        cumulative_return = (

            total_asset
            / INITIAL_CAPITAL
            - 1

        ) * 100


        # =============================================================
        # 7. 평균 매수가
        # =============================================================

        if total_shares > 0:

            avg_buy_price = (

                total_cost
                / total_shares

            )

            avg_return = (

                adjusted_price
                / avg_buy_price
                - 1

            ) * 100

        else:

            avg_buy_price = np.nan

            avg_return = np.nan


        # =============================================================
        # 8. 일별 기록
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

            "전략최고가":
                highest_price,

            "최고가_발생일":
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

            "평균매수가대비수익률":
                avg_return,

            "보유평가금액":
                position_value,

            "미실현손익":
                unrealized_profit,

            "현금":
                cash,

            "총자산":
                total_asset,

            "누적수익률":
                cumulative_return,

        })


        equity_curve.append(
            total_asset
        )


    # =================================================================
    # 9. 마지막 미청산 포지션
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

            last_price
            * shares

        )

        profit = (

            current_value
            - buy_amount

        )

        return_pct = (

            current_value
            / buy_amount
            - 1

        ) * 100


        holding_days = (

            last_date
            - position[
                "매수일"
            ]

        ).days


        holding_trading_days = (

            len(df)
            - 1
            - position[
                "매수_index"
            ]

        )


        trade_number += 1


        trades.append({

            "거래번호":
                trade_number,

            "매수조건":
                buy_drop * 100,

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

            "매수기준고점":
                position[
                    "매수_고점"
                ],

            "매수기준고점일":
                position[
                    "매수_고점_발생일"
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
                holding_days,

            "보유기간_거래일":
                holding_trading_days,

            "상태":
                "미청산",

        })


    # =================================================================
    # 10. 최종자산
    # =================================================================

    final_position_value = sum(

        position[
            "수량"
        ]
        * last_price

        for position in positions

    )


    final_asset = (

        cash
        + final_position_value

    )


    total_profit = (

        final_asset
        - INITIAL_CAPITAL

    )


    total_return = (

        final_asset
        / INITIAL_CAPITAL
        - 1

    ) * 100


    # =================================================================
    # 11. CAGR
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


    if years > 0:

        cagr = (

            (

                final_asset
                / INITIAL_CAPITAL

            )
            ** (1 / years)

            - 1

        ) * 100

    else:

        cagr = np.nan


    # =================================================================
    # 12. MDD
    # =================================================================

    equity = pd.Series(
        equity_curve
    )


    running_max = (
        equity.cummax()
    )


    equity_drawdown = (

        equity
        / running_max
        - 1

    )


    mdd = (

        equity_drawdown.min()
        * 100

    )


    mdd_index = int(

        equity_drawdown.idxmin()

    )


    peak_index = int(

        equity.iloc[
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
    # 13. 거래통계
    # =================================================================

    trades_df = pd.DataFrame(
        trades
    )


    if len(trades_df) > 0:

        completed = trades_df[
            trades_df["상태"]
            == "완료"
        ]

        unclosed = trades_df[
            trades_df["상태"]
            == "미청산"
        ]

    else:

        completed = pd.DataFrame()

        unclosed = pd.DataFrame()


    completed_count = len(
        completed
    )

    unclosed_count = len(
        unclosed
    )


    if completed_count > 0:

        realized_profit = (
            completed[
                "수익금"
            ].sum()
        )

        avg_trade_return = (
            completed[
                "수익률"
            ].mean()
        )

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

    else:

        realized_profit = 0.0

        avg_trade_return = np.nan

        win_rate = np.nan


    if unclosed_count > 0:

        unrealized_profit = (
            unclosed[
                "수익금"
            ].sum()
        )

    else:

        unrealized_profit = 0.0


    max_shares = max(

        x["보유주수"]
        for x in daily_records

    )


    # =================================================================
    # 14. 결과
    # =================================================================

    result = {

        "매수조건":
            buy_drop * 100,

        "매도조건":
            sell_profit * 100,

        "초기자금":
            INITIAL_CAPITAL,

        "1회매수금액":
            BUY_AMOUNT,

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
# 7. 전체 조건 테스트
# ====================================================================

def optimize_parameters(
    df
):

    results = []

    total_tests = (

        len(BUY_DROP_LIST)

        *
        len(SELL_PROFIT_LIST)

    )


    current = 0


    print()

    print("=" * 90)

    print(
        "TQQQ 매수 / 매도 조건 최적화"
    )

    print("=" * 90)

    print()

    print(
        f"매수 조건 : "
        f"{len(BUY_DROP_LIST)}개"
    )

    print(
        f"매도 조건 : "
        f"{len(SELL_PROFIT_LIST)}개"
    )

    print(
        f"총 조합 : "
        f"{total_tests:,}개"
    )

    print()


    for buy_drop in BUY_DROP_LIST:

        for sell_profit in SELL_PROFIT_LIST:

            current += 1


            print(

                f"\r진행률 : "
                f"{current:,} / "
                f"{total_tests:,}",

                end=""

            )


            result, _, _ = run_backtest(

                df,

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
# 8. TOP 결과
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
# 9. 최적 조건 요약
# ====================================================================

def make_best_summary(
    results_df
):

    best_return = (

        results_df

        .loc[
            results_df[
                "총수익률"
            ].idxmax()
        ]

    )


    best_cagr = (

        results_df

        .loc[
            results_df[
                "CAGR"
            ].idxmax()
        ]

    )


    best_mdd = (

        results_df

        .loc[
            results_df[
                "MDD"
            ].idxmax()
        ]

    )


    temp = (
        results_df.copy()
    )


    temp[
        "CAGR_MDD_비율"
    ] = (

        temp["CAGR"]
        / temp["MDD"].abs()

    )


    best_risk = (

        temp

        .loc[
            temp[
                "CAGR_MDD_비율"
            ].idxmax()
        ]

    )


    rows = [

        {

            "기준":
                "최고 총수익률",

            "매수조건":
                best_return[
                    "매수조건"
                ],

            "매도조건":
                best_return[
                    "매도조건"
                ],

            "최종자산":
                best_return[
                    "최종자산"
                ],

            "총수익금":
                best_return[
                    "총수익금"
                ],

            "총수익률":
                best_return[
                    "총수익률"
                ],

            "CAGR":
                best_return[
                    "CAGR"
                ],

            "MDD":
                best_return[
                    "MDD"
                ],

            "완료매도":
                best_return[
                    "완료매도"
                ],

            "미청산포지션":
                best_return[
                    "미청산포지션"
                ],

        },


        {

            "기준":
                "최고 CAGR",

            "매수조건":
                best_cagr[
                    "매수조건"
                ],

            "매도조건":
                best_cagr[
                    "매도조건"
                ],

            "최종자산":
                best_cagr[
                    "최종자산"
                ],

            "총수익금":
                best_cagr[
                    "총수익금"
                ],

            "총수익률":
                best_cagr[
                    "총수익률"
                ],

            "CAGR":
                best_cagr[
                    "CAGR"
                ],

            "MDD":
                best_cagr[
                    "MDD"
                ],

            "완료매도":
                best_cagr[
                    "완료매도"
                ],

            "미청산포지션":
                best_cagr[
                    "미청산포지션"
                ],

        },


        {

            "기준":
                "가장 낮은 MDD",

            "매수조건":
                best_mdd[
                    "매수조건"
                ],

            "매도조건":
                best_mdd[
                    "매도조건"
                ],

            "최종자산":
                best_mdd[
                    "최종자산"
                ],

            "총수익금":
                best_mdd[
                    "총수익금"
                ],

            "총수익률":
                best_mdd[
                    "총수익률"
                ],

            "CAGR":
                best_mdd[
                    "CAGR"
                ],

            "MDD":
                best_mdd[
                    "MDD"
                ],

            "완료매도":
                best_mdd[
                    "완료매도"
                ],

            "미청산포지션":
                best_mdd[
                    "미청산포지션"
                ],

        },


        {

            "기준":
                "CAGR / MDD 최고",

            "매수조건":
                best_risk[
                    "매수조건"
                ],

            "매도조건":
                best_risk[
                    "매도조건"
                ],

            "최종자산":
                best_risk[
                    "최종자산"
                ],

            "총수익금":
                best_risk[
                    "총수익금"
                ],

            "총수익률":
                best_risk[
                    "총수익률"
                ],

            "CAGR":
                best_risk[
                    "CAGR"
                ],

            "MDD":
                best_risk[
                    "MDD"
                ],

            "완료매도":
                best_risk[
                    "완료매도"
                ],

            "미청산포지션":
                best_risk[
                    "미청산포지션"
                ],

        },

    ]


    return pd.DataFrame(
        rows
    )


# ====================================================================
# 10. 히트맵
# ====================================================================

def make_heatmap(
    results_df,
    column
):

    return (

        results_df

        .pivot(

            index="매수조건",

            columns="매도조건",

            values=column

        )

    )


# ====================================================================
# 11. Excel 스타일
# ====================================================================

def style_worksheet(
    ws
):

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

        cell.border = (
            border
        )


    for row in ws.iter_rows():

        for cell in row:

            cell.border = (
                border
            )


    for column_cells in ws.columns:

        max_length = 0

        column_letter = (

            get_column_letter(

                column_cells[
                    0
                ].column

            )

        )


        for cell in column_cells:

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
            column_letter
        ].width = min(

            max(
                max_length + 2,
                12
            ),

            30

        )


    ws.freeze_panes = "A2"


# ====================================================================
# 12. Excel 숫자 포맷
# ====================================================================

def format_excel(
    wb
):

    usd_columns = [

        "초기자금",
        "1회매수금액",
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

    ]


    percent_columns = [

        "매수조건",
        "매도조건",
        "총수익률",
        "CAGR",
        "MDD",
        "승률",
        "평균거래수익률",

    ]


    price_columns = [

        "수정주가",
        "고가",
        "저가",
        "종가",
        "전략최고가",
        "평균매수가",
        "매수기준고점",

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

                    row=row,

                    column=col

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

                    row=row,

                    column=col

                ).number_format = (
                    '0.00"%"'
                )


        for name in price_columns:

            if name not in headers:

                continue

            col = headers[name]


            for row in range(

                2,
                ws.max_row + 1

            ):

                ws.cell(

                    row=row,

                    column=col

                ).number_format = (
                    '$0.0000'
                )


# ====================================================================
# 13. Excel 저장
# ====================================================================

def save_excel(

    df,

    results_df,

    best_summary,

    top_return,

    top_cagr,

    top_mdd,

    best_trades,

    best_daily

):

    OUTPUT_DIR.mkdir(

        parents=True,

        exist_ok=True

    )


    return_heatmap = make_heatmap(

        results_df,

        "총수익률"

    )


    cagr_heatmap = make_heatmap(

        results_df,

        "CAGR"

    )


    mdd_heatmap = make_heatmap(

        results_df,

        "MDD"

    )


    with pd.ExcelWriter(

        OUTPUT_FILE,

        engine="openpyxl"

    ) as writer:

        best_summary.to_excel(

            writer,

            sheet_name="최적조건",

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


        return_heatmap.to_excel(

            writer,

            sheet_name="수익률_히트맵"

        )


        cagr_heatmap.to_excel(

            writer,

            sheet_name="CAGR_히트맵"

        )


        mdd_heatmap.to_excel(

            writer,

            sheet_name="MDD_히트맵"

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


    wb = load_workbook(

        OUTPUT_FILE

    )


    for ws in wb.worksheets:

        style_worksheet(
            ws
        )


    format_excel(
        wb
    )


    # ================================================================
    # 히트맵
    # ================================================================

    for sheet_name in [

        "수익률_히트맵",
        "CAGR_히트맵",
        "MDD_히트맵",

    ]:

        ws = wb[
            sheet_name
        ]


        if (

            ws.max_row >= 2

            and ws.max_column >= 2

        ):

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


    # ================================================================
    # 최적조건 강조
    # ================================================================

    ws = wb[
        "최적조건"
    ]


    fill = PatternFill(

        fill_type="solid",

        fgColor="FFF2CC"

    )


    for row in ws.iter_rows():

        for cell in row:

            cell.fill = fill

            cell.font = Font(
                bold=True
            )


    # ================================================================
    # 총자산 차트
    # ================================================================

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

            "최고 총수익률 조건 - 총자산"

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

            max_row=ws.max_row,

        )


        categories = Reference(

            ws,

            min_col=headers[
                "날짜"
            ],

            min_row=2,

            max_row=ws.max_row,

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

            "U2"

        )


    wb.save(
        OUTPUT_FILE
    )


# ====================================================================
# 14. Main
# ====================================================================

def main():

    print()

    print("=" * 90)

    print(
        "TQQQ 피라미딩 / 분할매수 최적화"
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
        "소수점 매수    : YES"
    )


    print()


    print(
        "매수 조건"
    )


    print(

        " / ".join(

            f"-{x:.0%}"

            for x in BUY_DROP_LIST

        )

    )


    print()


    print(
        "매도 조건"
    )


    print(

        f"+5% ~ +300% "
        f"(5% 간격, "
        f"{len(SELL_PROFIT_LIST)}개)"

    )


    print()


    # =================================================================
    # 데이터
    # =================================================================

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


    # =================================================================
    # 최적화
    # =================================================================

    results_df = optimize_parameters(
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
    # 최적조건
    # =================================================================

    best_summary = make_best_summary(

        results_df

    )


    # =================================================================
    # 최고 총수익률 조건
    # =================================================================

    best_row = (

        results_df

        .sort_values(

            "총수익률",

            ascending=False

        )

        .iloc[0]

    )


    best_buy_drop = (

        best_row[
            "매수조건"
        ]
        / 100

    )


    best_sell_profit = (

        best_row[
            "매도조건"
        ]
        / 100

    )


    (

        _,

        best_trades,

        best_daily

    ) = run_backtest(

        df,

        best_buy_drop,

        best_sell_profit,

    )


    # =================================================================
    # Excel
    # =================================================================

    save_excel(

        df,

        results_df,

        best_summary,

        top_return,

        top_cagr,

        top_mdd,

        best_trades,

        best_daily,

    )


    # =================================================================
    # 결과
    # =================================================================

    print()

    print("=" * 90)

    print(
        "최적화 완료"
    )

    print("=" * 90)

    print()


    print(
        "★ 최고 총수익률"
    )


    print(

        f"매수조건 : "
        f"-{best_row['매수조건']:.0f}%"

    )


    print(

        f"매도조건 : "
        f"+{best_row['매도조건']:.0f}%"

    )


    print(

        f"최종자산 : "
        f"${best_row['최종자산']:,.2f}"

    )


    print(

        f"총수익금 : "
        f"${best_row['총수익금']:,.2f}"

    )


    print(

        f"총수익률 : "
        f"{best_row['총수익률']:.2f}%"

    )


    print(

        f"CAGR : "
        f"{best_row['CAGR']:.2f}%"

    )


    print(

        f"MDD : "
        f"{best_row['MDD']:.2f}%"

    )


    print(

        f"완료매도 : "
        f"{int(best_row['완료매도'])}"

    )


    print(

        f"미청산 : "
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

        [

            [

                "매수조건",
                "매도조건",
                "최종자산",
                "총수익금",
                "총수익률",
                "CAGR",
                "MDD",
                "완료매도",
                "미청산포지션",

            ]

        ]

        .to_string(
            index=False
        )

    )


    print()

    print("=" * 90)

    print(
        "Excel 저장"
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