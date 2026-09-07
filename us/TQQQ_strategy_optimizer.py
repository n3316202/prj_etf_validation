"""
====================================================================
TQQQ Pyramid Strategy Optimizer
====================================================================

목적
--------------------------------------------------------------------
TQQQ 실제 일별 OHLC 데이터를 이용하여

    가격 하락
        ↓
    일정 가격 간격마다 분할 매수
        ↓
    반등
        ↓
    일정 가격 간격마다 분할 매도

하는 피라미드 매매전략을 자동 최적화한다.


핵심 전략 예시
--------------------------------------------------------------------

기본 전략

    TQQQ $1 하락
        → 1주 매수

    TQQQ $2 상승
        → 1주 매도


하지만 자동 최적화에서는 다음을 모두 테스트한다.

    매수 간격
        $0.25
        $0.50
        $1
        $1.50
        $2
        $3
        $5

    매도 간격
        $0.50
        $1
        $1.50
        $2
        $3
        $5
        $10

    1회 매수금액
        100,000
        200,000
        300,000
        500,000
        1,000,000

    최대 투자금
        5M
        10M
        20M
        30M
        50M

    최대 보유주식
        10
        20
        50
        100
        200


백테스트
--------------------------------------------------------------------

1. 전체 기간 최적화
2. 최고 수익률
3. 최고 CAGR
4. MDD 제한 전략
5. Calmar 최고 전략

그리고

Walk-Forward Optimization

    학습 : 2016 ~ 2022
    검증 : 2023 ~ 2026

을 수행한다.


중요
--------------------------------------------------------------------
일별 OHLC 데이터만 있기 때문에 하루 안에서

    고가 / 저가가 모두 여러 매매가격을 통과한 경우

실제 장중 가격 순서는 알 수 없다.

따라서 기본값은 보수적인

    "LOW_FIRST"

방식을 사용한다.

즉 하루에 매수/매도가 모두 발생할 경우
하락 → 매수 → 반등 → 매도의 순서로 처리한다.

반대로

    HIGH_FIRST

도 테스트할 수 있다.


데이터
--------------------------------------------------------------------

기존 TQQQ CSV 사용.

예:

    TQQQ_analysis.csv

컬럼:

    날짜
    수정주가
    Capital Gains
    종가
    배당
    고가
    저가
    시가
    주식분할
    거래량
    최고가
    최고가_발생일
    고점_대비_하락률
    MDD
    MDD_시작일
    MDD_저점일
    회복일
    회복기간
    회복기간_거래일


결과
--------------------------------------------------------------------

analysis/TQQQ_pyramid_optimization/

    전체_최적화_결과.csv
    TOP100_수익률.csv
    TOP100_CAGR.csv
    TOP100_Calmar.csv
    TOP100_MDD20.csv
    TOP100_MDD30.csv

    WalkForward_결과.csv
    WalkForward_TOP100.csv

    기본전략_1달러매수_2달러매도.csv
    거래내역_최고전략.csv
====================================================================
"""

from pathlib import Path
from itertools import product

import numpy as np
import pandas as pd


# ====================================================================
# 1. 사용자 설정
# ====================================================================

# --------------------------------------------------------------------
# 초기 투자금
# --------------------------------------------------------------------

INITIAL_CAPITAL = 20_000_000


# --------------------------------------------------------------------
# 거래비용
# --------------------------------------------------------------------

# 매수 / 매도 각각 적용
FEE = 0.0005

# 슬리피지
SLIPPAGE = 0.0005


# --------------------------------------------------------------------
# 일중 체결 순서
# --------------------------------------------------------------------

# LOW_FIRST
#
#   시가
#     ↓
#   하락
#     ↓
#   매수
#     ↓
#   상승
#     ↓
#   매도
#
#
# HIGH_FIRST
#
#   상승
#     ↓
#   매도
#     ↓
#   하락
#     ↓
#   매수

INTRADAY_ORDER = "LOW_FIRST"


