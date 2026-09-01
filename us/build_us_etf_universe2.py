import io
import os
import requests
import pandas as pd
import yfinance as yf

import time
from pathlib import Path
from datetime import datetime


# ============================================================
# ETF Universe 설정
# ============================================================

START_DATE = "2016-01-01"

END_DATE = datetime.now().strftime(
    "%Y-%m-%d"
)

# 요청 간격
REQUEST_SLEEP = 0.5

DATA_DIR = Path("data/us_etf")

# NASDAQ Trader 직접 접속을 사용하지 않습니다.
# ETF Universe는 Yahoo Finance Screener(yfinance ETFQuery)를 사용합니다.

YAHOO_SCREEN_SIZE = 250
YAHOO_SCREEN_MAX_PAGES = 100


# ============================================================
# HTTP Header
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/151.0 Safari/537.36"
    )
}

def flatten_columns(df):

    if not isinstance(
        df.columns,
        pd.MultiIndex
    ):
        return df

    new_columns = []

    for column in df.columns:

        # 예:
        # ('Open', 'TQQQ')
        #
        # → Open

        if isinstance(column, tuple):

            first = str(
                column[0]
            ).strip()

            new_columns.append(
                first
            )

        else:

            new_columns.append(
                str(column).strip()
            )

    df.columns = new_columns

    return df

# ============================================================
# Yahoo Finance ETF Universe
# ============================================================

def _empty_universe():

    return pd.DataFrame(
        columns=[
            "티커",
            "ETF명",
            "거래소"
        ]
    )


def _normalize_exchange(exchange):
    """Yahoo Finance 거래소 코드를 기존 Universe용 이름으로 변환."""

    value = str(exchange or "").strip().upper()

    if value in {
        "NMS", "NAS", "NASDAQ", "NCM", "NGM",
        "NQ", "NMQ", "NMS"
    } or "NASDAQ" in value:
        return "NASDAQ"

    if value in {
        "PCX", "ARCX", "NYSEARCA", "ARCA",
        "NYQ", "NYS", "NYSE", "ASE", "AMX",
        "BATS", "BZX", "CBOE", "CBO", "BAT",
        "IEX", "OTC", "OPR"
    }:
        return "OTHER"

    # 이름으로도 한 번 더 판별
    if any(
        key in value
        for key in [
            "NYSE",
            "ARCA",
            "CBOE",
            "BATS",
            "AMERICAN"
        ]
    ):
        return "OTHER"

    # Yahoo가 거래소 코드를 제공하지 않는 ETF도 미국 ETF
    # Universe에 남긴다. 최종 거래소는 OTHER로 처리한다.
    return "OTHER"


def _get_yahoo_etf_universe():
    """
    Yahoo Finance ETF Screener를 이용해 미국 ETF 전체 후보를 가져온다.

    yfinance 1.3.0부터 ETFQuery가 제공되며, Yahoo Screener는 한 번에
    최대 250개를 반환하므로 offset을 증가시키며 반복 조회한다.
    """

    print()
    print("  🔎 Yahoo Finance ETF Screener 조회")

    ETFQuery = getattr(yf, "ETFQuery", None)
    screen = getattr(yf, "screen", None)

    if ETFQuery is None or screen is None:
        raise RuntimeError(
            "현재 설치된 yfinance가 ETFQuery를 지원하지 않습니다.\n"
            "다음 명령으로 업데이트하세요: \n"
            "python -m pip install -U yfinance"
        )

    # 미국 ETF
    query = ETFQuery(
        "eq",
        [
            "region",
            "us"
        ]
    )

    rows = []
    offset = 0

    for page in range(
        1,
        YAHOO_SCREEN_MAX_PAGES + 1
    ):

        try:

            result = yf.screen(
                query,
                offset=offset,
                size=YAHOO_SCREEN_SIZE,
                sortField="ticker",
                sortAsc=True
            )

        except Exception as e:

            raise RuntimeError(
                f"Yahoo Finance ETF Screener 조회 실패 "
                f"(offset={offset}): {e}"
            ) from e

        quotes = []

        if isinstance(result, dict):
            quotes = result.get("quotes", []) or []

        if not quotes:
            break

        for item in quotes:

            symbol = (
                item.get("symbol")
                or item.get("ticker")
            )

            if not symbol:
                continue

            symbol = str(symbol).strip().upper()

            # 미국 ETF만. ETFQuery가 이미 ETF로 제한하지만
            # 응답에 quoteType이 있다면 한 번 더 검증한다.
            quote_type = str(
                item.get("quoteType", "ETF")
            ).upper()

            if quote_type not in {
                "ETF",
                "ETN",
                ""
            }:
                continue

            name = (
                item.get("longName")
                or item.get("shortName")
                or item.get("displayName")
                or symbol
            )

            exchange = (
                item.get("exchange")
                or item.get("fullExchangeName")
                or ""
            )

            rows.append(
                {
                    "티커": symbol,
                    "ETF명": str(name).strip(),
                    "거래소원본": str(exchange).strip(),
                }
            )

        count = len(quotes)

        print(
            f"     페이지 {page:>3} | "
            f"offset={offset:>5} | "
            f"{count:>3}개"
        )

        if count < YAHOO_SCREEN_SIZE:
            break

        offset += YAHOO_SCREEN_SIZE

        time.sleep(0.2)

    if not rows:
        raise RuntimeError(
            "Yahoo Finance ETF Screener에서 ETF 목록을 "
            "가져오지 못했습니다."
        )

    df = pd.DataFrame(rows)

    # 중복 제거
    df = (
        df
        .drop_duplicates(
            subset=["티커"],
            keep="first"
        )
        .reset_index(drop=True)
    )

    # 거래소 표준화
    df["거래소"] = (
        df["거래소원본"]
        .apply(_normalize_exchange)
    )

    df = df[
        [
            "티커",
            "ETF명",
            "거래소"
        ]
    ].copy()

    return df


