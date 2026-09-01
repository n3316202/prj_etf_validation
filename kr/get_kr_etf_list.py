import os
import time

import pandas as pd
from dotenv import load_dotenv
from pykrx import stock


# ============================================================
# 환경변수
# ============================================================

load_dotenv()

KRX_ID = os.getenv("KRX_ID")
KRX_PW = os.getenv("KRX_PW")


if not KRX_ID:
    raise RuntimeError(
        "KRX_ID가 설정되지 않았습니다."
    )

if not KRX_PW:
    raise RuntimeError(
        "KRX_PW가 설정되지 않았습니다."
    )


print(f"KRX_ID 확인 : {KRX_ID[:3]}***")


# ============================================================
# ETF 전체 목록
# ============================================================

def get_all_etf_list():

    # --------------------------------------------------------
    # 날짜
    # --------------------------------------------------------

    # 오늘 날짜
    today = pd.Timestamp.today()

    # YYYYMMDD
    date = today.strftime("%Y%m%d")

    print()
    print("=" * 70)
    print(f"조회 기준일 : {date}")
    print("=" * 70)


    # --------------------------------------------------------
    # ETF 티커 조회
    # --------------------------------------------------------

    try:

        tickers = stock.get_etf_ticker_list(date)

    except Exception as e:

        print()
        print("❌ ETF 티커 조회 실패")
        print(e)

        raise


    if not tickers:

        raise RuntimeError(
            "ETF 티커 목록이 비어 있습니다."
        )


    print(
        f"ETF 개수 : {len(tickers):,}개"
    )


    # --------------------------------------------------------
    # ETF 정보 수집
    # --------------------------------------------------------

    rows = []


    for i, ticker in enumerate(tickers, 1):

        try:

            # ETF 이름
            name = stock.get_etf_ticker_name(
                ticker
            )


            # ------------------------------------------------
            # 반환값 방어
            # ------------------------------------------------

            if isinstance(name, pd.Series):

                name = name.iloc[0]


            elif isinstance(name, pd.DataFrame):

                name = name.iloc[0, 0]


            name = str(name)


            ticker = str(ticker)


            # ------------------------------------------------
            # 저장
            # ------------------------------------------------

            rows.append({

                "티커": ticker,

                "ETF명": name

            })


            print(
                f"[{i:4d}/{len(tickers):4d}] "
                f"{ticker} | {name}"
            )


            # KRX 요청 간격
            time.sleep(0.05)


        except Exception as e:

            print(
                f"⚠️ {ticker} 실패 : {e}"
            )


    # --------------------------------------------------------
    # DataFrame
    # --------------------------------------------------------

    df = pd.DataFrame(rows)


    if df.empty:

        raise RuntimeError(
            "ETF 데이터가 하나도 수집되지 않았습니다."
        )


    # --------------------------------------------------------
    # 데이터 타입 강제
    # --------------------------------------------------------

    df["티커"] = (
        df["티커"]
        .astype(str)
        .str.strip()
    )

    df["ETF명"] = (
        df["ETF명"]
        .astype(str)
        .str.strip()
    )


    # --------------------------------------------------------
    # 중복 제거
    # --------------------------------------------------------

    df = df.drop_duplicates(
        subset=["티커"]
    )


    # --------------------------------------------------------
    # ETF 이름 정렬
    # --------------------------------------------------------

    df = df.sort_values(
        by=["ETF명"],
        ascending=True
    ).reset_index(drop=True)


    # --------------------------------------------------------
    # 저장
    # --------------------------------------------------------

    filename = "국내_ETF_전체목록.csv"


    df.to_csv(

        filename,

        index=False,

        encoding="utf-8-sig"

    )


    # --------------------------------------------------------
    # 결과
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("✅ ETF 목록 수집 완료")
    print("=" * 70)

    print(
        f"총 ETF : {len(df):,}개"
    )

    print(
        f"파일   : {filename}"
    )

    print("=" * 70)


    # --------------------------------------------------------
    # 상위 데이터
    # --------------------------------------------------------

    print()

    print(
        df.head(20).to_string(
            index=False
        )
    )


    return df


# ============================================================
# 실행
# ============================================================

if __name__ == "__main__":

    df = get_all_etf_list()