# ====================================================================
# 2. 날짜 설정
# ====================================================================

BACKTEST_START = "2016-01-01"

BACKTEST_END = (
    pd.Timestamp.now()
    .strftime("%Y-%m-%d")
)


# ====================================================================
# 3. 경로 설정
# ====================================================================

BASE_DIR = Path(
    __file__
).resolve().parent

PROJECT_DIR = (
    BASE_DIR.parent
)

INPUT_DIR = (
    PROJECT_DIR
    / "us"
    / "data"
    / "us_etf"
)

OUTPUT_DIR = (
    INPUT_DIR
    / "analysis"
    / "TQQQ_pyramid_optimization"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# --------------------------------------------------------------------
# TQQQ 파일
# --------------------------------------------------------------------
#
# 실제 사용 중인 파일명을 우선 TQQQ_analysis.csv로 설정
#

INPUT_FILE = (
    INPUT_DIR
    / "TQQQ_analysis.csv"
)


# ====================================================================
# 4. 최적화 파라미터
# ====================================================================

# --------------------------------------------------------------------
# 매수 간격
# --------------------------------------------------------------------

BUY_INTERVALS = [
    0.25,
    0.50,
    0.75,
    1.00,
    1.50,
    2.00,
    3.00,
    5.00,
]


# --------------------------------------------------------------------
# 매도 간격
# --------------------------------------------------------------------

SELL_INTERVALS = [
    0.50,
    1.00,
    1.50,
    2.00,
    3.00,
    5.00,
    7.50,
    10.00,
]


# --------------------------------------------------------------------
# 1회 매수금액
# --------------------------------------------------------------------

BUY_AMOUNTS = [
    100_000,
    200_000,
    300_000,
    500_000,
    1_000_000,
]


# --------------------------------------------------------------------
# 최대 투자금
# --------------------------------------------------------------------

MAX_INVESTMENTS = [
    5_000_000,
    10_000_000,
    20_000_000,
    30_000_000,
    50_000_000,
]


# --------------------------------------------------------------------
# 최대 보유주식
# --------------------------------------------------------------------

MAX_SHARES = [
    10,
    20,
    50,
    100,
    200,
]


# ====================================================================
# 5. 데이터 로딩
# ====================================================================

def load_data():

    # ---------------------------------------------------------------
    # 파일 존재 확인
    # ---------------------------------------------------------------

    if not INPUT_FILE.exists():

        # TQQQ.csv도 확인
        alternative = (
            INPUT_DIR
            / "TQQQ.csv"
        )

        if alternative.exists():

            print(
                f"⚠ TQQQ_analysis.csv가 없어 "
                f"TQQQ.csv 사용"
            )

            filename = alternative

        else:

            raise FileNotFoundError(
                "\nTQQQ 데이터를 찾을 수 없습니다.\n\n"
                f"확인 경로:\n"
                f"{INPUT_FILE}\n"
                f"{alternative}"
            )

    else:

        filename = INPUT_FILE


    print()
    print("=" * 80)
    print("TQQQ 데이터 로딩")
    print("=" * 80)

    print(
        f"파일 : {filename}"
    )


    # ---------------------------------------------------------------
    # CSV 읽기
    # ---------------------------------------------------------------

    df = pd.read_csv(
        filename
    )


    if df.empty:

        raise ValueError(
            "TQQQ 데이터가 비어 있습니다."
        )


    # ---------------------------------------------------------------
    # 날짜
    # ---------------------------------------------------------------

    if "날짜" not in df.columns:

        if "Date" in df.columns:

            df = df.rename(
                columns={
                    "Date": "날짜"
                }
            )

        elif "date" in df.columns:

            df = df.rename(
                columns={
                    "date": "날짜"
                }
            )

        else:

            raise ValueError(
                "날짜 컬럼을 찾을 수 없습니다."
            )


    df["날짜"] = pd.to_datetime(
        df["날짜"],
        errors="coerce"
    )


    # ---------------------------------------------------------------
    # 필요한 가격 컬럼
    # ---------------------------------------------------------------

    required_columns = [
        "시가",
        "고가",
        "저가",
        "종가",
    ]


    for column in required_columns:

        if column not in df.columns:

            raise ValueError(
                f"필수 컬럼이 없습니다: {column}"
            )


        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )


    # ---------------------------------------------------------------
    # 정리
    # ---------------------------------------------------------------

    df = (
        df
        .dropna(
            subset=[
                "날짜",
                "시가",
                "고가",
                "저가",
                "종가",
            ]
        )
        .sort_values("날짜")
        .drop_duplicates(
            subset=["날짜"],
            keep="last"
        )
        .reset_index(drop=True)
    )


    # ---------------------------------------------------------------
    # 기간
    # ---------------------------------------------------------------

    df = df[
        (df["날짜"] >= BACKTEST_START)
        & (df["날짜"] <= BACKTEST_END)
    ].copy()


    df = (
        df
        .reset_index(drop=True)
    )


    print(
        f"기간 : "
        f"{df['날짜'].iloc[0].date()} "
        f"~ "
        f"{df['날짜'].iloc[-1].date()}"
    )

    print(
        f"거래일 : "
        f"{len(df):,}"
    )


    return df