def _add_required_etfs(df):
    """
    Yahoo Screener 응답에서 누락될 수 있는 주요 ETF를 보완한다.

    Universe 자체를 특정 ETF 목록으로 제한하는 것이 아니라,
    스크리너 누락 시 최소한 핵심 ETF가 빠지지 않도록 하는 보완 단계다.
    """

    required = {
        # NASDAQ
        "QQQ": ("Invesco QQQ Trust", "NASDAQ"),
        "TQQQ": ("ProShares UltraPro QQQ", "NASDAQ"),
        "QLD": ("ProShares Ultra QQQ", "NASDAQ"),
        "SQQQ": ("ProShares UltraPro Short QQQ", "NASDAQ"),
        "PSQ": ("ProShares Short QQQ", "NASDAQ"),
        "SOXX": ("iShares Semiconductor ETF", "NASDAQ"),
        "SMH": ("VanEck Semiconductor ETF", "NASDAQ"),
        # 기타 주요 미국 ETF
        "SPY": ("SPDR S&P 500 ETF Trust", "OTHER"),
        "VOO": ("Vanguard S&P 500 ETF", "OTHER"),
        "IVV": ("iShares Core S&P 500 ETF", "OTHER"),
        "VTI": ("Vanguard Total Stock Market ETF", "OTHER"),
        "IWM": ("iShares Russell 2000 ETF", "OTHER"),
        "DIA": ("SPDR Dow Jones Industrial Average ETF Trust", "OTHER"),
        "XLK": ("Technology Select Sector SPDR Fund", "OTHER"),
        "XLF": ("Financial Select Sector SPDR Fund", "OTHER"),
    }

    existing = set(
        df["티커"].astype(str).str.upper()
    ) if not df.empty else set()

    additions = []

    for ticker, (name, exchange) in required.items():

        if ticker not in existing:

            additions.append(
                {
                    "티커": ticker,
                    "ETF명": name,
                    "거래소": exchange
                }
            )

    if additions:

        df = pd.concat(
            [
                df,
                pd.DataFrame(additions)
            ],
            ignore_index=True
        )

    return (
        df
        .drop_duplicates(
            subset=["티커"],
            keep="first"
        )
        .reset_index(drop=True)
    )


# ============================================================
# Nasdaq Listed ETF
# ============================================================

