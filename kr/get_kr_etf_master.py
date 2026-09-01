import os
import time
from datetime import datetime, timedelta

import pandas as pd
from dotenv import load_dotenv
from pykrx import stock


# ============================================================
# 환경변수
# ============================================================

load_dotenv()

KRX_ID = os.getenv("KRX_ID")
KRX_PW = os.getenv("KRX_PW")

if not KRX_ID or not KRX_PW:
    raise RuntimeError(
        "KRX_ID 또는 KRX_PW가 설정되지 않았습니다.\n"
        ".env 파일을 확인하세요."
    )

print(f"KRX_ID 확인 : {KRX_ID[:3]}***")


# ============================================================
# 조회일 계산
# ============================================================

def get_recent_business_date():

    today = datetime.now()

    # 최근 7일 중 KRX 데이터를 얻을 수 있는 날짜를 찾음
    for i in range(7):

        date = today - timedelta(days=i)

        date_str = date.strftime("%Y%m%d")

        try:

            tickers = stock.get_etf_ticker_list(
                date_str
            )

            if tickers:

                return date_str

        except Exception:

            pass

    raise RuntimeError(
        "최근 거래일을 찾지 못했습니다."
    )


# ============================================================
# ETF MASTER 생성
# ============================================================

def get_etf_master():

    date = get_recent_business_date()

    print()
    print("=" * 70)
    print(f"ETF 조회 기준일 : {date}")
    print("=" * 70)


    # --------------------------------------------------------
    # ETF 목록
    # --------------------------------------------------------

    tickers = stock.get_etf_ticker_list(date)

    print(
        f"ETF 종목 수 : {len(tickers):,}개"
    )


    rows = []


    # --------------------------------------------------------
    # ETF별 데이터
    # --------------------------------------------------------

    for i, ticker in enumerate(tickers, 1):

        try:

            ticker = str(ticker)

            # ETF 이름
            name = stock.get_etf_ticker_name(
                ticker
            )

            if isinstance(name, pd.Series):
                name = name.iloc[0]

            elif isinstance(name, pd.DataFrame):
                name = name.iloc[0, 0]

            name = str(name)


            # ------------------------------------------------
            # 최근 ETF 가격 데이터
            # ------------------------------------------------

            price_df = stock.get_etf_ohlcv_by_date(
                date,
                date,
                ticker
            )


            # 데이터가 없으면 제외
            if price_df.empty:

                print(
                    f"[{i}/{len(tickers)}] "
                    f"{ticker} | 가격 데이터 없음"
                )

                continue


            row = price_df.iloc[-1]


            # ------------------------------------------------
            # 데이터 추출
            # ------------------------------------------------

            nav = row.get(
                "NAV",
                None
            )

            open_price = row.get(
                "시가",
                None
            )

            high_price = row.get(
                "고가",
                None
            )

            low_price = row.get(
                "저가",
                None
            )

            close_price = row.get(
                "종가",
                None
            )

            volume = row.get(
                "거래량",
                None
            )

            value = row.get(
                "거래대금",
                None
            )

            change = row.get(
                "등락률",
                None
            )


            # ------------------------------------------------
            # MASTER row
            # ------------------------------------------------

            rows.append({

                "기준일": date,
                "티커": ticker,
                "ETF명": name,
                "NAV": nav,
                "시가": open_price,
                "고가": high_price,
                "저가": low_price,
                "종가": close_price,
                "거래량": volume,
                "거래대금": value,
                "등락률": change,
            })


            print(
                f"[{i:4d}/{len(tickers):4d}] "
                f"{ticker} | {name}"
            )


            # KRX 요청 간격
            time.sleep(0.05)


        except Exception as e:

            print(
                f"ERROR {ticker}: {e}"
            )


    # ========================================================
    # DataFrame
    # ========================================================

    df = pd.DataFrame(rows)


    if df.empty:

        raise RuntimeError(
            "ETF MASTER 데이터가 비어 있습니다."
        )


    # ========================================================
    # 타입 정리
    # ========================================================

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


    # ========================================================
    # 중복 제거
    # ========================================================

    df = df.drop_duplicates(
        subset=["티커"]
    )


    # ========================================================
    # 정렬
    # ========================================================

    df = df.sort_values(
        by="ETF명"
    ).reset_index(drop=True)


    # ========================================================
    # CSV 저장
    # ========================================================

    filename = (
        "국내_ETF_MASTER.csv"
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
    print("✅ ETF MASTER 생성 완료")
    print("=" * 70)

    print(
        f"ETF 수 : {len(df):,}개"
    )

    print(
        f"파일   : {filename}"
    )

    print("=" * 70)


    # ========================================================
    # 샘플
    # ========================================================

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

    df = get_etf_master()