# ====================================================================
# 6. 가격 체결 함수
# ====================================================================

def buy_price(price):

    return (
        price
        * (1 + SLIPPAGE)
    )


def sell_price(price):

    return (
        price
        * (1 - SLIPPAGE)
    )


# ====================================================================
# 7. 피라미드 백테스트
# ====================================================================

def backtest_pyramid(
    df,
    buy_interval,
    sell_interval,
    buy_amount,
    max_investment,
    max_shares,
    record_trades=False,
):

    cash = INITIAL_CAPITAL

    shares = 0

    total_invested = 0

    avg_cost = 0

    # ---------------------------------------------------------------
    # 전략 기준가격
    #
    # 처음에는 첫날 시가
    # ---------------------------------------------------------------

    reference_price = (
        df.iloc[0]["시가"]
    )

    equity_curve = []

    trades = []

    buy_count = 0

    sell_count = 0


    # ================================================================
    # 일별 처리
    # ================================================================

    for i in range(
        len(df)
    ):

        row = df.iloc[i]

        date = row["날짜"]

        open_price = float(
            row["시가"]
        )

        high_price = float(
            row["고가"]
        )

        low_price = float(
            row["저가"]
        )

        close_price = float(
            row["종가"]
        )


        # ============================================================
        # 첫날 기준가격
        # ============================================================

        if i == 0:

            reference_price = (
                open_price
            )


        # ============================================================
        # LOW_FIRST
        # ============================================================

        if INTRADAY_ORDER == "LOW_FIRST":

            # --------------------------------------------------------
            # 하락 매수
            # --------------------------------------------------------

            while True:

                target_buy = (
                    reference_price
                    - buy_interval
                )

                if low_price > target_buy:

                    break


                if shares >= max_shares:

                    break


                if (
                    total_invested
                    + buy_amount
                    > max_investment
                ):

                    break


                execution_price = (
                    buy_price(
                        target_buy
                    )
                )


                # 실제 필요금액
                required_cash = (
                    buy_amount
                )


                if (
                    cash < required_cash
                ):

                    break


                quantity = (
                    required_cash
                    / execution_price
                )


                # 정수 주식 기준
                quantity = max(
                    1,
                    int(quantity)
                )


                actual_cost = (
                    quantity
                    * execution_price
                    * (1 + FEE)
                )


                if actual_cost > cash:

                    break


                if (
                    total_invested
                    + actual_cost
                    > max_investment
                ):

                    break


                # ----------------------------------------------------
                # 평균매입가
                # ----------------------------------------------------

                old_value = (
                    shares
                    * avg_cost
                )

                new_value = (
                    quantity
                    * execution_price
                )

                shares += quantity

                total_invested += (
                    actual_cost
                )

                cash -= actual_cost

                avg_cost = (
                    old_value
                    + new_value
                ) / shares


                buy_count += 1


                if record_trades:

                    trades.append({

                        "날짜": date,

                        "구분": "BUY",

                        "가격":
                            execution_price,

                        "수량":
                            quantity,

                        "현금":
                            cash,

                        "보유주식":
                            shares,

                        "평균매입가":
                            avg_cost,

                        "투자금":
                            total_invested,

                    })


                # 다음 단계 기준
                reference_price = (
                    target_buy
                )


            # --------------------------------------------------------
            # 상승 매도
            # --------------------------------------------------------

            while shares > 0:

                target_sell = (
                    reference_price
                    + sell_interval
                )


                if high_price < target_sell:

                    break


                execution_price = (
                    sell_price(
                        target_sell
                    )
                )


                quantity = 1


                proceeds = (
                    execution_price
                    * quantity
                    * (1 - FEE)
                )


                if shares < quantity:

                    break


                cash += proceeds

                shares -= quantity


                sell_count += 1


                # 투자금 감소
                if shares == 0:

                    total_invested = 0

                    avg_cost = 0

                else:

                    total_invested = (
                        shares
                        * avg_cost
                    )


                if record_trades:

                    pnl = (
                        execution_price
                        - avg_cost
                    )

                    trades.append({

                        "날짜": date,

                        "구분": "SELL",

                        "가격":
                            execution_price,

                        "수량":
                            quantity,

                        "현금":
                            cash,

                        "보유주식":
                            shares,

                        "평균매입가":
                            avg_cost,

                        "실현손익":
                            pnl,

                    })


                reference_price = (
                    target_sell
                )


        # ============================================================
        # HIGH_FIRST
        # ============================================================

        else:

            # --------------------------------------------------------
            # 상승 매도
            # --------------------------------------------------------

            while shares > 0:

                target_sell = (
                    reference_price
                    + sell_interval
                )

                if high_price < target_sell:

                    break


                execution_price = (
                    sell_price(
                        target_sell
                    )
                )


                quantity = 1


                proceeds = (
                    execution_price
                    * quantity
                    * (1 - FEE)
                )


                cash += proceeds

                shares -= quantity

                sell_count += 1


                if shares == 0:

                    total_invested = 0

                    avg_cost = 0

                else:

                    total_invested = (
                        shares
                        * avg_cost
                    )


                if record_trades:

                    trades.append({

                        "날짜": date,

                        "구분": "SELL",

                        "가격":
                            execution_price,

                        "수량":
                            quantity,

                        "현금":
                            cash,

                        "보유주식":
                            shares,

                        "평균매입가":
                            avg_cost,

                    })


                reference_price = (
                    target_sell
                )


            # --------------------------------------------------------
            # 하락 매수
            # --------------------------------------------------------

            while True:

                target_buy = (
                    reference_price
                    - buy_interval
                )

                if low_price > target_buy:

                    break


                if shares >= max_shares:

                    break


                if (
                    total_invested
                    + buy_amount
                    > max_investment
                ):

                    break


                execution_price = (
                    buy_price(
                        target_buy
                    )
                )


                if cash < buy_amount:

                    break


                quantity = max(
                    1,
                    int(
                        buy_amount
                        / execution_price
                    )
                )


                actual_cost = (
                    quantity
                    * execution_price
                    * (1 + FEE)
                )


                if actual_cost > cash:

                    break


                if (
                    total_invested
                    + actual_cost
                    > max_investment
                ):

                    break


                old_value = (
                    shares
                    * avg_cost
                )

                new_value = (
                    quantity
                    * execution_price
                )


                shares += quantity

                total_invested += (
                    actual_cost
                )

                cash -= actual_cost


                avg_cost = (
                    old_value
                    + new_value
                ) / shares


                buy_count += 1


                if record_trades:

                    trades.append({

                        "날짜": date,

                        "구분": "BUY",

                        "가격":
                            execution_price,

                        "수량":
                            quantity,

                        "현금":
                            cash,

                        "보유주식":
                            shares,

                        "평균매입가":
                            avg_cost,

                        "투자금":
                            total_invested,

                    })


                reference_price = (
                    target_buy
                )


        # ============================================================
        # 평가금액
        # ============================================================

        portfolio_value = (
            cash
            + shares * close_price
        )


        equity_curve.append(
            portfolio_value
        )


    # =================================================================
    # 최종 평가
    # =================================================================

    equity = pd.Series(
        equity_curve,
        index=df["날짜"]
    )


    final_asset = (
        equity.iloc[-1]
    )


    total_return = (
        final_asset
        / INITIAL_CAPITAL
        - 1
    )


    years = (
        df["날짜"].iloc[-1]
        - df["날짜"].iloc[0]
    ).days / 365.25


    if years > 0:

        cagr = (
            final_asset
            / INITIAL_CAPITAL
        ) ** (
            1 / years
        ) - 1

    else:

        cagr = 0


    # =================================================================
    # MDD
    # =================================================================

    running_max = (
        equity
        .cummax()
    )

    drawdown = (
        equity
        / running_max
        - 1
    )

    mdd = (
        drawdown.min()
    )


    # =================================================================
    # MDD 시작 / 저점
    # =================================================================

    mdd_date = (
        drawdown.idxmin()
    )


    peak_before_mdd = (
        equity.loc[:mdd_date]
        .idxmax()
    )


    # =================================================================
    # Calmar
    # =================================================================

    if abs(mdd) > 0:

        calmar = (
            cagr
            / abs(mdd)
        )

    else:

        calmar = np.nan


    # =================================================================
    # Sharpe
    # =================================================================

    daily_returns = (
        equity
        .pct_change()
        .dropna()
    )


    if (
        len(daily_returns) > 1
        and daily_returns.std() > 0
    ):

        sharpe = (
            daily_returns.mean()
            / daily_returns.std()
            * np.sqrt(252)
        )

    else:

        sharpe = np.nan


    # =================================================================
    # 결과
    # =================================================================

    result = {

        "매수간격":
            buy_interval,

        "매도간격":
            sell_interval,

        "1회매수금액":
            buy_amount,

        "최대투자금":
            max_investment,

        "최대보유주식":
            max_shares,

        "최종자산":
            final_asset,

        "총수익률":
            total_return,

        "CAGR":
            cagr,

        "MDD":
            mdd,

        "Calmar":
            calmar,

        "Sharpe":
            sharpe,

        "매수횟수":
            buy_count,

        "매도횟수":
            sell_count,

        "최종보유주식":
            shares,

        "최종현금":
            cash,

        "MDD_시작일":
            peak_before_mdd,

        "MDD_저점일":
            mdd_date,

    }


    if record_trades:

        return (
            result,
            pd.DataFrame(trades),
            equity
        )


    return result


