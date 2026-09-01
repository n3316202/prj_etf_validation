"""
============================================================
jp_etf_backtest.py
============================================================

목적
------------------------------------------------------------
이미 다운로드된 일본 ETF CSV 데이터를 이용해서
N년 이상 운용된 ETF만 골라 백테스트한다.

다운로드 기능 없음.
Yahoo Finance 호출 없음.

사용자는 MIN_YEARS만 변경하면 된다.

예:
    MIN_YEARS = 5
    MIN_YEARS = 10
    MIN_YEARS = 15


백테스트
------------------------------------------------------------
① 2016-01-01 ~ 현재 공통기간 비교
② 일시투자 20,000,000원
③ 월적립 1,000,000원
④ CAGR
⑤ MDD
⑥ Sharpe
⑦ 변동성
⑧ 총수익률
⑨ 월적립 XIRR
⑩ 종합점수


데이터
------------------------------------------------------------
data/
 ├── 일본_ETF_Universe.csv
 │
 └── jp_etf/
      ├── 1306.csv
      ├── 1321.csv
      ├── 1570.csv
      ├── 2558.csv
      ├── 2869.csv
      └── ...


결과
------------------------------------------------------------
results/
 ├── 일본_ETF_10년이상_백테스트_원본.csv
 ├── 일본_ETF_10년이상_백테스트.csv
 ├── 일본_ETF_10년이상_TOP50.csv
 ├── 일본_ETF_10년이상_CAGR_TOP50.csv
 ├── 일본_ETF_10년이상_MDD_TOP50.csv
 └── 일본_ETF_10년이상_월적립_TOP50.csv

============================================================
"""

from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd


# ============================================================
# 1. 사용자 설정
# ============================================================

# ★ 이것만 변경하면 됩니다.
MIN_YEARS = 1


# ============================================================
# 공통 백테스트 기간
# ============================================================

BACKTEST_START = "2016-01-01"

BACKTEST_END = (
    datetime.now().strftime("%Y-%m-%d")
)


# ============================================================
# 투자금
# ============================================================

LUMP_SUM = 20_000_000

MONTHLY_INVESTMENT = 1_000_000


# ============================================================
# 데이터 위치
# ============================================================

DATA_DIR = Path(
    "data/jp_etf"
)


UNIVERSE_FILE = Path(
    "data/일본_ETF_Universe.csv"
)


RESULT_DIR = Path(
    "results"
)


RESULT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# 2. 일본 ETF Universe
# ============================================================

def load_universe():

    if not UNIVERSE_FILE.exists():

        print(
            "⚠ 일본 ETF Universe 파일이 없습니다."
        )

        print(
            f"필요 파일: {UNIVERSE_FILE}"
        )

        return pd.DataFrame()


    try:

        df = pd.read_csv(
            UNIVERSE_FILE,
            dtype={
                "티커": str
            }
        )

    except Exception as e:

        print(
            "Universe 읽기 실패:"
        )

        print(e)

        return pd.DataFrame()


    if df.empty:

        return pd.DataFrame()


    # --------------------------------------------------------
    # 일본 ETF 티커는 숫자형이 많으므로 문자열 처리
    # --------------------------------------------------------

    df["티커"] = (
        df["티커"]
        .astype(str)
        .str.strip()
    )

    # 1234.0 형태 방지
    df["티커"] = (
        df["티커"]
        .str.replace(
            r"\.0$",
            "",
            regex=True
        )
    )

    return df


# ============================================================
# 3. ETF CSV 목록
# ============================================================

def get_local_etf_files():

    if not DATA_DIR.exists():

        print(
            f"❌ 데이터 폴더가 없습니다: "
            f"{DATA_DIR}"
        )

        return []


    files = list(
        DATA_DIR.glob("*.csv")
    )


    print()

    print(
        f"로컬 일본 ETF CSV : "
        f"{len(files):,}개"
    )


    return files


# ============================================================
# 4. ETF 데이터 읽기
# ============================================================