def get_nasdaq_etf():

    print()
    print("-" * 70)
    print("① Nasdaq 상장 ETF 조회")
    print("-" * 70)

    df = _get_yahoo_etf_universe()
    df = _add_required_etfs(df)

    result = df[
        df["거래소"] == "NASDAQ"
    ].copy()

    result = (
        result
        .drop_duplicates(
            subset=["티커"]
        )
        .sort_values("티커")
        .reset_index(drop=True)
    )

    print()
    print(
        f"Nasdaq ETF : "
        f"{len(result):,}개"
    )

    # TQQQ 확인
    tqqq = result[
        result["티커"] == "TQQQ"
    ]

    print()

    if not tqqq.empty:

        print("✅ TQQQ 발견!")
        print(
            tqqq.to_string(
                index=False
            )
        )

    else:

        print(
            "⚠ TQQQ가 NASDAQ ETF 목록에 없습니다."
        )

    return result


# ============================================================
# Other Listed ETF
# ============================================================

def get_other_etf():

    print()
    print("-" * 70)
    print("② 기타 거래소 상장 ETF 조회")
    print("-" * 70)

    df = _get_yahoo_etf_universe()
    df = _add_required_etfs(df)

    result = df[
        df["거래소"] != "NASDAQ"
    ].copy()

    result = (
        result
        .drop_duplicates(
            subset=["티커"]
        )
        .sort_values("티커")
        .reset_index(drop=True)
    )

    print()
    print(
        f"Other Listed ETF : "
        f"{len(result):,}개"
    )

    return result


# ============================================================
# 미국 ETF Universe
# ============================================================