# ====================================================================
# 8. 기본전략
# ====================================================================

def run_base_strategy(df):

    print()
    print("=" * 80)
    print("기본전략 테스트")
    print("=" * 80)

    print()
    print(
        "전략:"
    )

    print(
        "TQQQ $1 하락 → 1주 매수"
    )

    print(
        "TQQQ $2 상승 → 1주 매도"
    )


    result = backtest_pyramid(

        df=df,

        buy_interval=1.0,

        sell_interval=2.0,

        buy_amount=100_000,

        max_investment=50_000_000,

        max_shares=100,

        record_trades=True,

    )


    metrics, trades, equity = result


    result_df = pd.DataFrame(
        [metrics]
    )


    result_df.to_csv(

        OUTPUT_DIR
        / "기본전략_1달러매수_2달러매도.csv",

        index=False,

        encoding="utf-8-sig"

    )


    trades.to_csv(

        OUTPUT_DIR
        / "기본전략_거래내역.csv",

        index=False,

        encoding="utf-8-sig"

    )


    return metrics


# ====================================================================
# 9. 전체 최적화
# ====================================================================

def optimize(df):

    print()
    print("=" * 80)
    print("TQQQ 피라미드 전략 최적화")
    print("=" * 80)


    parameter_count = (
        len(BUY_INTERVALS)
        * len(SELL_INTERVALS)
        * len(BUY_AMOUNTS)
        * len(MAX_INVESTMENTS)
        * len(MAX_SHARES)
    )


    print()
    print(
        f"총 조합 수 : "
        f"{parameter_count:,}"
    )


    results = []


    count = 0


    for (
        buy_interval,
        sell_interval,
        buy_amount,
        max_investment,
        max_shares,
    ) in product(

        BUY_INTERVALS,

        SELL_INTERVALS,

        BUY_AMOUNTS,

        MAX_INVESTMENTS,

        MAX_SHARES,

    ):

        count += 1


        result = backtest_pyramid(

            df=df,

            buy_interval=buy_interval,

            sell_interval=sell_interval,

            buy_amount=buy_amount,

            max_investment=max_investment,

            max_shares=max_shares,

        )


        results.append(
            result
        )


        if (
            count % 5000 == 0
            or count == parameter_count
        ):

            print(
                f"\r진행률 : "
                f"{count:,}"
                f" / "
                f"{parameter_count:,}",
                end=""
            )


    print()


    result_df = pd.DataFrame(
        results
    )


    return result_df


