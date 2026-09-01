import io
import os
import requests
import pandas as pd
import yfinance as yf

import time
from pathlib import Path
from datetime import datetime


# ============================================================
# Nasdaq Trader
# ============================================================

START_DATE = "2016-01-01"

END_DATE = datetime.now().strftime(
    "%Y-%m-%d"
)

# 요청 간격
REQUEST_SLEEP = 0.5

DATA_DIR = Path("data/us_etf")

NASDAQ_URL = (
    "https://www.nasdaqtrader.com/"
    "dynamic/SymDir/nasdaqlisted.txt"
)

OTHER_URL = (
    "https://www.nasdaqtrader.com/"
    "dynamic/SymDir/otherlisted.txt"
)


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
# Nasdaq Listed ETF
# ============================================================

def get_nasdaq_etf():

    print()
    print("-" * 70)
    print("① Nasdaq 상장 종목 조회")
    print("-" * 70)

    response = requests.get(
        NASDAQ_URL,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    # --------------------------------------------------------
    # 응답 확인
    # --------------------------------------------------------

    text = response.text

    print(
        f"NASDAQ 응답 크기 : "
        f"{len(text):,} bytes"
    )

    if not text.strip():
        raise ValueError(
            "NASDAQ 서버에서 빈 응답을 받았습니다."
        )

    # --------------------------------------------------------
    # 데이터 읽기
    # --------------------------------------------------------

    df = pd.read_csv(
        io.StringIO(text),
        sep="|",
        dtype=str,
        keep_default_na=False
    )

    # --------------------------------------------------------
    # 컬럼명 정리
    # --------------------------------------------------------

    df.columns = (
        df.columns
        .astype(str)
        .str.replace("\ufeff", "", regex=False)
        .str.strip()
    )

    print()
    print("NASDAQ 컬럼:")
    print(df.columns.tolist())

    # --------------------------------------------------------
    # Symbol 컬럼 확인
    # --------------------------------------------------------

    if "Symbol" not in df.columns:

        print()
        print("❌ Symbol 컬럼을 찾을 수 없습니다.")
        print()
        print("현재 컬럼:")
        print(df.columns.tolist())
        print()

        print("응답 앞부분:")
        print(text[:1_000])

        raise KeyError(
            "NASDAQ 응답에 'Symbol' 컬럼이 없습니다."
        )

    # --------------------------------------------------------
    # Security Name 컬럼 확인
    # --------------------------------------------------------

    if "Security Name" not in df.columns:

        print()
        print("❌ Security Name 컬럼을 찾을 수 없습니다.")
        print()
        print("현재 컬럼:")
        print(df.columns.tolist())

        raise KeyError(
            "NASDAQ 응답에 'Security Name' 컬럼이 없습니다."
        )

    # --------------------------------------------------------
    # ETF 컬럼 확인
    # --------------------------------------------------------

    if "ETF" not in df.columns:

        print()
        print("❌ ETF 컬럼을 찾을 수 없습니다.")
        print()
        print("현재 컬럼:")
        print(df.columns.tolist())

        raise KeyError(
            "NASDAQ 응답에 'ETF' 컬럼이 없습니다."
        )

    # --------------------------------------------------------
    # 컬럼 값 정리
    # --------------------------------------------------------

    df["Symbol"] = (
        df["Symbol"]
        .astype(str)
        .str.strip()
    )

    df["Security Name"] = (
        df["Security Name"]
        .astype(str)
        .str.strip()
    )

    df["ETF"] = (
        df["ETF"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    # --------------------------------------------------------
    # Symbol 없는 행 제거
    # --------------------------------------------------------

    df = df[
        df["Symbol"] != ""
    ].copy()

    # --------------------------------------------------------
    # 마지막 File Creation 행 제거
    # --------------------------------------------------------

    df = df[
        ~df["Symbol"].str.startswith(
            "File Creation",
            na=False
        )
    ].copy()

    # --------------------------------------------------------
    # ETF만 추출
    # --------------------------------------------------------

    df = df[
        df["ETF"] == "Y"
    ].copy()

    # --------------------------------------------------------
    # 컬럼 변경
    # --------------------------------------------------------

    df = df.rename(
        columns={
            "Symbol": "티커",
            "Security Name": "ETF명",
        }
    )

    # --------------------------------------------------------
    # 거래소
    # --------------------------------------------------------

    df["거래소"] = "NASDAQ"

    # --------------------------------------------------------
    # 필요한 컬럼
    # --------------------------------------------------------

    df = df[
        [
            "티커",
            "ETF명",
            "거래소"
        ]
    ].copy()

    # --------------------------------------------------------
    # 빈 티커 제거
    # --------------------------------------------------------

    df = df[
        df["티커"].notna()
        & (df["티커"].astype(str).str.strip() != "")
    ].copy()

    # --------------------------------------------------------
    # 중복 제거
    # --------------------------------------------------------

    df = df.drop_duplicates(
        subset=["티커"]
    ).reset_index(drop=True)

    # --------------------------------------------------------
    # 결과 출력
    # --------------------------------------------------------

    print()
    print(
        f"Nasdaq ETF : "
        f"{len(df):,}개"
    )

    # --------------------------------------------------------
    # TQQQ 확인
    # --------------------------------------------------------

    tqqq = df[
        df["티커"].str.upper() == "TQQQ"
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
            "⚠ TQQQ가 Nasdaq ETF 목록에 없습니다."
        )

    return df




# ============================================================
# Other Listed ETF
# ============================================================

def get_other_etf():

    print()
    print("-" * 70)
    print("② 기타 거래소 상장 종목 조회")
    print("-" * 70)

    response = requests.get(
        OTHER_URL,
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    df = pd.read_csv(
        io.StringIO(response.text),
        sep="|"
    )

    # --------------------------------------------------------
    # ACT Symbol 존재 데이터
    # --------------------------------------------------------

    df = df[
        df["ACT Symbol"].notna()
    ].copy()

    # --------------------------------------------------------
    # 마지막 설명 행 제거
    # --------------------------------------------------------

    df = df[
        ~df["ACT Symbol"]
        .astype(str)
        .str.startswith(
            "File Creation"
        )
    ].copy()

    # --------------------------------------------------------
    # ETF만
    # --------------------------------------------------------

    df = df[
        df["ETF"] == "Y"
    ].copy()

    # --------------------------------------------------------
    # 컬럼 변경
    # --------------------------------------------------------

    df = df.rename(
        columns={
            "ACT Symbol": "티커",
            "Security Name": "ETF명",
            "Exchange": "거래소",
        }
    )

    df = df[
        [
            "티커",
            "ETF명",
            "거래소"
        ]
    ]

    print(
        f"Other Listed ETF : "
        f"{len(df):,}개"
    )

    return df


# ============================================================
# 미국 ETF Universe
# ============================================================

def get_us_etf_universe():

    print()
    print("=" * 70)
    print("🇺🇸 미국 ETF Universe 생성")
    print("=" * 70)

    # --------------------------------------------------------
    # Nasdaq
    # --------------------------------------------------------

    nasdaq_df = get_nasdaq_etf()

    # --------------------------------------------------------
    # 기타 거래소
    # --------------------------------------------------------

    other_df = get_other_etf()

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
    ].copy()

    df = df[
        df["티커"] != ""
    ].copy()

    # --------------------------------------------------------
    # 중복 제거
    # --------------------------------------------------------

    df = df.drop_duplicates(
        subset=[
            "티커"
        ],
        keep="first"
    )

    # --------------------------------------------------------
    # 정렬
    # --------------------------------------------------------

    df = df.sort_values(
        "티커"
    ).reset_index(
        drop=True
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