def get_us_etf_universe():

    print()
    print("=" * 70)
    print("🇺🇸 미국 ETF Universe 생성")
    print("=" * 70)
    print("NASDAQ Trader 직접 접속 없이 Yahoo Finance로 생성합니다.")

    # --------------------------------------------------------
    # Yahoo에서 한 번만 전체 ETF 조회
    # --------------------------------------------------------

    all_df = _get_yahoo_etf_universe()
    all_df = _add_required_etfs(all_df)

    # --------------------------------------------------------
    # Nasdaq / 기타 거래소 분리
    # --------------------------------------------------------

    nasdaq_df = (
        all_df[
            all_df["거래소"] == "NASDAQ"
        ]
        .copy()
        .sort_values("티커")
        .reset_index(drop=True)
    )

    other_df = (
        all_df[
            all_df["거래소"] != "NASDAQ"
        ]
        .copy()
        .sort_values("티커")
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # 합치기
    # --------------------------------------------------------

    df = pd.concat(
        [
            nasdaq_df,
            other_df
        ],
        ignore_index=True
    )

    # --------------------------------------------------------
    # 티커 정리
    # --------------------------------------------------------

    df["티커"] = (
        df["티커"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    # --------------------------------------------------------
    # 빈 티커 제거
    # --------------------------------------------------------

    df = df[
        df["티커"].notna()
        & (df["티커"] != "")
        & (df["티커"] != "NAN")
    ].copy()

    # --------------------------------------------------------
    # 중복 제거
    # --------------------------------------------------------

    df = (
        df
        .drop_duplicates(
            subset=["티커"],
            keep="first"
        )
        .sort_values("티커")
        .reset_index(drop=True)
    )

    # ========================================================
    # TQQQ 최종 확인
    # ========================================================

    tqqq = df[
        df["티커"] == "TQQQ"
    ]

    print()
    print("=" * 70)
    print("🔎 TQQQ 최종 확인")
    print("=" * 70)

    if not tqqq.empty:

        print(
            "✅ TQQQ가 Universe에 포함되었습니다."
        )

        print()
        print(
            tqqq.to_string(
                index=False
            )
        )

    else:

        print(
            "❌ TQQQ가 Universe에 없습니다."
        )

    # ========================================================
    # 저장
    # ========================================================

    os.makedirs(
        "data",
        exist_ok=True
    )

    filename = (
        "data/"
        "미국_ETF_Universe.csv"
    )

    df.to_csv(
        filename,
        index=False,
        encoding="utf-8-sig"
    )

    # ========================================================
    # 결과
    # ========================================================

    print()
    print("=" * 70)
    print("✅ 미국 ETF Universe 생성 완료")
    print("=" * 70)

    print(
        f"Nasdaq ETF       : "
        f"{len(nasdaq_df):,}개"
    )

    print(
        f"Other ETF        : "
        f"{len(other_df):,}개"
    )

    print(
        f"중복 제거 후 전체 : "
        f"{len(df):,}개"
    )

    print(
        f"저장 파일         : "
        f"{filename}"
    )

    print()
    print("상위 20개")
    print()

    print(
        df.head(20)
        .to_string(
            index=False
        )
    )

    return df


def download_etf(
    ticker,
    force=False
):
    """
    미국 ETF 가격 데이터 증분 업데이트

    ------------------------------------------------------------
    동작 방식
    ------------------------------------------------------------

    1. CSV 없음
       → START_DATE부터 전체 다운로드

    2. CSV 존재하지만 비어 있음
       → START_DATE부터 전체 다운로드

    3. CSV 존재하지만 날짜 컬럼 없음
       → START_DATE부터 전체 다운로드

    4. CSV 존재 + 날짜 정상
       → 마지막 날짜 이전 며칠을 포함하여 재다운로드

    5. 기존 데이터 + 신규 데이터 병합

    6. 날짜 중복 제거

    7. CSV 저장
    """

    # ========================================================
    # 저장 파일
    # ========================================================

    filename = (
        DATA_DIR
        / f"{ticker}.csv"
    )

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


    # ========================================================
    # 오늘
    # ========================================================

    today = (
        pd.Timestamp
        .today()
        .normalize()
    )


    # ========================================================
    # 기존 데이터
    # ========================================================

    old_df = None


    if (
        filename.exists()
        and not force
    ):

        print()
        print(
            f"  📂 기존 CSV 발견: "
            f"{filename}"
        )

        try:

            old_df = pd.read_csv(
                filename
            )


            # ------------------------------------------------
            # CSV 자체가 비어있는 경우
            # ------------------------------------------------

            if old_df is None:

                old_df = None

            elif old_df.empty:

                print(
                    "  ⚠ CSV가 비어 있습니다."
                )

                old_df = None


            # ------------------------------------------------
            # 날짜 컬럼 확인
            # ------------------------------------------------

            elif "날짜" not in old_df.columns:

                print(
                    "  ⚠ '날짜' 컬럼이 없습니다."
                )

                print(
                    f"     현재 컬럼: "
                    f"{list(old_df.columns)}"
                )

                old_df = None


            else:

                # --------------------------------------------
                # 날짜 변환
                # --------------------------------------------

                old_df["날짜"] = (
                    pd.to_datetime(
                        old_df["날짜"],
                        errors="coerce"
                    )
                )


                # --------------------------------------------
                # 날짜가 전부 잘못된 경우
                # --------------------------------------------

                valid_date_count = (
                    old_df["날짜"]
                    .notna()
                    .sum()
                )


                if valid_date_count == 0:

                    print(
                        "  ⚠ 정상적인 날짜 데이터가 없습니다."
                    )

                    print(
                        "     → 처음부터 다시 다운로드합니다."
                    )

                    old_df = None


                else:

                    # ----------------------------------------
                    # 날짜 없는 행 제거
                    # ----------------------------------------

                    old_df = (
                        old_df
                        .dropna(
                            subset=[
                                "날짜"
                            ]
                        )
                    )


                    # ----------------------------------------
                    # 날짜 정렬
                    # ----------------------------------------

                    old_df = (
                        old_df
                        .sort_values(
                            "날짜"
                        )
                    )


                    # ----------------------------------------
                    # 중복 날짜 제거
                    # ----------------------------------------

                    old_df = (
                        old_df
                        .drop_duplicates(
                            subset=[
                                "날짜"
                            ],
                            keep="last"
                        )
                    )


                    old_df = (
                        old_df
                        .reset_index(
                            drop=True
                        )
                    )


        except Exception as e:

            print(
                f"  ⚠ 기존 CSV 읽기 실패: "
                f"{e}"
            )

            print(
                "     → 처음부터 다시 다운로드합니다."
            )

            old_df = None


    # ========================================================
    # 다운로드 시작 날짜 결정
    # ========================================================

    if (
        old_df is None
        or old_df.empty
    ):

        # ----------------------------------------------------
        # 처음부터 다운로드
        # ----------------------------------------------------

        download_start = (
            pd.Timestamp(
                START_DATE
            )
        )


        print()
        print(
            "  🆕 최초 다운로드"
        )

        print(
            f"     ETF : {ticker}"
        )

        print(
            f"     기간 : "
            f"{download_start.date()} "
            f"~ "
            f"{today.date()}"
        )


    else:

        # ----------------------------------------------------
        # 마지막 정상 날짜
        # ----------------------------------------------------

        last_date = (
            old_df["날짜"]
            .max()
        )


        # ====================================================
        # 중요
        #
        # 마지막 날짜 하루 전부터 다시 받는다.
        #
        # Yahoo 데이터 수정/배당/분할 등을 보완하기 위함.
        # ====================================================

        download_start = (
            last_date
            - pd.Timedelta(
                days=3
            )
        )


        # START_DATE보다 빠를 수 없음

        start_limit = pd.Timestamp(
            START_DATE
        )


        if download_start < start_limit:

            download_start = (
                start_limit
            )


        # ----------------------------------------------------
        # 이미 최신 데이터인지 확인
        # ----------------------------------------------------

        if last_date >= today:

            print()
            print(
                f"  ✅ 최신 데이터: "
                f"{ticker}"
            )

            print(
                f"     마지막 날짜: "
                f"{last_date.date()}"
            )

            return old_df


        print()
        print(
            f"  🔄 증분 업데이트"
        )

        print(
            f"     ETF : {ticker}"
        )

        print(
            f"     기존 마지막 날짜 : "
            f"{last_date.date()}"
        )

        print(
            f"     다운로드 시작 : "
            f"{download_start.date()}"
        )

        print(
            f"     다운로드 종료 : "
            f"{today.date()}"
        )


    # ========================================================
    # Yahoo Finance 다운로드
    # ========================================================

    try:

        new_df = yf.download(

            ticker,

            start=(
                download_start
                .strftime(
                    "%Y-%m-%d"
                )
            ),

            end=(
                today
                + pd.Timedelta(
                    days=1
                )
            ).strftime(
                "%Y-%m-%d"
            ),

            interval="1d",

            auto_adjust=False,

            actions=True,

            progress=False,

            threads=False

        )


    except Exception as e:

        print()
        print(
            f"  ❌ Yahoo 다운로드 실패: "
            f"{ticker}"
        )

        print(
            f"     {e}"
        )


        # 기존 데이터가 있다면 유지

        if (
            old_df is not None
            and not old_df.empty
        ):

            return old_df


        return None


    # ========================================================
    # 신규 데이터 확인
    # ========================================================

    if (
        new_df is None
        or new_df.empty
    ):

        print()
        print(
            f"  ⚠ Yahoo에서 데이터가 없습니다: "
            f"{ticker}"
        )


        if (
            old_df is not None
            and not old_df.empty
        ):

            return old_df


        return None


    # ========================================================
    # MultiIndex 처리
    # ========================================================

    new_df = flatten_columns(
        new_df
    )


    # ========================================================
    # Index → 날짜
    # ========================================================

    new_df = (
        new_df
        .reset_index()
    )


    # ========================================================
    # 컬럼명
    # ========================================================

    rename_map = {

        "Date":
            "날짜",

        "Datetime":
            "날짜",

        "Open":
            "시가",

        "High":
            "고가",

        "Low":
            "저가",

        "Close":
            "종가",

        "Adj Close":
            "수정주가",

        "Volume":
            "거래량",

        "Dividends":
            "배당",

        "Stock Splits":
            "주식분할",

    }


    new_df = (
        new_df
        .rename(
            columns=rename_map
        )
    )


    # ========================================================
    # 날짜 컬럼 확인
    # ========================================================

    if "날짜" not in new_df.columns:

        print()
        print(
            f"  ❌ 날짜 컬럼이 없습니다: "
            f"{ticker}"
        )

        print(
            list(
                new_df.columns
            )
        )

        return old_df


    # ========================================================
    # 수정주가
    # ========================================================

    if (
        "수정주가"
        not in new_df.columns
    ):

        if (
            "종가"
            in new_df.columns
        ):

            new_df["수정주가"] = (
                new_df["종가"]
            )

        else:

            print(
                f"  ❌ 가격 데이터 없음: "
                f"{ticker}"
            )

            return old_df


    # ========================================================
    # 날짜 변환
    # ========================================================

    new_df["날짜"] = (
        pd.to_datetime(
            new_df["날짜"],
            errors="coerce"
        )
    )


    new_df = (
        new_df
        .dropna(
            subset=[
                "날짜"
            ]
        )
    )


    # ========================================================
    # 숫자 변환
    # ========================================================

    numeric_columns = [

        "시가",
        "고가",
        "저가",
        "종가",
        "수정주가",
        "거래량",
        "배당",
        "주식분할",

    ]


    for column in numeric_columns:

        if (
            column
            in new_df.columns
        ):

            new_df[column] = (
                pd.to_numeric(
                    new_df[column],
                    errors="coerce"
                )
            )


    # ========================================================
    # 가격 없는 데이터 제거
    # ========================================================

    new_df = (
        new_df
        .dropna(
            subset=[
                "수정주가"
            ]
        )
    )


    # ========================================================
    # 신규 데이터가 실제로 존재하는지
    # ========================================================

    if new_df.empty:

        print(
            f"  ⚠ 유효한 가격 데이터 없음: "
            f"{ticker}"
        )

        if old_df is not None:

            return old_df

        return None


    # ========================================================
    # 기존 + 신규
    # ========================================================

    if (
        old_df is not None
        and not old_df.empty
    ):

        combined = pd.concat(

            [
                old_df,
                new_df
            ],

            ignore_index=True

        )

    else:

        combined = (
            new_df.copy()
        )


    # ========================================================
    # 날짜 다시 정리
    # ========================================================

    combined["날짜"] = (
        pd.to_datetime(
            combined["날짜"],
            errors="coerce"
        )
    )


    combined = (
        combined
        .dropna(
            subset=[
                "날짜"
            ]
        )
    )


    # ========================================================
    # 날짜 정렬
    # ========================================================

    combined = (
        combined
        .sort_values(
            "날짜"
        )
    )


    # ========================================================
    # 중복 날짜 제거
    #
    # 신규 Yahoo 데이터가 기존 데이터를 덮어쓴다.
    # ========================================================

    combined = (
        combined
        .drop_duplicates(
            subset=[
                "날짜"
            ],
            keep="last"
        )
    )


    # ========================================================
    # 인덱스
    # ========================================================

    combined = (
        combined
        .reset_index(
            drop=True
        )
    )


    # ========================================================
    # 저장
    # ========================================================

    combined.to_csv(

        filename,

        index=False,

        encoding="utf-8-sig"

    )


    # ========================================================
    # 결과
    # ========================================================

    first_date = (
        combined["날짜"]
        .min()
    )


    last_date = (
        combined["날짜"]
        .max()
    )


    print()
    print(
        f"  ✅ 업데이트 완료"
    )

    print(
        f"     ETF : "
        f"{ticker}"
    )

    print(
        f"     데이터 : "
        f"{len(combined):,}일"
    )

    print(
        f"     기간 : "
        f"{first_date.date()} "
        f"~ "
        f"{last_date.date()}"
    )

    print(
        f"     저장 : "
        f"{filename}"
    )


    return combined

# ============================================================
# 5. Universe 읽기
# ============================================================

def load_etf_universe():

    filename = Path(
        "data/미국_ETF_Universe.csv"
    )


    if filename.exists():

        try:

            df = pd.read_csv(
                filename,
                dtype={
                    "티커": str
                }
            )

            if not df.empty:
                return df

        except Exception:
            pass



# ============================================================
# 실행
# ============================================================

if __name__ == "__main__":

    get_us_etf_universe()

    print()
    print("=" * 100)
    print("데이타 다운로드")
    print("=" * 100)

    # ========================================================
    # ETF Universe
    # ========================================================

    universe = load_etf_universe()

    if universe is None or universe.empty:

        raise RuntimeError(
            "미국 ETF Universe를 "
            "가져오지 못했습니다."
        )

    print()
    print("🔥 전체 ETF 모드")

    # ========================================================
    # 데이터 다운로드
    # ========================================================

    success = []

    failed = []

    total = len(universe)


    for index, ticker in enumerate(
        universe["티커"],
        start=1
    ):

        print()
        print(
            f"[{index}/{total}] "
            f"{ticker}"
        )


        df = download_etf(
            ticker
        )


        if (df is not None and not df.empty):
            success.append(ticker)
        else:
            failed.append(ticker)


        time.sleep(REQUEST_SLEEP)


    print()
    print("=" * 100)

    print(
        f"데이터 성공 : "
        f"{len(success):,}"
    )

    print(
        f"데이터 실패 : "
        f"{len(failed):,}"
    )

    print("=" * 100)