def load_price_data(
    ticker
):

    filename = (
        DATA_DIR
        / f"{ticker}.csv"
    )


    if not filename.exists():

        return None


    try:

        df = pd.read_csv(
            filename
        )

    except Exception:

        return None


    if df.empty:

        return None


    # ========================================================
    # 날짜 컬럼
    # ========================================================

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

            return None


    # ========================================================
    # 수정주가
    # ========================================================

    if "수정주가" not in df.columns:

        if "Adj Close" in df.columns:

            df = df.rename(
                columns={
                    "Adj Close": "수정주가"
                }
            )

        elif "종가" in df.columns:

            df["수정주가"] = (
                df["종가"]
            )

        elif "Close" in df.columns:

            df["수정주가"] = (
                df["Close"]
            )

        else:

            return None


    # ========================================================
    # 날짜 변환
    # ========================================================

    df["날짜"] = pd.to_datetime(

        df["날짜"],

        errors="coerce"

    )


    # ========================================================
    # 가격 변환
    # ========================================================

    df["수정주가"] = pd.to_numeric(

        df["수정주가"],

        errors="coerce"

    )


    # ========================================================
    # 결측 제거
    # ========================================================

    df = df.dropna(

        subset=[
            "날짜",
            "수정주가"
        ]

    )


    if df.empty:

        return None


    # ========================================================
    # 가격 <= 0 제거
    # ========================================================

    df = df[
        df["수정주가"] > 0
    ].copy()


    # ========================================================
    # 정렬
    # ========================================================

    df = df.sort_values(
        "날짜"
    )


    # ========================================================
    # 중복 제거
    # ========================================================

    df = df.drop_duplicates(

        subset=[
            "날짜"
        ],

        keep="last"

    )


    return df.reset_index(
        drop=True
    )


# ============================================================
# 5. ETF 운용기간
# ============================================================

def get_etf_period(
    df
):

    if df is None or df.empty:

        return None


    first_date = (
        df["날짜"].min()
    )


    last_date = (
        df["날짜"].max()
    )


    years = (

        last_date
        - first_date

    ).days / 365.25


    return {

        "start":
            first_date,

        "end":
            last_date,

        "years":
            years

    }


# ============================================================
# 6. N년 이상 ETF 필터
# ============================================================

def filter_by_min_years(
    universe,
    min_years
):

    print()

    print("=" * 110)

    print(
        f"ETF 운용기간 필터 : "
        f"{min_years}년 이상"
    )

    print("=" * 110)


    valid = []


    total = len(
        universe
    )


    for index, row in universe.iterrows():

        ticker = str(
            row["티커"]
        ).strip()


        df = load_price_data(
            ticker
        )


        if df is None:

            continue


        period = get_etf_period(
            df
        )


        if period is None:

            continue


        if (
            period["years"]
            >= min_years
        ):

            item = row.to_dict()


            item[
                "데이터_시작일"
            ] = (
                period["start"].date()
            )


            item[
                "데이터_종료일"
            ] = (
                period["end"].date()
            )


            item[
                "데이터_기간년"
            ] = round(
                period["years"],
                2
            )


            valid.append(
                item
            )


    result = pd.DataFrame(
        valid
    )


    print()

    print(
        f"전체 Universe : "
        f"{total:,}개"
    )


    print(
        f"{min_years}년 이상 : "
        f"{len(result):,}개"
    )


    if result.empty:

        return result


    result = result.sort_values(

        "데이터_시작일"

    )


    result = result.reset_index(
        drop=True
    )


    return result


# ============================================================
# 7. 공통기간
# ============================================================

def prepare_common_period(
    df
):

    start = pd.Timestamp(
        BACKTEST_START
    )


    end = pd.Timestamp(
        BACKTEST_END
    )


    data = df[

        (
            df["날짜"]
            >= start
        )

        &

        (
            df["날짜"]
            <= end
        )

    ].copy()


    if data.empty:

        return None


    data = data.sort_values(
        "날짜"
    )


    return data.reset_index(
        drop=True
    )


# ============================================================
# 8. CAGR
# ============================================================

def calculate_cagr(
    initial,
    final,
    years
):

    if (

        initial <= 0
        or final <= 0
        or years <= 0

    ):

        return np.nan


    return (

        final / initial

    ) ** (

        1 / years

    ) - 1


