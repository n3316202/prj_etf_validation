# etf_analysis.py

# ```python
# """
# ============================================================
# etf_analysis.py
# ============================================================

# 미국 ETF CSV 전체 자동 분석 프로그램

# 폴더 구조
# ------------------------------------------------------------

# 프로젝트/
# │
# ├─ us/
# │   └─ etf_analysis.py
# │
# └─ data/
#     └─ us_etf/
#         ├─ QQQ.csv
#         ├─ QLD.csv
#         ├─ TQQQ.csv
#         ├─ SOXX.csv
#         ├─ SMH.csv
#         └─ ...
        
# 실행 후
# ------------------------------------------------------------

# data/
# └─ us_etf/
#     │
#     ├─ QQQ.csv
#     ├─ QLD.csv
#     ├─ TQQQ.csv
#     ├─ ...
#     │
#     └─ analysis/
#         ├─ QQQ_analysis.csv
#         ├─ QLD_analysis.csv
#         ├─ TQQQ_analysis.csv
#         ├─ ...
#         └─ summary.csv


# 원본 CSV는 절대 수정하지 않는다.


# ============================================================
# 분석 기준
# ============================================================

# [가격 기준]

# 최고가
#     = 고가(High)의 누적 최고값

# 고점_대비_하락률
#     = (종가 / 최고가 - 1) × 100

# MDD
#     = 고점_대비_하락률의 최저값


# [MDD]

# MDD_시작일
#     = MDD 저점 이전의 MDD 발생 고점 날짜

# MDD_저점일
#     = 가장 큰 낙폭이 발생한 날짜

# 회복일
#     = MDD 시작 당시 고점 가격을
#       종가 기준으로 다시 회복한 최초 날짜

# 회복기간_거래일
#     = MDD 시작일 → 회복일까지의 거래일 수

# 회복기간_달력일
#     = MDD 시작일 → 회복일까지의 달력 일수


# [수익률]

# 수익률
#     = (종료 수정주가 / 시작 수정주가 - 1) × 100

# CAGR
#     = 연복리 수익률

# 수익률/CAGR은 수정주가 기준


# ============================================================
# """

import pandas as pd
from pathlib import Path


# ============================================================
# 1. 경로 설정
# ============================================================

# 현재 Python 파일 위치
BASE_DIR = Path(__file__).resolve().parent

# 현재 파일의 부모 폴더
PROJECT_DIR = BASE_DIR.parent

# 원본 ETF 데이터
INPUT_DIR = PROJECT_DIR / "us" / "data" / "us_etf"

# 분석 결과
OUTPUT_DIR = INPUT_DIR / "analysis"

# 전체 ETF 요약
SUMMARY_FILE = OUTPUT_DIR / "summary.csv"


# ============================================================
# 2. 기본 설정
# ============================================================

CSV_ENCODING = "utf-8-sig"


# ============================================================
# 3. 날짜 포맷 함수
# ============================================================

def format_date(value):

    if pd.isna(value):
        return ""

    return pd.Timestamp(value).strftime("%Y-%m-%d")


# ============================================================
# 4. ETF CSV 분석
# ============================================================