# ====================================================================
# 10. 결과 저장
# ====================================================================

def save_optimization_results(
    result_df
):

    # =================================================================
    # 전체 결과
    # =================================================================

    result_df.to_csv(

        OUTPUT_DIR
        / "전체_최적화_결과.csv",

        index=False,

        encoding="utf-8-sig"

    )


    # =================================================================
    # 수익률 TOP
    # =================================================================

    top_return = (

        result_df

        .sort_values(

            "총수익률",

            ascending=False

        )

        .head(100)

    )


    top_return.to_csv(

        OUTPUT_DIR
        / "TOP100_수익률.csv",

        index=False,

        encoding="utf-8-sig"

    )


    # =================================================================
    # CAGR TOP
    # =================================================================

    top_cagr = (

        result_df

        .sort_values(

            "CAGR",

            ascending=False

        )

        .head(100)

    )


    top_cagr.to_csv(

        OUTPUT_DIR
        / "TOP100_CAGR.csv",

        index=False,

        encoding="utf-8-sig"

    )


    # =================================================================
    # Calmar TOP
    # =================================================================

    top_calmar = (

        result_df

        .dropna(
            subset=["Calmar"]
        )

        .sort_values(

            "Calmar",

            ascending=False

        )

        .head(100)

    )


    top_calmar.to_csv(

        OUTPUT_DIR
        / "TOP100_Calmar.csv",

        index=False,

        encoding="utf-8-sig"

    )


    # =================================================================
    # MDD -20% 이내
    # =================================================================

    top_mdd20 = (

        result_df[
            result_df["MDD"]
            >= -0.20
        ]

        .sort_values(

            "CAGR",

            ascending=False

        )

        .head(100)

    )


    top_mdd20.to_csv(

        OUTPUT_DIR
        / "TOP100_MDD20.csv",

        index=False,

        encoding="utf-8-sig"

    )


    # =================================================================
    # MDD -30% 이내
    # =================================================================

    top_mdd30 = (

        result_df[
            result_df["MDD"]
            >= -0.30
        ]

        .sort_values(

            "CAGR",

            ascending=False

        )

        .head(100)

    )


    top_mdd30.to_csv(

        OUTPUT_DIR
        / "TOP100_MDD30.csv",

        index=False,

        encoding="utf-8-sig"

    )


    return {

        "return":
            top_return,

        "cagr":
            top_cagr,

        "calmar":
            top_calmar,

        "mdd20":
            top_mdd20,

        "mdd30":
            top_mdd30,

    }