# ============================================================
# 9. MDD
# ============================================================

def calculate_mdd(
    equity
):

    equity = pd.Series(
        equity
    ).dropna()


    if equity.empty:

        return np.nan


    peak = equity.cummax()


    drawdown = (

        equity / peak

    ) - 1


    return float(
        drawdown.min()
    )


# ============================================================
# 10. 변동성
# ============================================================

def calculate_volatility(
    returns
):

    returns = pd.Series(
        returns
    ).dropna()


    if len(returns) < 2:

        return np.nan


    return float(

        returns.std()
        * np.sqrt(252)

    )


# ============================================================
# 11. Sharpe
# ============================================================

def calculate_sharpe(
    returns
):

    returns = pd.Series(
        returns
    ).dropna()


    if len(returns) < 2:

        return np.nan


    std = returns.std()


    if (

        std == 0
        or pd.isna(std)

    ):

        return np.nan


    # 무위험수익률 0%
    return float(

        returns.mean()
        / std
        * np.sqrt(252)

    )


# ============================================================
# 12. 일시투자
# ============================================================

def backtest_lump_sum(
    df
):

    if (

        df is None
        or len(df) < 2

    ):

        return None


    price = (

        df["수정주가"]
        .astype(float)

    )


    dates = df["날짜"]


    start_price = float(
        price.iloc[0]
    )


    end_price = float(
        price.iloc[-1]
    )


    start_date = (
        dates.iloc[0]
    )


    end_date = (
        dates.iloc[-1]
    )


    years = (

        end_date
        - start_date

    ).days / 365.25


    # ========================================================
    # 최종금액
    # ========================================================

    final_value = (

        LUMP_SUM
        * end_price
        / start_price

    )


    # ========================================================
    # 총수익률
    # ========================================================

    total_return = (

        final_value
        / LUMP_SUM

    ) - 1


    # ========================================================
    # CAGR
    # ========================================================

    cagr = calculate_cagr(

        LUMP_SUM,

        final_value,

        years

    )


    # ========================================================
    # 자산곡선
    # ========================================================

    equity = (

        LUMP_SUM
        * price
        / start_price

    )


    # ========================================================
    # MDD
    # ========================================================

    mdd = calculate_mdd(
        equity
    )


    # ========================================================
    # 일별 수익률
    # ========================================================

    returns = (

        price
        .pct_change()
        .dropna()

    )


    volatility = (
        calculate_volatility(
            returns
        )
    )


    sharpe = (
        calculate_sharpe(
            returns
        )
    )


    return {

        "시작일":
            start_date.date(),

        "종료일":
            end_date.date(),

        "기간년":
            years,

        "최종금액":
            final_value,

        "수익금":
            final_value
            - LUMP_SUM,

        "총수익률":
            total_return,

        "CAGR":
            cagr,

        "MDD":
            mdd,

        "변동성":
            volatility,

        "Sharpe":
            sharpe,

    }


# ============================================================
# 13. XNPV
# ============================================================

def xnpv(
    rate,
    cashflows
):

    if rate <= -1:

        return np.nan


    first_date = (
        cashflows[0][0]
    )


    total = 0.0


    for date, amount in cashflows:

        years = (

            date
            - first_date

        ).days / 365.25


        total += (

            amount
            /
            (
                (1 + rate)
                ** years
            )

        )


    return total


# ============================================================
# 14. XIRR
# ============================================================

def calculate_xirr(
    cashflows
):

    if len(cashflows) < 2:

        return np.nan


    amounts = [

        x[1]
        for x in cashflows

    ]


    if not any(
        x < 0
        for x in amounts
    ):

        return np.nan


    if not any(
        x > 0
        for x in amounts
    ):

        return np.nan


    low = -0.9999

    high = 10.0


    low_value = xnpv(
        low,
        cashflows
    )


    high_value = xnpv(
        high,
        cashflows
    )


    # --------------------------------------------------------
    # 구간 확장
    # --------------------------------------------------------

    for _ in range(50):

        if (

            np.sign(low_value)
            != np.sign(high_value)

        ):

            break


        high *= 2


        high_value = xnpv(

            high,

            cashflows

        )


    if (

        np.sign(low_value)
        == np.sign(high_value)

    ):

        return np.nan


    # --------------------------------------------------------
    # Bisection
    # --------------------------------------------------------

    for _ in range(200):

        mid = (

            low + high
        ) / 2


        mid_value = xnpv(

            mid,

            cashflows

        )


        if abs(
            mid_value
        ) < 1e-7:

            return float(mid)


        if (

            np.sign(mid_value)
            == np.sign(low_value)

        ):

            low = mid

        else:

            high = mid


    return float(

        (low + high)
        / 2

    )


