import io
import os
import time
from pathlib import Path
from datetime import datetime

import requests
import pandas as pd
import yfinance as yf


# ============================================================
# 기본 설정
# ============================================================

START_DATE = "2016-01-01"

END_DATE = datetime.now().strftime(
    "%Y-%m-%d"
)

REQUEST_SLEEP = 0.5

DATA_DIR = Path(
    "data/jp_etf"
)

UNIVERSE_FILE = Path(
    "data/일본_ETF_Universe.csv"
)


# ============================================================
# Yahoo Finance
# ============================================================

YAHOO_SUFFIX = ".T"


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


# ============================================================
# JPX ETF 목록
# ============================================================

JPX_URL = (
    "https://www.jpx.co.jp/"
    "markets/statistics-equities/"
    "misc/01.html"
)


# ============================================================
# Yahoo 티커 변환
# ============================================================

def yahoo_ticker(ticker):

    ticker = str(ticker).strip()

    if ticker.endswith(".T"):
        return ticker

    return ticker + YAHOO_SUFFIX


# ============================================================
# 일본 ETF Universe
# ============================================================

def get_japan_etf_universe():

    print()
    print("=" * 70)
    print("🇯🇵 일본 ETF Universe 생성")
    print("=" * 70)

    # ========================================================
    # JPX ETF 전체 목록
    # ========================================================

    JPX_URL = (
        "https://www.jpx.co.jp/"
        "english/equities/products/"
        "etfs/issues/01.html"
    )

    print()
    print("JPX ETF 목록을 조회합니다.")
    print()
    print(f"URL : {JPX_URL}")

    # ========================================================
    # HTTP
    # ========================================================

    try:

        response = requests.get(
            JPX_URL,
            headers=HEADERS,
            timeout=30
        )

        response.raise_for_status()

    except Exception as e:

        print()
        print("❌ JPX 접속 실패")
        print(e)

        return None


    print()
    print("✅ JPX 페이지 접속 성공")


    # ========================================================
    # HTML TABLE
    # ========================================================

    try:

        tables = pd.read_html(
            io.StringIO(
                response.text
            )
        )

    except Exception as e:

        print()
        print("❌ HTML Table 읽기 실패")
        print(e)

        return None


    print()
    print(
        f"JPX Table 수 : {len(tables)}"
    )


    # ========================================================
    # Table 검색
    # ========================================================

    etf_df = None


    for i, table in enumerate(tables):

        print()
        print(
            f"Table {i}"
        )

        print(
            table.head(3)
            .to_string(
                index=False
            )
        )


        # 컬럼 문자열
        column_text = " ".join(
            [
                str(c)
                for c in table.columns
            ]
        )


        # ETF 목록의 특징적인 컬럼
        if (
            "Code" in column_text
            and "Fund Name" in column_text
        ):

            etf_df = table.copy()

            print()
            print(
                f"✅ ETF Table 발견 : "
                f"Table {i}"
            )

            break


    # ========================================================
    # ETF Table 없음
    # ========================================================

    if etf_df is None:

        print()
        print("=" * 70)
        print("❌ ETF Table을 찾지 못했습니다.")
        print("=" * 70)

        print()
        print(
            "현재 JPX HTML 구조를 확인해야 합니다."
        )

        return None


    # ========================================================
    # 컬럼 확인
    # ========================================================

    print()
    print("원본 컬럼:")
    print(
        list(etf_df.columns)
    )


    # ========================================================
    # Code
    # ========================================================

    code_column = "Code"


    if code_column not in etf_df.columns:

        print(
            "❌ Code 컬럼 없음"
        )

        return None


    # ========================================================
    # Fund Name
    # ========================================================

    name_column = "Fund Name"


    if name_column not in etf_df.columns:

        print(
            "❌ Fund Name 컬럼 없음"
        )

        return None


    # ========================================================
    # Universe 생성
    # ========================================================

    df = pd.DataFrame({

        "티커":
            etf_df[code_column]
            .astype(str)
            .str.strip(),

        "ETF명":
            etf_df[name_column]
            .astype(str)
            .str.strip(),

        "거래소":
            "TSE"

    })


    # ========================================================
    # 불필요한 행 제거
    # ========================================================

    df = df[
        df["티커"].notna()
    ].copy()


    df = df[
        df["티커"] != ""
    ].copy()


    df = df[
        df["티커"] != "nan"
    ].copy()


    # ========================================================
    # JPX 코드 정리
    #
    # 1306
    # 1321
    # 2869
    # 611A
    # 613A
    # ========================================================

    df["티커"] = (
        df["티커"]
        .str.replace(
            " ",
            "",
            regex=False
        )
        .str.upper()
    )


    # ========================================================
    # 중복 제거
    # ========================================================

    df = (
        df
        .drop_duplicates(
            subset=[
                "티커"
            ],
            keep="first"
        )
    )


    # ========================================================
    # 정렬
    # ========================================================

    df = df.sort_values("티커").reset_index(drop=True)


    # ========================================================
    # 2869 확인
    # ========================================================

    print()
    print("=" * 70)
    print("🔎 2869 확인")
    print("=" * 70)


    target = df[
        df["티커"] == "2869"
    ]


    if not target.empty:

        print(
            "✅ 2869 발견!"
        )

        print()

        print(
            target.to_string(
                index=False
            )
        )

    else:

        print(
            "⚠ 2869가 없습니다."
        )


    # ========================================================
    # 저장
    # ========================================================

    UNIVERSE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    df.to_csv(
        UNIVERSE_FILE,
        index=False,
        encoding="utf-8-sig"
    )


    # ========================================================
    # 결과
    # ========================================================

    print()
    print("=" * 70)
    print("✅ 일본 ETF Universe 생성 완료")
    print("=" * 70)


    print(
        f"전체 ETF : "
        f"{len(df):,}개"
    )


    print(
        f"저장 파일 : "
        f"{UNIVERSE_FILE}"
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


# ============================================================
# MultiIndex 처리
# ============================================================

def flatten_columns(df):

    if not isinstance(
        df.columns,
        pd.MultiIndex
    ):

        return df


    new_columns = []

    for column in df.columns:

        values = [
            str(x)
            for x in column
            if str(x) != "nan"
        ]

        new_columns.append(
            values[0]
            if values
            else ""
        )


    df.columns = new_columns

    return df


# ============================================================
# 일본 ETF 다운로드
# ============================================================

def download_etf(
    ticker,
    force=False
):

    # --------------------------------------------------------
    # 일본 티커
    # --------------------------------------------------------

    ticker = str(
        ticker
    ).strip()


    # --------------------------------------------------------
    # Yahoo 티커
    # --------------------------------------------------------

    yf_ticker = yahoo_ticker(
        ticker
    )


    # --------------------------------------------------------
    # 저장 파일
    # --------------------------------------------------------

    filename = (
        DATA_DIR
        / f"{ticker}.csv"
    )


    # --------------------------------------------------------
    # 데이터 폴더
    # --------------------------------------------------------

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


    # --------------------------------------------------------
    # 오늘
    # --------------------------------------------------------

    today = (
        pd.Timestamp.today()
        .normalize()
    )


    # ========================================================
    # 기존 CSV
    # ========================================================

    old_df = None


    if (
        filename.exists()
        and not force
    ):

        try:

            old_df = pd.read_csv(
                filename
            )


            if not old_df.empty:

                old_df["날짜"] = (
                    pd.to_datetime(
                        old_df["날짜"],
                        errors="coerce"
                    )
                )


                old_df = (
                    old_df
                    .dropna(
                        subset=[
                            "날짜"
                        ]
                    )
                )


                old_df = (
                    old_df
                    .sort_values(
                        "날짜"
                    )
                )


                old_df = (
                    old_df
                    .drop_duplicates(
                        subset=[
                            "날짜"
                        ],
                        keep="last"
                    )
                )


        except Exception as e:

            print(
                f"  ⚠ 기존 CSV 읽기 실패: "
                f"{e}"
            )

            old_df = None


    # ========================================================
    # 최초 다운로드
    # ========================================================

    if (
        old_df is None
        or old_df.empty
    ):

        download_start = (
            pd.Timestamp(
                START_DATE
            )
        )


        print(
            f"  ↓ 최초 다운로드: "
            f"{ticker}"
        )


        print(
            f"     Yahoo: "
            f"{yf_ticker}"
        )


        print(
            f"     "
            f"{download_start.date()} "
            f"~ "
            f"{today.date()}"
        )


    # ========================================================
    # 증분 업데이트
    # ========================================================

    else:

        last_date = (
            old_df["날짜"].max()
        )


        download_start = (
            last_date
            + pd.Timedelta(
                days=1
            )
        )


        # ----------------------------------------------------
        # 최신
        # ----------------------------------------------------

        if download_start > today:

            print(
                f"  ✅ 최신 데이터: "
                f"{ticker}"
            )


            print(
                f"     마지막 날짜: "
                f"{last_date.date()}"
            )


            return old_df


        print(
            f"  🔄 증분 업데이트: "
            f"{ticker}"
        )


        print(
            f"     Yahoo: "
            f"{yf_ticker}"
        )


        print(
            f"     기존 마지막 날짜: "
            f"{last_date.date()}"
        )


        print(
            f"     신규 다운로드: "
            f"{download_start.date()} "
            f"~ "
            f"{today.date()}"
        )


    # ========================================================
    # Yahoo Finance
    # ========================================================

    try:

        new_df = yf.download(

            yf_ticker,

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

        print(
            f"  ❌ 다운로드 실패: "
            f"{ticker}"
        )


        print(
            f"     Yahoo: "
            f"{yf_ticker}"
        )


        print(
            f"     {e}"
        )


        if old_df is not None:

            return old_df


        return None


    # ========================================================
    # 신규 데이터 없음
    # ========================================================

    if (
        new_df is None
        or new_df.empty
    ):

        print(
            f"  ℹ 신규 거래 데이터 없음: "
            f"{ticker}"
        )


        if old_df is not None:

            return old_df


        return None


    # ========================================================
    # MultiIndex
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
    # 수정주가
    # ========================================================

    if "수정주가" not in new_df.columns:

        if "종가" in new_df.columns:

            new_df["수정주가"] = (
                new_df["종가"]
            )

        else:

            print(
                f"  ❌ 가격 컬럼 없음: "
                f"{ticker}"
            )

            return old_df


    # ========================================================
    # 날짜
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
    # 숫자
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

        if column in new_df.columns:

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
    # 날짜 정리
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


    combined = (
        combined
        .sort_values(
            "날짜"
        )
    )


    # ========================================================
    # 중복 제거
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
        combined["날짜"].min()
    )


    last_date = (
        combined["날짜"].max()
    )


    print()

    print(
        f"  ✅ 업데이트 완료: "
        f"{ticker}"
    )


    print(
        f"     Yahoo: "
        f"{yf_ticker}"
    )


    print(
        f"     전체 데이터: "
        f"{len(combined):,}일"
    )


    print(
        f"     기간: "
        f"{first_date.date()} "
        f"~ "
        f"{last_date.date()}"
    )


    print(
        f"     저장: "
        f"{filename}"
    )


    return combined


# ============================================================
# Universe 읽기
# ============================================================

def load_etf_universe():

    if not UNIVERSE_FILE.exists():

        return None


    try:

        df = pd.read_csv(

            UNIVERSE_FILE,

            dtype={
                "티커": str
            }

        )


        if df.empty:

            return None


        return df


    except Exception as e:

        print(
            f"❌ Universe 읽기 실패: "
            f"{e}"
        )


        return None


# ============================================================
# 실행
# ============================================================

if __name__ == "__main__":

    # ========================================================
    # Universe 생성
    # ========================================================

    universe = (
        get_japan_etf_universe()
    )


    if universe is None:

        raise RuntimeError(
            "일본 ETF Universe를 "
            "생성하지 못했습니다."
        )


    print()

    print("=" * 100)

    print(
        "🇯🇵 일본 ETF 데이터 다운로드"
    )

    print("=" * 100)


    # ========================================================
    # Universe 다시 읽기
    # ========================================================

    universe = (
        load_etf_universe()
    )


    if (
        universe is None
        or universe.empty
    ):

        raise RuntimeError(
            "일본 ETF Universe를 "
            "가져오지 못했습니다."
        )


    print()

    print(
        f"🔥 전체 일본 ETF 모드"
    )


    print(
        f"전체 ETF : "
        f"{len(universe):,}개"
    )


    # ========================================================
    # 다운로드
    # ========================================================

    success = []

    failed = []


    total = len(
        universe
    )


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


        if (
            df is not None
            and not df.empty
        ):

            success.append(
                ticker
            )

        else:

            failed.append(
                ticker
            )


        time.sleep(
            REQUEST_SLEEP
        )


    # ========================================================
    # 결과
    # ========================================================

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


    # ========================================================
    # 실패 목록
    # ========================================================

    if failed:

        print()

        print(
            "실패 목록"
        )

        print(
            ", ".join(
                failed
            )
        )