# ====================================================================
# 11. Walk-Forward Optimization
# ====================================================================

def walk_forward(
    df
):

    print()
    print("=" * 80)
    print("Walk-Forward Optimization")
    print("=" * 80)


    # =================================================================
    # 1단계
    #
    # Train
    # 2016 ~ 2022
    #
    # Test
    # 2023 ~ 현재
    # =================================================================

    train = df[
        df["날짜"]
        <= "2022-12-31"
    ].copy()


    test = df[
        df["날짜"]
        >= "2023-01-01"
    ].copy()


    print()
    print(
        "TRAIN : "
        f"{train['날짜'].min().date()}"
        " ~ "
        f"{train['날짜'].max().date()}"
    )


    print(
        "TEST  : "
        f"{test['날짜'].min().date()}"
        " ~ "
        f"{test['날짜'].max().date()}"
    )


    # =================================================================
    # Train 최적화
    # =================================================================

    train_results = optimize(
        train
    )


    # =================================================================
    # Train 기준 최고 전략
    # =================================================================

    best_train = (

        train_results

        .sort_values(

            "CAGR",

            ascending=False

        )

        .iloc[0]

    )


    # =================================================================
    # 최적 파라미터
    # =================================================================

    buy_interval = (
        best_train["매수간격"]
    )

    sell_interval = (
        best_train["매도간격"]
    )

    buy_amount = (
        best_train["1회매수금액"]
    )

    max_investment = (
        best_train["최대투자금"]
    )

    max_shares = (
        best_train["최대보유주식"]
    )


    # =================================================================
    # Test
    # =================================================================

    test_result = (
        backtest_pyramid(

            df=test,

            buy_interval=buy_interval,

            sell_interval=sell_interval,

            buy_amount=buy_amount,

            max_investment=max_investment,

            max_shares=max_shares,

        )
    )


    # =================================================================
    # 결과
    # =================================================================

    wf_result = {

        "Train_시작":
            train["날짜"].min(),

        "Train_종료":
            train["날짜"].max(),

        "Test_시작":
            test["날짜"].min(),

        "Test_종료":
            test["날짜"].max(),

        "매수간격":
            buy_interval,

        "매도간격":
            sell_interval,

        "1회매수금액":
            buy_amount,

        "최대투자금":
            max_investment,

        "최대보유주식":
            max_shares,

        "Train_최종자산":
            best_train["최종자산"],

        "Train_CAGR":
            best_train["CAGR"],

        "Train_MDD":
            best_train["MDD"],

        "Train_Calmar":
            best_train["Calmar"],

        "Test_최종자산":
            test_result["최종자산"],

        "Test_총수익률":
            test_result["총수익률"],

        "Test_CAGR":
            test_result["CAGR"],

        "Test_MDD":
            test_result["MDD"],

        "Test_Calmar":
            test_result["Calmar"],

        "Test_Sharpe":
            test_result["Sharpe"],

        "Test_매수횟수":
            test_result["매수횟수"],

        "Test_매도횟수":
            test_result["매도횟수"],

    }


    wf_df = pd.DataFrame(
        [wf_result]
    )


    wf_df.to_csv(

        OUTPUT_DIR
        / "WalkForward_결과.csv",

        index=False,

        encoding="utf-8-sig"

    )


    return wf_df