# ============================================================
# 15. 월 100만원 적립식
# ============================================================

def backtest_monthly(
    df
):

    if (

        df is None
        or len(df) < 2

    ):

        return None


    data = df[

        [
            "날짜",
            "수정주가"
        ]

    ].copy()


    data = data.set_index(
        "날짜"
    )


    data = data.sort_index()


    # ========================================================
    # 매월 첫 거래일
    # ========================================================

    monthly = (

        data["수정주가"]

        .resample("MS")

        .first()

        .dropna()

    )


    if len(monthly) < 2:

        return None


    shares = 0.0

    invested = 0.0


    equity = []


    cashflows = []


    # ========================================================
    # 월별 투자
    # ========================================================

    for date, price in monthly.items():

        price = float(
            price
        )


        shares += (

            MONTHLY_INVESTMENT
            / price

        )


        invested += (
            MONTHLY_INVESTMENT
        )


        equity.append({

            "날짜":
                date,

            "평가금액":
                shares * price

        })


        cashflows.append((

            date.to_pydatetime(),

            -MONTHLY_INVESTMENT

        ))


    # ========================================================
    # 마지막 거래일
    # ========================================================

    last_date = (
        data.index[-1]
    )


    last_price = float(

        data[
            "수정주가"
        ].iloc[-1]

    )


    final_value = (

        shares
        * last_price

    )


    cashflows.append((

        last_date.to_pydatetime(),

        final_value

    ))


    # ========================================================
    # 수익
    # ========================================================

    profit = (

        final_value
        - invested

    )


    return_rate = (

        final_value
        / invested

    ) - 1


    # ========================================================
    # XIRR
    # ========================================================

    xirr = calculate_xirr(
        cashflows
    )


    # ========================================================
    # MDD
    # ========================================================

    equity_df = pd.DataFrame(
        equity
    )


    mdd = calculate_mdd(

        equity_df[
            "평가금액"
        ]

    )


    return {

        "월적립_시작일":
            data.index[0].date(),

        "월적립_종료일":
            last_date.date(),

        "월적립_납입개월":
            len(monthly),

        "월적립_납입원금":
            invested,

        "월적립_최종금액":
            final_value,

        "월적립_수익금":
            profit,

        "월적립_수익률":
            return_rate,

        "월적립_XIRR":
            xirr,

        "월적립_MDD":
            mdd,

    }


# ============================================================
# 16. 종합 Ranking
# ============================================================

def create_ranking(
    df
):

    result = df.copy()


    # ========================================================
    # CAGR
    # ========================================================

    result["CAGR_Rank"] = (

        result["CAGR"]
        .rank(
            ascending=False,
            method="min"
        )

    )


    # ========================================================
    # Sharpe
    # ========================================================

    result["Sharpe_Rank"] = (

        result["Sharpe"]
        .rank(
            ascending=False,
            method="min"
        )

    )


    # ========================================================
    # MDD
    # ========================================================

    result["MDD_Rank"] = (

        result["MDD"]
        .rank(
            ascending=False,
            method="min"
        )

    )


    n = len(result)


    def score(rank):

        if pd.isna(rank):

            return np.nan


        if n <= 1:

            return 100


        return (

            1
            -
            (
                rank - 1
            )
            /
            (
                n - 1
            )

        ) * 100


    # ========================================================
    # 점수
    # ========================================================

    result["CAGR_Score"] = (

        result["CAGR_Rank"]
        .apply(score)

    )


    result["Sharpe_Score"] = (

        result["Sharpe_Rank"]
        .apply(score)

    )


    result["MDD_Score"] = (

        result["MDD_Rank"]
        .apply(score)

    )


    # ========================================================
    # 종합점수
    # ========================================================

    result["종합점수"] = (

        result["CAGR_Score"]
        * 0.50

        +

        result["Sharpe_Score"]
        * 0.30

        +

        result["MDD_Score"]
        * 0.20

    )


    result = result.sort_values(

        "종합점수",

        ascending=False,

        na_position="last"

    )


    result = result.reset_index(
        drop=True
    )


    result.insert(

        0,

        "종합순위",

        range(
            1,
            len(result) + 1
        )

    )


    return result


