import os
import pandas as pd
from pathlib import Path

# 1. 경로 설정
BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
INPUT_DIR = PROJECT_DIR / "us" / "data" / "us_etf"

# TQQQ 분석 결과 저장 폴더
OUTPUT_DIR = INPUT_DIR / "analysis" / "TQQQ_analysis"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 2. 파라미터 설정
BUY_AMOUNT = 10_000_000  # 1회 매수 금액: 1,000만 원
STEP_PCT = 20.0           # 하락률 분할 매수 기준: 20% 단위 (-20%, -40%, -60%...)
PRICE_COL = '수정주가'     # 매수 및 수익률 산출 기준 컬럼 ('수정주가' 또는 '종가')
DATA_FILE = INPUT_DIR / "TQQQ.csv"                        # 입력 파일
OUTPUT_EXCEL = OUTPUT_DIR / "TQQQ_drawdown_analysis.xlsx" # 출력 엑셀 파일


def run_drawdown_backtest(file_path: Path, buy_amount: float, step: float, price_col: str):
    # CSV 읽기 (인코딩 예외 처리)
    try:
        df = pd.read_csv(file_path, encoding='utf-8-sig')
    except UnicodeDecodeError:
        df = pd.read_csv(file_path, encoding='cp949')

    # 컬럼명 앞뒤 공백 제거
    df.columns = df.columns.str.strip()

    # 날짜 정렬
    df['날짜'] = pd.to_datetime(df['날짜'])
    df = df.sort_values('날짜').reset_index(drop=True)

    # 백테스트 상태 변수
    total_invested = 0       # 총 누적 투자 금액 (원)
    total_shares = 0.0       # 총 누적 보유 주식 수
    triggered_levels = set() # 현재 고점 대비 이미 매수한 단계 (-20, -40 등)
    
    current_peak = -1.0      # 고점 추적용 변수
    trade_logs = []

    # 고가 컬럼이 없으면 수정주가/종가 활용
    peak_source_col = '고가' if '고가' in df.columns else price_col

    for idx, row in df.iterrows():
        date_str = row['날짜'].strftime('%Y-%m-%d')
        price = row[price_col]
        day_high = row[peak_source_col]

        # -------------------------------------------------------------
        # [핵심 로직 수정] 
        # 1. 신고가(최고가)를 갱신하면 고점을 업데이트하고 매수 기록을 완전히 리셋합니다.
        # -------------------------------------------------------------
        if day_high > current_peak:
            current_peak = day_high
            triggered_levels.clear() # 고점 갱신 시 매수 단계 초기화

        # 고점 대비 현재 하락률 계산 (%)
        if '고점_대비_하락률' in df.columns and pd.notna(row['고점_대비_하락률']):
            dd = float(row['고점_대비_하락률'])
        else:
            dd = ((price - current_peak) / current_peak) * 100.0

        abs_dd = abs(dd)

        # 현재 하락률 기준 매수 도달 단계 계산 (예: abs_dd가 25.5%면 target_level은 20)
        target_level = (int(abs_dd // step)) * int(step)

        # -------------------------------------------------------------
        # 2. 고점이 갱신되기 전까지는 각 단계(-20%, -40% 등)별로 딱 1번만 매수
        # -------------------------------------------------------------
        if target_level >= step:
            for level in range(int(step), target_level + 1, int(step)):
                if level not in triggered_levels:
                    # 매수 실행
                    shares_bought = buy_amount / price
                    total_shares += shares_bought
                    total_invested += buy_amount
                    triggered_levels.add(level) # 해당 단계 매수 완료 기록

                    trade_logs.append({
                        '날짜': date_str,
                        '매수단계': f"-{level}%",
                        '매수가격': round(price, 4),
                        '고점대비하락률(%)': round(dd, 2),
                        '매수금액(원)': buy_amount,
                        '매수수량': round(shares_bought, 4),
                        '누적투자금액(원)': total_invested,
                        '누적보유주식수': round(total_shares, 4)
                    })

    trade_df = pd.DataFrame(trade_logs)

    if total_invested == 0:
        print("TQQQ 데이터 중 최고가 대비 -20% 이상 하락한 구간이 존재하지 않습니다.")
        return trade_df, pd.DataFrame()

    # 최종 결과 계산
    final_price = df.iloc[-1][price_col]
    final_date = df.iloc[-1]['날짜'].strftime('%Y-%m-%d')
    final_valuation = total_shares * final_price
    total_profit = final_valuation - total_invested
    total_return_pct = (total_profit / total_invested) * 100

    summary_data = {
        '지표': [
            '분석 종목',
            '분석기간 시작일', 
            '분석기간 종료일', 
            '총 매수 횟수', 
            '총 투자 금액', 
            '최종 평가 금액', 
            '최종 손익금', 
            '최종 수익률(%)', 
            '최종 주가'
        ],
        '값': [
            'TQQQ',
            df.iloc[0]['날짜'].strftime('%Y-%m-%d'),
            final_date,
            len(trade_df),
            f"{total_invested:,.0f} 원",
            f"{round(final_valuation, 0):,.0f} 원",
            f"{round(total_profit, 0):,.0f} 원",
            f"{total_return_pct:.2f} %",
            f"{final_price:,.2f}"
        ]
    }
    summary_df = pd.DataFrame(summary_data)

    return trade_df, summary_df


def save_to_excel(trade_df: pd.DataFrame, summary_df: pd.DataFrame, output_path: Path):
    """성과 요약과 매수 내역 시트를 포함한 엑셀 파일 저장"""
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        summary_df.to_excel(writer, sheet_name='성과_요약', index=False)
        trade_df.to_excel(writer, sheet_name='매수_내역', index=False)

        # 열 너비 자동 조정
        ws_summary = writer.sheets['성과_요약']
        ws_summary.column_dimensions['A'].width = 22
        ws_summary.column_dimensions['B'].width = 25

        ws_trades = writer.sheets['매수_내역']
        col_widths = {'A': 14, 'B': 12, 'C': 14, 'D': 18, 'E': 18, 'F': 14, 'G': 18, 'H': 16}
        for col, width in col_widths.items():
            ws_trades.column_dimensions[col].width = width


if __name__ == "__main__":
    if not DATA_FILE.exists():
        print(f"TQQQ 파일이 존재하지 않습니다: {DATA_FILE}")
    else:
        # 백테스트 실행
        trades, summary = run_drawdown_backtest(
            file_path=DATA_FILE,
            buy_amount=BUY_AMOUNT,
            step=STEP_PCT,
            price_col=PRICE_COL
        )

        if not summary.empty:
            # 엑셀 저장
            save_to_excel(trades, summary, OUTPUT_EXCEL)

            print("=== TQQQ 백테스트 성과 요약 ===")
            print(summary.to_string(index=False))
            print(f"\n매수 내역 샘플 (상위 10건):")
            print(trades.head(10).to_string(index=False))
            print(f"\n엑셀 파일이 정상적으로 저장되었습니다:\n{OUTPUT_EXCEL}")