# ====================================================================
# 12. 최적전략 거래내역
# ====================================================================

def save_best_strategy_trades(
    df,
    result_df
):

    best = (

        result_df

        .sort_values(

            "CAGR",

            ascending=False

        )

        .iloc[0]

    )


    result = backtest_pyramid(

        df=df,

        buy_interval=best["매수간격"],

        sell_interval=best["매도간격"],

        buy_amount=best["1회매수금액"],

        max_investment=best["최대투자금"],

        max_shares=best["최대보유주식"],

        record_trades=True,

    )


    metrics, trades, equity = result


    trades.to_csv(

        OUTPUT_DIR
        / "거래내역_최고전략.csv",

        index=False,

        encoding="utf-8-sig"

    )


    equity_df = (

        equity

        .rename("자산")

        .reset_index()

    )


    equity_df.columns = [
        "날짜",
        "자산",
    ]


    equity_df.to_csv(

        OUTPUT_DIR
        / "자산곡선_최고전략.csv",

        index=False,

        encoding="utf-8-sig"

    )


# ====================================================================
# 13. 콘솔 결과 출력
# ====================================================================

def print_summary(
    result_df
):

    print()
    print("=" * 100)
    print("TQQQ 피라미드 전략 최적화 결과")
    print("=" * 100)


    # =================================================================
    # 최고 수익률
    # =================================================================

    print()
    print("■ 총수익률 TOP 10")

    print(

        result_df

        .sort_values(

            "총수익률",

            ascending=False

        )

        .head(10)

        .to_string(

            index=False

        )

    )


    # =================================================================
    # 최고 CAGR
    # =================================================================

    print()
    print("■ CAGR TOP 10")

    print(

        result_df

        .sort_values(

            "CAGR",

            ascending=False

        )

        .head(10)

        .to_string(

            index=False

        )

    )


    # =================================================================
    # MDD -20%
    # =================================================================

    print()
    print("■ MDD -20% 이내 CAGR TOP 10")

    mdd20 = result_df[
        result_df["MDD"] >= -0.20
    ]


    print(

        mdd20

        .sort_values(

            "CAGR",

            ascending=False

        )

        .head(10)

        .to_string(

            index=False

        )

    )


    # =================================================================
    # MDD -30%
    # =================================================================

    print()
    print("■ MDD -30% 이내 CAGR TOP 10")

    mdd30 = result_df[
        result_df["MDD"] >= -0.30
    ]


    print(

        mdd30

        .sort_values(

            "CAGR",

            ascending=False

        )

        .head(10)

        .to_string(

            index=False

        )

    )


    # =================================================================
    # Calmar
    # =================================================================

    print()
    print("■ Calmar TOP 10")

    print(

        result_df

        .sort_values(

            "Calmar",

            ascending=False

        )

        .head(10)

        .to_string(

            index=False

        )

    )