def analyze_etf(csv_file):

    print()
    print("=" * 90)
    print(f"▶ 처리 중 : {csv_file.name}")
    print("=" * 90)

    try:

        # ====================================================
        # CSV 읽기
        # ====================================================

        df = pd.read_csv(
            csv_file,
            encoding=CSV_ENCODING
        )


        # ====================================================
        # 필수 컬럼 확인
        # ====================================================

        required_columns = [
            "날짜",
            "수정주가",
            "종가",
            "고가"
        ]

        missing_columns = [
            column
            for column in required_columns
            if column not in df.columns
        ]

        if missing_columns:

            print(
                f"❌ 필수 컬럼 없음 : "
                f"{missing_columns}"
            )

            return None


        # ====================================================
        # 날짜 변환
        # ====================================================

        df["날짜"] = pd.to_datetime(
            df["날짜"],
            errors="coerce"
        )

        df = df.dropna(
            subset=["날짜"]
        )


        # ====================================================
        # 숫자형 변환
        # ====================================================

        numeric_columns = [
            "수정주가",
            "종가",
            "고가"
        ]

        for column in numeric_columns:

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            )


        # ====================================================
        # 필요한 데이터가 없는 행 제거
        # ====================================================

        df = df.dropna(
            subset=[
                "수정주가",
                "종가",
                "고가"
            ]
        )


        # ====================================================
        # 날짜순 정렬
        # ====================================================

        df = (
            df
            .sort_values("날짜")
            .reset_index(drop=True)
        )


        # ====================================================
        # 데이터 확인
        # ====================================================

        if len(df) < 2:

            print(
                "❌ 데이터가 2개 미만입니다."
            )

            return None


        # ====================================================
        # 5. 실제 가격 기준 누적 최고가
        # ====================================================
        #
        # 중요:
        #
        # 수정주가가 아니라 "고가"를 사용한다.
        #
        # 따라서 ETF가 새로운 고점을 만들 때마다
        # 최고가가 정상적으로 갱신된다.
        #

        df["최고가"] = (
            df["고가"]
            .cummax()
        )


        # ====================================================
        # 6. 최고가 발생일
        # ====================================================
        #
        # 현재까지의 최고가가 언제 만들어졌는지
        #

        highest_date_list = []

        current_high = float("-inf")
        current_high_date = pd.NaT

        for _, row in df.iterrows():

            high = row["고가"]

            if high > current_high:

                current_high = high
                current_high_date = row["날짜"]

            highest_date_list.append(
                current_high_date
            )

        df["최고가_발생일"] = (
            pd.Series(
                highest_date_list,
                index=df.index
            )
        )


        # ====================================================
        # 7. 고점 대비 하락률
        # ====================================================
        #
        # 현재 종가가 지금까지의 실제 최고가에서
        # 얼마나 떨어졌는지 계산
        #

        df["고점_대비_하락률"] = (
            (
                df["종가"]
                /
                df["최고가"]
            )
            - 1
        ) * 100


        # ====================================================
        # 8. 누적 MDD
        # ====================================================

        df["MDD"] = (
            df["고점_대비_하락률"]
            .cummin()
        )


        # ====================================================
        # 9. 최종 MDD 위치
        # ====================================================

        mdd_index = (
            df["고점_대비_하락률"]
            .idxmin()
        )

        mdd = df.loc[
            mdd_index,
            "고점_대비_하락률"
        ]


        # ====================================================
        # 10. MDD 저점일
        # ====================================================

        mdd_low_date = df.loc[
            mdd_index,
            "날짜"
        ]


        # ====================================================
        # 11. MDD 시작 고점
        # ====================================================
        #
        # MDD가 발생한 시점의
        # "최고가 발생일"을 사용
        #

        mdd_start_date = df.loc[
            mdd_index,
            "최고가_발생일"
        ]


        # ====================================================
        # 12. MDD 시작 인덱스
        # ====================================================

        start_candidates = df[
            df["날짜"]
            ==
            mdd_start_date
        ]

        if len(start_candidates) > 0:

            mdd_start_index = (
                start_candidates.index[-1]
            )

        else:

            mdd_start_index = None


        # ====================================================
        # 13. MDD 회복일
        # ====================================================
        #
        # MDD 시작 당시 최고가를
        # 종가가 다시 회복한 첫 번째 날짜
        #

        recovery_index = None
        recovery_date = pd.NaT

        if mdd_start_index is not None:

            recovery_price = df.loc[
                mdd_start_index,
                "고가"
            ]


            recovery_candidates = df[
                (df.index > mdd_index)
                &
                (
                    df["종가"]
                    >=
                    recovery_price
                )
            ]


            if len(recovery_candidates) > 0:

                recovery_index = (
                    recovery_candidates
                    .index[0]
                )

                recovery_date = df.loc[
                    recovery_index,
                    "날짜"
                ]


        # ====================================================
        # 14. 회복기간
        # ====================================================

        if mdd_start_index is not None:

            # -----------------------------------------------
            # 달력일
            # -----------------------------------------------

            if recovery_index is not None:

                recovery_calendar_days = (
                    df.loc[
                        recovery_index,
                        "날짜"
                    ]
                    -
                    df.loc[
                        mdd_start_index,
                        "날짜"
                    ]
                ).days

            else:

                recovery_calendar_days = (
                    df["날짜"].iloc[-1]
                    -
                    df.loc[
                        mdd_start_index,
                        "날짜"
                    ]
                ).days


            # -----------------------------------------------
            # 거래일
            # -----------------------------------------------

            if recovery_index is not None:

                recovery_trading_days = (
                    recovery_index
                    -
                    mdd_start_index
                )

            else:

                recovery_trading_days = (
                    len(df)
                    -
                    1
                    -
                    mdd_start_index
                )

        else:

            recovery_calendar_days = None
            recovery_trading_days = None


        # ====================================================
        # 15. 전체 투자기간
        # ====================================================

        start_date = df[
            "날짜"
        ].iloc[0]

        end_date = df[
            "날짜"
        ].iloc[-1]


        total_days = (
            end_date
            -
            start_date
        ).days


        years = (
            total_days
            /
            365.25
        )


        # ====================================================
        # 16. 수정주가 기준 수익률
        # ====================================================

        start_adjusted_price = (
            df["수정주가"]
            .iloc[0]
        )

        end_adjusted_price = (
            df["수정주가"]
            .iloc[-1]
        )


        total_return = (
            (
                end_adjusted_price
                /
                start_adjusted_price
            )
            - 1
        ) * 100


        # ====================================================
        # 17. CAGR
        # ====================================================

        if (
            years > 0
            and start_adjusted_price > 0
            and end_adjusted_price > 0
        ):

            cagr = (
                (
                    end_adjusted_price
                    /
                    start_adjusted_price
                )
                ** (1 / years)
                - 1
            ) * 100

        else:

            cagr = None


        # ====================================================
        # 18. 분석 결과 컬럼 추가
        # ====================================================

        df["MDD_시작일"] = format_date(
            mdd_start_date
        )

        df["MDD_저점일"] = format_date(
            mdd_low_date
        )

        df["회복일"] = format_date(
            recovery_date
        )


        # 기존 요구사항 유지
        # 회복기간 = 달력일

        if recovery_calendar_days is not None:

            df["회복기간"] = (
                recovery_calendar_days
            )

        else:

            df["회복기간"] = ""


        # 추가 정보
        df["회복기간_거래일"] = (
            recovery_trading_days
            if recovery_trading_days is not None
            else ""
        )


        # ====================================================
        # 19. 숫자 반올림
        # ====================================================

        df["최고가"] = (
            df["최고가"]
            .round(6)
        )

        df["고점_대비_하락률"] = (
            df["고점_대비_하락률"]
            .round(2)
        )

        df["MDD"] = (
            df["MDD"]
            .round(2)
        )


        # ====================================================
        # 20. ETF 분석 CSV 저장
        # ====================================================

        etf_name = csv_file.stem

        output_file = (
            OUTPUT_DIR
            /
            f"{etf_name}_analysis.csv"
        )


        df.to_csv(
            output_file,
            index=False,
            encoding=CSV_ENCODING
        )


        # ====================================================
        # 21. Summary 생성
        # ====================================================

        summary = {

            "ETF":
                etf_name,

            "시작일":
                format_date(
                    start_date
                ),

            "종료일":
                format_date(
                    end_date
                ),

            "운용기간_년":
                round(
                    years,
                    2
                ),

            "거래일수":
                len(df),

            "시작_수정주가":
                round(
                    start_adjusted_price,
                    6
                ),

            "종료_수정주가":
                round(
                    end_adjusted_price,
                    6
                ),

            "수익률_%":
                round(
                    total_return,
                    2
                ),

            "CAGR_%":
                round(
                    cagr,
                    2
                )
                if cagr is not None
                else None,

            "최고가":
                round(
                    df["고가"].max(),
                    6
                ),

            "최고가_발생일":
                format_date(
                    df.loc[
                        df["고가"].idxmax(),
                        "날짜"
                    ]
                ),

            "MDD_%":
                round(
                    mdd,
                    2
                ),

            "MDD_시작일":
                format_date(
                    mdd_start_date
                ),

            "MDD_저점일":
                format_date(
                    mdd_low_date
                ),

            "회복일":
                format_date(
                    recovery_date
                ),

            "회복기간_달력일":
                recovery_calendar_days
                if recovery_calendar_days is not None
                else "",

            "회복기간_거래일":
                recovery_trading_days
                if recovery_trading_days is not None
                else "",

            "현재_고점대비_%":
                round(
                    df[
                        "고점_대비_하락률"
                    ].iloc[-1],
                    2
                )
        }


        # ====================================================
        # 22. 콘솔 출력
        # ====================================================

        print(
            f"기간       : "
            f"{format_date(start_date)} ~ "
            f"{format_date(end_date)}"
        )

        print(
            f"최고가     : "
            f"{df['고가'].max():.6f}"
        )

        print(
            f"최고가 발생: "
            f"{format_date(df.loc[df['고가'].idxmax(), '날짜'])}"
        )

        print(
            f"수익률     : "
            f"{total_return:.2f}%"
        )

        if cagr is not None:

            print(
                f"CAGR       : "
                f"{cagr:.2f}%"
            )

        else:

            print(
                "CAGR       : N/A"
            )

        print(
            f"MDD        : "
            f"{mdd:.2f}%"
        )

        print(
            f"MDD 시작일 : "
            f"{format_date(mdd_start_date)}"
        )

        print(
            f"MDD 저점일 : "
            f"{format_date(mdd_low_date)}"
        )


        if pd.notna(recovery_date):

            print(
                f"회복일     : "
                f"{format_date(recovery_date)}"
            )

            print(
                f"회복기간   : "
                f"{recovery_calendar_days}일"
            )

            print(
                f"거래일     : "
                f"{recovery_trading_days}일"
            )

        else:

            print(
                "회복일     : "
                "아직 회복하지 못함"
            )

            if recovery_calendar_days is not None:

                print(
                    f"현재 경과  : "
                    f"{recovery_calendar_days}일"
                )


        print(
            f"분석파일   : "
            f"{output_file}"
        )


        return summary


    except Exception as e:

        print()
        print(
            f"❌ 오류 발생 : "
            f"{csv_file.name}"
        )

        print(
            f"오류 종류 : "
            f"{type(e).__name__}"
        )

        print(
            f"오류 내용 : "
            f"{e}"
        )

        return None


