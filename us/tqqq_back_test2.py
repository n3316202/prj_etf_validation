"""
====================================================================
TQQQ Pyramid / Split Buy Backtest
====================================================================

전략
--------------------------------------------------------------------
초기자금
    $10,000

매수
    누적 최고점 대비 -10%마다 1주

예:
    최고점 $100

    -10% -> $90  -> 1주 매수
    -20% -> $80  -> 1주 매수
    -30% -> $70  -> 1주 매수
    -40% -> $60  -> 1주 매수

매도
    각각의 매수가 대비 +10%가 되면 해당 포지션 1주 매도

예:
    $90 매수 -> $99 매도
    $80 매수 -> $88 매도
    $70 매수 -> $77 매도

중요
--------------------------------------------------------------------
모든 금액은 USD 기준입니다.

환율 사용 안 함
원화 사용 안 함

초기자금:
    $10,000

가격:
    TQQQ USD 가격

수수료:
    0

세금:
    0


가격 사용 기준
--------------------------------------------------------------------
최고점 계산:
    고가

매수 조건:
    저가

매수 체결가격:
    고점 대비 정확한 -10% 가격

매도 조건:
    고가

매도 체결가격:
    매수가 대비 정확한 +10% 가격

미청산 포지션 평가:
    수정주가


입력파일
--------------------------------------------------------------------
data/us_etf/TQQQ_analysis.csv


필수 컬럼
--------------------------------------------------------------------
날짜
수정주가
고가
저가
종가


출력파일
--------------------------------------------------------------------
data/us_etf/analysis/TQQQ_pyramid_USD_10pct.xlsx


Excel Sheet
--------------------------------------------------------------------
1. 요약
2. 거래내역
3. 일별전략
4. 보유포지션
5. 자산추이
6. 원본데이터


주의
--------------------------------------------------------------------
OHLC 데이터만으로 하루 중 실제 가격 순서를 알 수 없습니다.

예를 들어 하루에

고가 = $100
저가 = $80

이라면

$80 -> $100

인지

$100 -> $80

인지 알 수 없습니다.

따라서 본 백테스트에서는 다음 순서로 처리합니다.

1. 기존 포지션 매도
2. 새로운 매수

즉 같은 날 매수와 매도 조건이 동시에 발생할 경우
기존 포지션의 매도를 먼저 처리합니다.


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
from openpyxl.chart import LineChart, Reference
from openpyxl.utils import get_column_letter


# ====================================================================
# 사용자 설정
# ====================================================================

INPUT_FILE = Path(
    "us/data/us_etf/analysis/TQQQ_analysis.csv"
)

OUTPUT_DIR = Path(
    "us/data/us_etf/analysis"
)

OUTPUT_FILE = (
    OUTPUT_DIR /
    "TQQQ_pyramid_USD_10pct.xlsx"
)


# ====================================================================
# 전략 설정
# ====================================================================

# 초기 투자금 USD
INITIAL_CAPITAL = 10_000.0

# 고점 대비 매수 간격
BUY_STEP = 0.10

# 개별 매도 수익률
SELL_PROFIT = 0.10

# 매수 수량
BUY_SHARES = 1


# ====================================================================
# 데이터 로드
# ====================================================================

def load_data():

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            "\n입력 파일을 찾을 수 없습니다.\n"
            f"{INPUT_FILE.resolve()}"
        )

    print()
    print("=" * 90)
    print("TQQQ 데이터 로드")
    print("=" * 90)

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

    missing_columns = [
        col
        for col in required_columns
        if col not in df.columns
    ]

    if missing_columns:

        raise ValueError(
            "다음 필수 컬럼이 없습니다:\n"
            + "\n".join(
                missing_columns
            )
        )

    # ---------------------------------------------------------------
    # 날짜
    # ---------------------------------------------------------------

    df["날짜"] = pd.to_datetime(
        df["날짜"],
        errors="coerce"
    )

    # ---------------------------------------------------------------
    # 숫자
    # ---------------------------------------------------------------

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

    # ---------------------------------------------------------------
    # 결측 제거
    # ---------------------------------------------------------------

    df = df.dropna(
        subset=required_columns
    )

    # ---------------------------------------------------------------
    # 날짜 정렬
    # ---------------------------------------------------------------

    df = df.sort_values(
        "날짜"
    )

    # ---------------------------------------------------------------
    # 중복 날짜 제거
    # ---------------------------------------------------------------

    df = df.drop_duplicates(
        subset=["날짜"],
        keep="last"
    )

    df = df.reset_index(
        drop=True
    )

    if df.empty:

        raise ValueError(
            "분석할 데이터가 없습니다."
        )

    print(
        f"분석 시작일 : "
        f"{df['날짜'].iloc[0].date()}"
    )

    print(
        f"분석 종료일 : "
        f"{df['날짜'].iloc[-1].date()}"
    )

    print(
        f"거래일수    : "
        f"{len(df):,}"
    )

    print()

    return df


# ====================================================================
# 매수 가격 계산
# ====================================================================

def calculate_buy_price(
    highest_price,
    level
):
    """
    최고점에서 level * 10% 하락한 가격

    level = 1
        최고점 × 0.90

    level = 2
        최고점 × 0.80

    level = 3
        최고점 × 0.70

    """

    return (
        highest_price
        * (
            1
            - BUY_STEP * level
        )
    )


# ====================================================================
# 매도 가격 계산
# ====================================================================

def calculate_sell_price(
    buy_price
):
    """
    매수가 대비 +10%
    """

    return (
        buy_price
        * (
            1
            + SELL_PROFIT
        )
    )


# ====================================================================
# 백테스트
# ====================================================================

def run_backtest(
    df
):

    print()
    print("=" * 90)
    print("TQQQ 피라미딩 백테스트 시작")
    print("=" * 90)

    print(
        f"초기자금       : ${INITIAL_CAPITAL:,.2f}"
    )

    print(
        f"매수 조건       : "
        f"고점 대비 -{BUY_STEP:.0%}마다"
    )

    print(
        f"매수 수량       : "
        f"{BUY_SHARES}주"
    )

    print(
        f"매도 조건       : "
        f"매수가 대비 +{SELL_PROFIT:.0%}"
    )

    print(
        "환율            : 사용 안 함"
    )

    print(
        "수수료          : $0"
    )

    # =================================================================
    # 계좌
    # =================================================================

    cash = INITIAL_CAPITAL

    # 현재 보유 포지션
    positions = []

    # 완료/미청산 거래
    trades = []

    # 일별 결과
    daily_records = []

    # 거래번호
    trade_number = 0

    # =================================================================
    # 전략 최고점
    # =================================================================

    highest_price = None

    highest_date = None

    # 현재 최고점 기준으로
    # 이미 매수한 가장 깊은 레벨

    highest_bought_level = 0

    # =================================================================
    # 일별 반복
    # =================================================================

    for i, row in df.iterrows():

        date = row["날짜"]

        adjusted_price = float(
            row["수정주가"]
        )

        high = float(
            row["고가"]
        )

        low = float(
            row["저가"]
        )

        close = float(
            row["종가"]
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

            # ---------------------------------------------------------
            # 새로운 최고점 발생
            #
            # 새로운 고점이 생기면
            # 새로운 고점 기준의 매수 레벨을 다시 시작
            # ---------------------------------------------------------

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
                calculate_sell_price(
                    buy_price
                )
            )

            # ---------------------------------------------------------
            # 당일 고가가 목표가격 이상이면 매도
            # ---------------------------------------------------------

            if high >= target_price:

                sell_price = target_price

                shares = position[
                    "수량"
                ]

                buy_amount = (
                    buy_price
                    * shares
                )

                sell_amount = (
                    sell_price
                    * shares
                )

                profit = (
                    sell_amount
                    - buy_amount
                )

                return_pct = (
                    sell_price
                    / buy_price
                    - 1
                ) * 100

                calendar_days = (
                    date
                    - position["매수일"]
                ).days

                trading_days = (
                    i
                    - position["매수_index"]
                )

                # -----------------------------------------------------
                # 현금 증가
                # -----------------------------------------------------

                cash += sell_amount

                trade_number += 1

                # -----------------------------------------------------
                # 거래 기록
                # -----------------------------------------------------

                trades.append({

                    "거래번호":
                        trade_number,

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

                    "매수_고점":
                        position[
                            "매수_고점"
                        ],

                    "매수_고점_발생일":
                        position[
                            "매수_고점_발생일"
                        ],

                    "매수_하락률":
                        position[
                            "매수_하락률"
                        ],

                    "매도목표가":
                        target_price,

                    "매도일":
                        date,

                    "매도가":
                        sell_price,

                    "수량":
                        shares,

                    "매수금액":
                        buy_amount,

                    "매도금액":
                        sell_amount,

                    "수익금":
                        profit,

                    "수익률":
                        return_pct,

                    "보유기간":
                        calendar_days,

                    "보유기간_거래일":
                        trading_days,

                    "상태":
                        "완료",
                })

                actions.append(
                    f"매도 L{position['매수레벨']}"
                )

                positions_to_remove.append(
                    position
                )

                print(
                    f"[매도] "
                    f"{date.date()} | "
                    f"L{position['매수레벨']} | "
                    f"${buy_price:.4f}"
                    f" -> "
                    f"${sell_price:.4f} | "
                    f"+${profit:.4f}"
                )

        # -------------------------------------------------------------
        # 포지션 제거
        # -------------------------------------------------------------

        for position in positions_to_remove:

            positions.remove(
                position
            )

        # =============================================================
        # 3. 새로운 매수 레벨 계산
        # =============================================================

        if highest_price > 0:

            drawdown = (
                low
                / highest_price
                - 1
            )

            # ---------------------------------------------------------
            # 몇 번째 10% 하락 레벨까지 도달했는가
            # ---------------------------------------------------------

            max_level = int(
                np.floor(
                    (
                        1
                        - low / highest_price
                    )
                    / BUY_STEP
                    + 1e-12
                )
            )

        else:

            drawdown = 0

            max_level = 0

        max_level = max(
            0,
            max_level
        )

        # =============================================================
        # 4. 매수
        # =============================================================

        for level in range(
            highest_bought_level + 1,
            max_level + 1
        ):

            buy_price = (
                calculate_buy_price(
                    highest_price,
                    level
                )
            )

            buy_amount = (
                buy_price
                * BUY_SHARES
            )

            # ---------------------------------------------------------
            # 현금 부족
            # ---------------------------------------------------------

            if cash < buy_amount:

                print(
                    f"[매수불가] "
                    f"{date.date()} | "
                    f"L{level} | "
                    f"필요=${buy_amount:.2f} | "
                    f"현금=${cash:.2f}"
                )

                continue

            # ---------------------------------------------------------
            # 매수
            # ---------------------------------------------------------

            cash -= buy_amount

            position = {

                "매수일":
                    date,

                "매수가":
                    buy_price,

                "수량":
                    BUY_SHARES,

                "매수_고점":
                    highest_price,

                "매수_고점_발생일":
                    highest_date,

                "매수_하락률":
                    (
                        buy_price
                        / highest_price
                        - 1
                    ) * 100,

                "매수레벨":
                    level,

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

            print(
                f"[매수] "
                f"{date.date()} | "
                f"L{level} | "
                f"고점=${highest_price:.4f} | "
                f"매수가=${buy_price:.4f} | "
                f"현금=${cash:.2f}"
            )

        # =============================================================
        # 5. 현재 포지션 평가
        # =============================================================

        position_value = 0.0

        unrealized_profit = 0.0

        total_shares = 0

        for position in positions:

            shares = position[
                "수량"
            ]

            market_value = (
                shares
                * adjusted_price
            )

            cost = (
                shares
                * position["매수가"]
            )

            position_value += (
                market_value
            )

            unrealized_profit += (
                market_value
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

        if positions:

            total_cost = sum(
                p["매수가"]
                * p["수량"]
                for p in positions
            )

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
        # 8. 다음 매수 가격
        # =============================================================

        next_level = (
            highest_bought_level
            + 1
        )

        next_buy_price = (
            calculate_buy_price(
                highest_price,
                next_level
            )
        )

        next_buy_drawdown = (
            next_buy_price
            / highest_price
            - 1
        ) * 100

        # =============================================================
        # 9. 매매 기록
        # =============================================================

        if actions:

            action_text = (
                " / ".join(actions)
            )

        else:

            action_text = "대기"

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

            "전략최고가":
                highest_price,

            "최고가_발생일":
                highest_date,

            "고점대비하락률":
                drawdown * 100,

            "매매":
                action_text,

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

            "다음매수레벨":
                next_level,

            "다음매수기준가":
                next_buy_price,

            "다음매수_고점대비":
                next_buy_drawdown,
        })

    # =================================================================
    # 11. 마지막 미청산 포지션 기록
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

        market_value = (
            buy_price * 0
        )

        market_value = (
            last_price
            * shares
        )

        cost = (
            buy_price
            * shares
        )

        unrealized_profit = (
            market_value
            - cost
        )

        return_pct = (
            last_price
            / buy_price
            - 1
        ) * 100

        calendar_days = (
            last_date
            - position["매수일"]
        ).days

        trading_days = (
            len(df)
            - 1
            - position["매수_index"]
        )

        trade_number += 1

        trades.append({

            "거래번호":
                trade_number,

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

            "매수_고점":
                position[
                    "매수_고점"
                ],

            "매수_고점_발생일":
                position[
                    "매수_고점_발생일"
                ],

            "매수_하락률":
                position[
                    "매수_하락률"
                ],

            "매도목표가":
                calculate_sell_price(
                    buy_price
                ),

            "매도일":
                None,

            "매도가":
                None,

            "수량":
                shares,

            "매수금액":
                cost,

            "매도금액":
                None,

            "수익금":
                unrealized_profit,

            "수익률":
                return_pct,

            "보유기간":
                calendar_days,

            "보유기간_거래일":
                trading_days,

            "상태":
                "미청산",
        })

    # =================================================================
    # DataFrame
    # =================================================================

    daily_df = pd.DataFrame(
        daily_records
    )

    trades_df = pd.DataFrame(
        trades
    )

    return (
        daily_df,
        trades_df
    )


# ====================================================================
# 전략 MDD 계산
# ====================================================================

def calculate_strategy_mdd(
    daily_df
):

    asset = daily_df[
        "총자산"
    ].astype(float)

    running_max = (
        asset.cummax()
    )

    drawdown = (
        asset
        / running_max
        - 1
    )

    mdd = (
        drawdown.min()
    )

    mdd_index = (
        drawdown.idxmin()
    )

    # ---------------------------------------------------------------
    # MDD 시작점
    # ---------------------------------------------------------------

    peak_index = (
        asset.loc[
            :mdd_index
        ].idxmax()
    )

    mdd_start_date = (
        daily_df.loc[
            peak_index,
            "날짜"
        ]
    )

    mdd_low_date = (
        daily_df.loc[
            mdd_index,
            "날짜"
        ]
    )

    # ---------------------------------------------------------------
    # 회복일
    # ---------------------------------------------------------------

    peak_asset = (
        asset.loc[
            peak_index
        ]
    )

    recovery_candidates = (
        asset.loc[
            mdd_index:
        ]
        [
            asset.loc[
                mdd_index:
            ]
            >= peak_asset
        ]
    )

    if not recovery_candidates.empty:

        recovery_index = (
            recovery_candidates.index[0]
        )

        recovery_date = (
            daily_df.loc[
                recovery_index,
                "날짜"
            ]
        )

        recovery_days = (
            recovery_date
            - mdd_start_date
        ).days

        recovery_trading_days = (
            recovery_index
            - peak_index
        )

    else:

        recovery_date = None

        recovery_days = None

        recovery_trading_days = None

    return {

        "MDD":
            mdd * 100,

        "MDD_시작일":
            mdd_start_date,

        "MDD_저점일":
            mdd_low_date,

        "MDD_회복일":
            recovery_date,

        "MDD_회복기간":
            recovery_days,

        "MDD_회복기간_거래일":
            recovery_trading_days,
    }


# ====================================================================
# 요약 생성
# ====================================================================

def create_summary(
    df,
    daily_df,
    trades_df
):

    start_date = (
        df["날짜"].iloc[0]
    )

    end_date = (
        df["날짜"].iloc[-1]
    )

    years = (
        end_date
        - start_date
    ).days / 365.25

    # ---------------------------------------------------------------
    # 최종자산
    # ---------------------------------------------------------------

    final_asset = float(
        daily_df[
            "총자산"
        ].iloc[-1]
    )

    # ---------------------------------------------------------------
    # 수익
    # ---------------------------------------------------------------

    total_profit = (
        final_asset
        - INITIAL_CAPITAL
    )

    total_return = (
        final_asset
        / INITIAL_CAPITAL
        - 1
    )

    # ---------------------------------------------------------------
    # CAGR
    # ---------------------------------------------------------------

    if years > 0:

        cagr = (
            final_asset
            / INITIAL_CAPITAL
        ) ** (
            1 / years
        ) - 1

    else:

        cagr = np.nan

    # ---------------------------------------------------------------
    # MDD
    # ---------------------------------------------------------------

    mdd_info = (
        calculate_strategy_mdd(
            daily_df
        )
    )

    # ---------------------------------------------------------------
    # 거래
    # ---------------------------------------------------------------

    completed = trades_df[
        trades_df["상태"]
        == "완료"
    ]

    unclosed = trades_df[
        trades_df["상태"]
        == "미청산"
    ]

    completed_count = len(
        completed
    )

    unclosed_count = len(
        unclosed
    )

    # ---------------------------------------------------------------
    # 실현수익
    # ---------------------------------------------------------------

    if completed_count > 0:

        realized_profit = float(
            completed[
                "수익금"
            ].sum()
        )

        avg_trade_return = float(
            completed[
                "수익률"
            ].mean()
        )

        max_trade_return = float(
            completed[
                "수익률"
            ].max()
        )

        min_trade_return = float(
            completed[
                "수익률"
            ].min()
        )

        avg_holding_days = float(
            completed[
                "보유기간"
            ].mean()
        )

        total_buy_amount = float(
            completed[
                "매수금액"
            ].sum()
        )

        total_sell_amount = float(
            completed[
                "매도금액"
            ].sum()
        )

    else:

        realized_profit = 0

        avg_trade_return = np.nan

        max_trade_return = np.nan

        min_trade_return = np.nan

        avg_holding_days = np.nan

        total_buy_amount = 0

        total_sell_amount = 0

    # ---------------------------------------------------------------
    # 미실현
    # ---------------------------------------------------------------

    if unclosed_count > 0:

        unrealized_profit = float(
            unclosed[
                "수익금"
            ].sum()
        )

    else:

        unrealized_profit = 0

    # ---------------------------------------------------------------
    # 최대 보유주수
    # ---------------------------------------------------------------

    max_position = int(
        daily_df[
            "보유주수"
        ].max()
    )

    # ---------------------------------------------------------------
    # 승률
    # ---------------------------------------------------------------

    if completed_count > 0:

        winning_trades = (
            completed[
                completed[
                    "수익금"
                ] > 0
            ]
        )

        win_rate = (
            len(winning_trades)
            / completed_count
            * 100
        )

    else:

        win_rate = np.nan

    # ---------------------------------------------------------------
    # 요약
    # ---------------------------------------------------------------

    summary_data = [

        (
            "분석 시작일",
            start_date
        ),

        (
            "분석 종료일",
            end_date
        ),

        (
            "투자기간(년)",
            years
        ),

        (
            "초기자금",
            INITIAL_CAPITAL
        ),

        (
            "최종자산",
            final_asset
        ),

        (
            "총 수익금",
            total_profit
        ),

        (
            "총 수익률",
            total_return * 100
        ),

        (
            "CAGR",
            cagr * 100
        ),

        (
            "매수 조건",
            f"고점 대비 -{BUY_STEP:.0%}마다"
        ),

        (
            "매수 수량",
            f"{BUY_SHARES}주"
        ),

        (
            "개별 매도 조건",
            f"매수가 대비 +{SELL_PROFIT:.0%}"
        ),

        (
            "총 거래 기록",
            len(trades_df)
        ),

        (
            "완료 매도",
            completed_count
        ),

        (
            "미청산 포지션",
            unclosed_count
        ),

        (
            "승률",
            win_rate
        ),

        (
            "실현 수익금",
            realized_profit
        ),

        (
            "미실현 수익금",
            unrealized_profit
        ),

        (
            "평균 거래 수익률",
            avg_trade_return
        ),

        (
            "최고 거래 수익률",
            max_trade_return
        ),

        (
            "최저 거래 수익률",
            min_trade_return
        ),

        (
            "평균 보유기간(일)",
            avg_holding_days
        ),

        (
            "총 매수금액",
            total_buy_amount
        ),

        (
            "총 매도금액",
            total_sell_amount
        ),

        (
            "최대 보유주수",
            max_position
        ),

        (
            "전략 MDD",
            mdd_info["MDD"]
        ),

        (
            "MDD 시작일",
            mdd_info["MDD_시작일"]
        ),

        (
            "MDD 저점일",
            mdd_info["MDD_저점일"]
        ),

        (
            "MDD 회복일",
            mdd_info["MDD_회복일"]
        ),

        (
            "MDD 회복기간(일)",
            mdd_info["MDD_회복기간"]
        ),

        (
            "MDD 회복기간(거래일)",
            mdd_info[
                "MDD_회복기간_거래일"
            ]
        ),

        (
            "환율",
            "사용 안 함"
        ),

        (
            "수수료",
            "$0"
        ),

        (
            "세금",
            "$0"
        ),
    ]

    summary_df = pd.DataFrame(
        summary_data,
        columns=[
            "항목",
            "값"
        ]
    )

    return summary_df


# ====================================================================
# 보유포지션
# ====================================================================

def create_positions_df(
    trades_df
):

    if trades_df.empty:

        return pd.DataFrame()

    columns = [

        "거래번호",

        "매수레벨",

        "매수일",

        "매수가",

        "매수_고점",

        "매수_고점_발생일",

        "매수_하락률",

        "매도목표가",

        "매도일",

        "매도가",

        "수량",

        "매수금액",

        "매도금액",

        "수익금",

        "수익률",

        "보유기간",

        "보유기간_거래일",

        "상태",
    ]

    columns = [
        col
        for col in columns
        if col in trades_df.columns
    ]

    return trades_df[
        columns
    ].copy()


# ====================================================================
# Excel 스타일
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

    # ---------------------------------------------------------------
    # 헤더
    # ---------------------------------------------------------------

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

        cell.border = border

    # ---------------------------------------------------------------
    # 전체 셀
    # ---------------------------------------------------------------

    for row in ws.iter_rows():

        for cell in row:

            cell.border = border

            cell.alignment = Alignment(
                vertical="center"
            )

    # ---------------------------------------------------------------
    # 컬럼 너비
    # ---------------------------------------------------------------

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

    # ---------------------------------------------------------------
    # Freeze
    # ---------------------------------------------------------------

    ws.freeze_panes = "A2"

    # ---------------------------------------------------------------
    # Filter
    # ---------------------------------------------------------------

    if ws.max_row > 1:

        ws.auto_filter.ref = (
            ws.dimensions
        )


# ====================================================================
# Excel 숫자 포맷
# ====================================================================

def format_excel(
    wb
):

    # ================================================================
    # 요약
    # ================================================================

    ws = wb["요약"]

    for row in range(
        2,
        ws.max_row + 1
    ):

        label = ws.cell(
            row=row,
            column=1
        ).value

        cell = ws.cell(
            row=row,
            column=2
        )

        if label in [

            "초기자금",
            "최종자산",
            "총 수익금",
            "실현 수익금",
            "미실현 수익금",
            "총 매수금액",
            "총 매도금액",

        ]:

            cell.number_format = (
                '$#,##0.00'
            )

        elif label in [

            "총 수익률",
            "CAGR",
            "승률",
            "평균 거래 수익률",
            "최고 거래 수익률",
            "최저 거래 수익률",
            "전략 MDD",

        ]:

            cell.number_format = (
                '0.00"%"'
            )

    # ================================================================
    # 거래내역
    # ================================================================

    ws = wb["거래내역"]

    headers = {
        cell.value: cell.column
        for cell in ws[1]
    }

    price_columns = [

        "매수가",
        "매수_고점",
        "매도목표가",
        "매도가",
    ]

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

    money_columns = [

        "매수금액",
        "매도금액",
        "수익금",
    ]

    for name in money_columns:

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

    if "수익률" in headers:

        col = headers[
            "수익률"
        ]

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

    if "매수_하락률" in headers:

        col = headers[
            "매수_하락률"
        ]

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

    # ================================================================
    # 일별전략
    # ================================================================

    ws = wb["일별전략"]

    headers = {
        cell.value: cell.column
        for cell in ws[1]
    }

    price_columns = [

        "수정주가",
        "고가",
        "저가",
        "종가",
        "전략최고가",
        "평균매수가",
        "다음매수기준가",
    ]

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

    percent_columns = [

        "고점대비하락률",
        "평균매수가대비수익률",
        "누적수익률",
        "다음매수_고점대비",
    ]

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

    money_columns = [

        "보유평가금액",
        "미실현손익",
        "현금",
        "총자산",
    ]

    for name in money_columns:

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

    # ================================================================
    # 자산추이
    # ================================================================

    ws = wb["자산추이"]

    headers = {
        cell.value: cell.column
        for cell in ws[1]
    }

    for name in [

        "수정주가",
        "총자산",
        "현금",
        "보유평가금액",

    ]:

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

    if "누적수익률" in headers:

        col = headers[
            "누적수익률"
        ]

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


# ====================================================================
# Excel 저장
# ====================================================================

def save_excel(
    original_df,
    summary_df,
    trades_df,
    daily_df
):

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    print()
    print("=" * 90)
    print("Excel 파일 생성")
    print("=" * 90)

    # ---------------------------------------------------------------
    # 보유 포지션
    # ---------------------------------------------------------------

    positions_df = (
        create_positions_df(
            trades_df
        )
    )

    # ---------------------------------------------------------------
    # 자산 추이
    # ---------------------------------------------------------------

    asset_df = daily_df[
        [
            "날짜",
            "수정주가",
            "총자산",
            "현금",
            "보유평가금액",
            "보유주수",
            "보유포지션수",
            "누적수익률",
            "매매",
        ]
    ].copy()

    # ---------------------------------------------------------------
    # Excel 작성
    # ---------------------------------------------------------------

    with pd.ExcelWriter(
        OUTPUT_FILE,
        engine="openpyxl"
    ) as writer:

        summary_df.to_excel(
            writer,
            sheet_name="요약",
            index=False
        )

        trades_df.to_excel(
            writer,
            sheet_name="거래내역",
            index=False
        )

        daily_df.to_excel(
            writer,
            sheet_name="일별전략",
            index=False
        )

        positions_df.to_excel(
            writer,
            sheet_name="보유포지션",
            index=False
        )

        asset_df.to_excel(
            writer,
            sheet_name="자산추이",
            index=False
        )

        original_df.to_excel(
            writer,
            sheet_name="원본데이터",
            index=False
        )

    # ---------------------------------------------------------------
    # OpenPyXL
    # ---------------------------------------------------------------

    wb = load_workbook(
        OUTPUT_FILE
    )

    # ---------------------------------------------------------------
    # 전체 스타일
    # ---------------------------------------------------------------

    for ws in wb.worksheets:

        style_worksheet(
            ws
        )

    # ---------------------------------------------------------------
    # 숫자 포맷
    # ---------------------------------------------------------------

    format_excel(
        wb
    )

    # ================================================================
    # 일별 매매 색상
    # ================================================================

    ws = wb[
        "일별전략"
    ]

    headers = {
        cell.value: cell.column
        for cell in ws[1]
    }

    action_col = headers.get(
        "매매"
    )

    if action_col:

        for row in range(
            2,
            ws.max_row + 1
        ):

            cell = ws.cell(
                row=row,
                column=action_col
            )

            value = str(
                cell.value
            )

            if "매수" in value:

                cell.fill = (
                    PatternFill(
                        "solid",
                        fgColor="C6EFCE"
                    )
                )

                cell.font = Font(
                    bold=True
                )

            if "매도" in value:

                cell.fill = (
                    PatternFill(
                        "solid",
                        fgColor="FFC7CE"
                    )
                )

                cell.font = Font(
                    bold=True
                )

    # ================================================================
    # 거래내역 색상
    # ================================================================

    ws = wb[
        "거래내역"
    ]

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

                cell.fill = (
                    PatternFill(
                        "solid",
                        fgColor="C6EFCE"
                    )
                )

            elif cell.value == "미청산":

                cell.fill = (
                    PatternFill(
                        "solid",
                        fgColor="FFF2CC"
                    )
                )

    # ================================================================
    # 자산추이 차트
    # ================================================================

    ws = wb[
        "자산추이"
    ]

    headers = {
        cell.value: cell.column
        for cell in ws[1]
    }

    if "총자산" in headers:

        chart = LineChart()

        chart.title = (
            "TQQQ 피라미딩 전략 자산 추이"
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
            "K2"
        )

    # ================================================================
    # 저장
    # ================================================================

    wb.save(
        OUTPUT_FILE
    )

    print()
    print(
        "Excel 저장 완료"
    )

    print(
        OUTPUT_FILE.resolve()
    )


# ====================================================================
# 최종 결과 출력
# ====================================================================

def print_result(
    summary_df,
    trades_df
):

    print()
    print("=" * 90)
    print("최종 결과")
    print("=" * 90)

    for _, row in summary_df.iterrows():

        print(
            f"{str(row['항목']):35s}"
            f" : {row['값']}"
        )

    # ---------------------------------------------------------------
    # 거래내역
    # ---------------------------------------------------------------

    print()
    print("=" * 90)
    print("최근 거래 10건")
    print("=" * 90)

    if not trades_df.empty:

        print(
            trades_df.tail(10).to_string(
                index=False
            )
        )


# ====================================================================
# MAIN
# ====================================================================

def main():

    print()
    print("=" * 90)
    print("TQQQ - 고점 대비 -10% 피라미딩 전략")
    print("=" * 90)

    # ---------------------------------------------------------------
    # 1. 데이터
    # ---------------------------------------------------------------

    df = load_data()

    # ---------------------------------------------------------------
    # 2. 백테스트
    # ---------------------------------------------------------------

    (
        daily_df,
        trades_df
    ) = run_backtest(
        df
    )

    # ---------------------------------------------------------------
    # 3. 요약
    # ---------------------------------------------------------------

    summary_df = (
        create_summary(
            df,
            daily_df,
            trades_df
        )
    )

    # ---------------------------------------------------------------
    # 4. 결과 출력
    # ---------------------------------------------------------------

    print_result(
        summary_df,
        trades_df
    )

    # ---------------------------------------------------------------
    # 5. Excel
    # ---------------------------------------------------------------

    save_excel(
        original_df=df,
        summary_df=summary_df,
        trades_df=trades_df,
        daily_df=daily_df
    )

    print()
    print("=" * 90)
    print("백테스트 완료")
    print("=" * 90)


# ====================================================================
# 실행
# ====================================================================

if __name__ == "__main__":

    main()