# ====================================================================
# 14. Main
# ====================================================================

def main():

    print()
    print("=" * 100)
    print("TQQQ PYRAMID STRATEGY OPTIMIZER")
    print("=" * 100)


    print()
    print(
        f"입력 : {INPUT_FILE}"
    )


    print(
        f"출력 : {OUTPUT_DIR}"
    )


    # =================================================================
    # 데이터
    # =================================================================

    df = load_data()


    # =================================================================
    # 기본 전략
    # =================================================================

    base_result = (
        run_base_strategy(df)
    )


    print()
    print("■ 기본전략 결과")

    print(
        pd.DataFrame(
            [base_result]
        ).to_string(
            index=False
        )
    )


    # =================================================================
    # 전체 최적화
    # =================================================================

    result_df = optimize(
        df
    )


    # =================================================================
    # 저장
    # =================================================================

    saved = (
        save_optimization_results(
            result_df
        )
    )


    # =================================================================
    # 최고 전략 거래내역
    # =================================================================

    save_best_strategy_trades(
        df,
        result_df
    )


    # =================================================================
    # 출력
    # =================================================================

    print_summary(
        result_df
    )


    # =================================================================
    # Walk Forward
    # =================================================================

    wf_df = walk_forward(
        df
    )


    print()
    print("=" * 100)
    print("Walk-Forward 결과")
    print("=" * 100)

    print(
        wf_df.to_string(
            index=False
        )
    )


    # =================================================================
    # 완료
    # =================================================================

    print()
    print("=" * 100)
    print("최적화 완료")
    print("=" * 100)

    print()
    print(
        f"결과 폴더:\n"
        f"{OUTPUT_DIR}"
    )


# ====================================================================
# 실행
# ====================================================================

if __name__ == "__main__":

    main()