# ============================================================
# 23. 전체 ETF 처리
# ============================================================

def main():

    print()
    print("=" * 90)
    print("ETF 전체 CSV 분석")
    print("=" * 90)


    # ========================================================
    # 경로 출력
    # ========================================================

    print()
    print(
        f"프로그램 위치 : "
        f"{BASE_DIR}"
    )

    print(
        f"프로젝트 위치 : "
        f"{PROJECT_DIR}"
    )

    print(
        f"원본 데이터   : "
        f"{INPUT_DIR}"
    )

    print(
        f"분석 결과     : "
        f"{OUTPUT_DIR}"
    )


    # ========================================================
    # 원본 폴더 확인
    # ========================================================

    if not INPUT_DIR.exists():

        print()
        print(
            "❌ 원본 ETF 폴더가 없습니다."
        )

        print(
            f"경로 : {INPUT_DIR}"
        )

        return


    # ========================================================
    # 분석 폴더 생성
    # ========================================================

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


    # ========================================================
    # 원본 CSV 검색
    # ========================================================

    csv_files = sorted(
        INPUT_DIR.glob("*.csv")
    )


    # ========================================================
    # 분석 파일이 원본 폴더에 있을 경우 제외
    # ========================================================

    csv_files = [
        file
        for file in csv_files
        if not file.stem.endswith(
            "_analysis"
        )
    ]


    # summary.csv가 원본 폴더에 있을 경우 제외

    csv_files = [
        file
        for file in csv_files
        if file.name.lower()
        != "summary.csv"
    ]


    # ========================================================
    # CSV 없음
    # ========================================================

    if not csv_files:

        print()
        print(
            "❌ ETF CSV 파일이 없습니다."
        )

        print(
            f"검색 경로 : {INPUT_DIR}"
        )

        return


    # ========================================================
    # CSV 목록
    # ========================================================

    print()
    print(
        f"발견된 ETF CSV : "
        f"{len(csv_files)}개"
    )

    for file in csv_files:

        print(
            f"  └─ {file.name}"
        )


    # ========================================================
    # 전체 ETF 분석
    # ========================================================

    results = []

    success_count = 0
    error_count = 0


    for csv_file in csv_files:

        result = analyze_etf(
            csv_file
        )

        if result is not None:

            results.append(result)
            success_count += 1

        else:

            error_count += 1


    # ========================================================
    # 분석 결과 확인
    # ========================================================

    if not results:

        print()
        print(
            "❌ 정상적으로 분석된 ETF가 없습니다."
        )

        return


    # ========================================================
    # Summary DataFrame
    # ========================================================

    summary_df = pd.DataFrame(
        results
    )


    # ========================================================
    # 수익률 순 정렬
    # ========================================================

    summary_df = (
        summary_df
        .sort_values(
            by="수익률_%",
            ascending=False
        )
        .reset_index(drop=True)
    )


    # ========================================================
    # 순위 추가
    # ========================================================

    summary_df.insert(
        0,
        "순위",
        range(
            1,
            len(summary_df) + 1
        )
    )


    # ========================================================
    # Summary 저장
    # ========================================================

    summary_df.to_csv(
        SUMMARY_FILE,
        index=False,
        encoding=CSV_ENCODING
    )


    # ========================================================
    # 최종 출력
    # ========================================================

    print()
    print("=" * 90)
    print("🎉 전체 ETF 분석 완료")
    print("=" * 90)

    print(
        f"전체 CSV : "
        f"{len(csv_files)}개"
    )

    print(
        f"성공     : "
        f"{success_count}개"
    )

    print(
        f"실패     : "
        f"{error_count}개"
    )

    print()
    print(
        f"Summary 파일:"
    )

    print(
        f"{SUMMARY_FILE}"
    )


    # ========================================================
    # ETF Summary 출력
    # ========================================================

    print()
    print("=" * 150)
    print("ETF SUMMARY")
    print("=" * 150)


    display_columns = [

        "순위",
        "ETF",
        "시작일",
        "종료일",
        "운용기간_년",
        "수익률_%",
        "CAGR_%",
        "최고가",
        "최고가_발생일",
        "MDD_%",
        "MDD_시작일",
        "MDD_저점일",
        "회복일",
        "회복기간_달력일",
        "회복기간_거래일",
        "현재_고점대비_%"
    ]


    print(
        summary_df[
            display_columns
        ].to_string(
            index=False
        )
    )


    print()
    print("=" * 150)


# ============================================================
# 프로그램 실행
# ============================================================

if __name__ == "__main__":

    main()
# ```