# ============================================================
# 17. 결과 표시용
# ============================================================

def format_result(
    df
):

    result = df.copy()


    percent_columns = [

        "총수익률",

        "CAGR",

        "MDD",

        "변동성",

        "월적립_수익률",

        "월적립_XIRR",

        "월적립_MDD",

    ]


    for column in percent_columns:

        if column in result.columns:

            result[column] = (

                result[column]
                * 100
            ).round(2)


    money_columns = [

        "최종금액",

        "수익금",

        "월적립_납입원금",

        "월적립_최종금액",

        "월적립_수익금",

    ]


    for column in money_columns:

        if column in result.columns:

            result[column] = (

                result[column]
                .round(0)

            )


    result["종합점수"] = (

        result["종합점수"]
        .round(2)

    )


    return result


# ============================================================
# 18. 메인
# ============================================================

def main():

    print()

    print("=" * 120)

    print(
        "🇯🇵 일본 ETF N년 이상 백테스트"
    )

    print("=" * 120)


    print(
        f"최소 운용기간 : "
        f"{MIN_YEARS}년"
    )


    print(
        f"공통 백테스트 : "
        f"{BACKTEST_START} ~ "
        f"{BACKTEST_END}"
    )


    print(
        f"일시투자 : "
        f"{LUMP_SUM:,}원"
    )


    print(
        f"월적립 : "
        f"{MONTHLY_INVESTMENT:,}원"
    )


    print("=" * 120)


    # ========================================================
    # Universe
    # ========================================================

    universe = load_universe()


    if universe.empty:

        raise RuntimeError(

            "일본 ETF Universe가 없습니다."

        )


    # ========================================================
    # N년 필터
    # ========================================================

    filtered = filter_by_min_years(

        universe,

        MIN_YEARS

    )


    if filtered.empty:

        raise RuntimeError(

            f"{MIN_YEARS}년 이상 "
            "ETF가 없습니다."

        )


    # ========================================================
    # 백테스트
    # ========================================================

    results = []


    total = len(
        filtered
    )


    print()

    print("=" * 120)

    print(
        "백테스트 시작"
    )

    print("=" * 120)


    for index, row in filtered.iterrows():

        ticker = str(
            row["티커"]
        ).strip()


        print(

            f"[{index + 1}/{total}] "
            f"{ticker} | "
            f"{row.get('ETF명', '')}"

        )


        df = load_price_data(
            ticker
        )


        if df is None:

            print(
                "  ❌ 데이터 없음"
            )

            continue


        # ====================================================
        # 공통기간
        # ====================================================

        test_df = prepare_common_period(
            df
        )


        if (

            test_df is None
            or len(test_df) < 2

        ):

            print(
                "  ❌ 공통기간 데이터 없음"
            )

            continue


        # ====================================================
        # 일시투자
        # ====================================================

        lump = backtest_lump_sum(
            test_df
        )


        # ====================================================
        # 월적립
        # ====================================================

        monthly = backtest_monthly(
            test_df
        )


        if lump is None:

            continue


        result = {

            "티커":
                ticker,

            "ETF명":
                row.get(
                    "ETF명",
                    ""
                ),

            "거래소":
                row.get(
                    "거래소",
                    ""
                ),

            "ETF_데이터시작":
                row.get(
                    "데이터_시작일",
                    ""
                ),

            "ETF_운용기간년":
                row.get(
                    "데이터_기간년",
                    np.nan
                ),

        }


        result.update(
            lump
        )


        if monthly:

            result.update(
                monthly
            )


        results.append(
            result
        )


    # ========================================================
    # 결과 DataFrame
    # ========================================================

    result_df = pd.DataFrame(
        results
    )


    if result_df.empty:

        raise RuntimeError(

            "백테스트 결과가 없습니다."

        )


    # ========================================================
    # Ranking
    # ========================================================

    result_df = create_ranking(
        result_df
    )


    # ========================================================
    # 파일명
    # ========================================================

    prefix = (

        f"일본_ETF_"
        f"{MIN_YEARS}년이상"

    )


    # ========================================================
    # 원본
    # ========================================================

    raw_file = (

        RESULT_DIR
        /
        f"{prefix}_백테스트_원본.csv"

    )


    result_df.to_csv(

        raw_file,

        index=False,

        encoding="utf-8-sig"

    )


    # ========================================================
    # 표시용
    # ========================================================

    display_df = format_result(
        result_df
    )


    # ========================================================
    # 전체 Ranking
    # ========================================================

    ranking_file = (

        RESULT_DIR
        /
        f"{prefix}_백테스트.csv"

    )


    display_df.to_csv(

        ranking_file,

        index=False,

        encoding="utf-8-sig"

    )


    # ========================================================
    # TOP 50
    # ========================================================

    top50 = display_df.head(
        50
    )


    top50_file = (

        RESULT_DIR
        /
        f"{prefix}_TOP50.csv"

    )


    top50.to_csv(

        top50_file,

        index=False,

        encoding="utf-8-sig"

    )


    # ========================================================
    # CAGR TOP 50
    # ========================================================

    cagr_top50 = (

        display_df
        .sort_values(
            "CAGR",
            ascending=False
        )
        .head(50)

    )


    cagr_file = (

        RESULT_DIR
        /
        f"{prefix}_CAGR_TOP50.csv"

    )


    cagr_top50.to_csv(

        cagr_file,

        index=False,

        encoding="utf-8-sig"

    )


    # ========================================================
    # MDD TOP 50
    # ========================================================

    mdd_top50 = (

        display_df
        .sort_values(
            "MDD",
            ascending=False
        )
        .head(50)

    )


    mdd_file = (

        RESULT_DIR
        /
        f"{prefix}_MDD_TOP50.csv"

    )


    mdd_top50.to_csv(

        mdd_file,

        index=False,

        encoding="utf-8-sig"

    )


    # ========================================================
    # 월적립 TOP 50
    # ========================================================

    monthly_top50 = (

        display_df
        .sort_values(
            "월적립_XIRR",
            ascending=False
        )
        .head(50)

    )


    monthly_file = (

        RESULT_DIR
        /
        f"{prefix}_월적립_TOP50.csv"

    )


    monthly_top50.to_csv(

        monthly_file,

        index=False,

        encoding="utf-8-sig"

    )


    # ========================================================
    # 화면 출력
    # ========================================================

    print()

    print("=" * 160)

    print(

        f"🏆 {MIN_YEARS}년 이상 일본 ETF "
        "종합 TOP 50"

    )

    print("=" * 160)


    columns = [

        "종합순위",

        "티커",

        "ETF명",

        "ETF_운용기간년",

        "최종금액",

        "CAGR",

        "MDD",

        "Sharpe",

        "월적립_최종금액",

        "월적립_XIRR",

        "종합점수",

    ]


    available_columns = [

        col
        for col in columns
        if col in display_df.columns

    ]


    print(

        display_df[
            available_columns
        ]
        .head(50)
        .to_string(
            index=False
        )

    )


    # ========================================================
    # 저장 결과
    # ========================================================

    print()

    print("=" * 160)

    print(
        "📁 결과 파일"
    )

    print("=" * 160)


    print(
        raw_file
    )


    print(
        ranking_file
    )


    print(
        top50_file
    )


    print(
        cagr_file
    )


    print(
        mdd_file
    )


    print(
        monthly_file
    )


    print("=" * 160)


# ============================================================
# 실행
# ============================================================

if __name__ == "__main__":

    main()