import os
import pandas as pd
from pathlib import Path

# 1. 경로 설정
BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
INPUT_DIR = PROJECT_DIR / "us" / "data" / "us_etf"

# 분석 결과 저장 폴더
OUTPUT_DIR = INPUT_DIR / "analysis" / "multi_etf_analysis"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 2. 파라미터 설정
BUY_AMOUNT = 10_000_000  # 1회 매수 금액: 1,000만 원
STEPS = [-5, -10, -15, -20, -25, -30, -35, -40, -45, -50] # 테스트 단계별 단위 (%)
PRICE_COL = '수정주가'     # 매수 및 수익률 산출 기준 컬럼
TARGET_SYMBOLS = ['TQQQ', 'SPY', 'QLD'] # 대상 종목 리스트
OUTPUT_EXCEL = OUTPUT_DIR / "Multi_ETF_drawdown_analysis.xlsx"


def run_drawdown_backtest_for_step(symbol: str, df: pd.DataFrame, buy_amount: float, step: float, price_col: str):
    """특정 종목 및 step(-5%~-50%)에 대한 백테스트 수행"""
    abs_step = abs(step)
    
    total_invested = 0       # 총 누적 투자 금액 (원)
    total_shares = 0.0       # 총 누적 보유 주식 수
    triggered_levels = set() # 현재 고점 대비 이미 매수한 단계
    current_peak = -1.0      # 고점 추적 변수
    trade_logs = []

    peak_source_col = '고가' if '고가' in df.columns else price_col

    for idx, row in df.iterrows():
        date_str = row['날짜'].strftime('%Y-%m-%d')
        price = row[price_col]
        day_high = row[peak_source_col]

        # 신고가 갱신 시 고점 업데이트 및 매수 단계 리셋
        if day_high > current_peak:
            current_peak = day_high
            triggered_levels.clear()

        # 고점 대비 하락률 계산
        if '고점_대비_하락률' in df.columns and pd.notna(row['고점_대비_하락률']):
            dd = float(row['고점_대비_하락률'])
        else:
            dd = ((price - current_peak) / current_peak) * 100.0

        abs_dd = abs(dd)
        target_level = (int(abs_dd // abs_step)) * int(abs_step)

        # 고점 갱신 전까지 해당 단계별로 딱 1번만 매수
        if target_level >= abs_step:
            for level in range(int(abs_step), target_level + 1, int(abs_step)):
                if level not in triggered_levels:
                    shares_bought = buy_amount / price
                    total_shares += shares_bought
                    total_invested += buy_amount
                    triggered_levels.add(level)

                    trade_logs.append({
                        '종목': symbol,
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

    # 성과 지표 산출
    if total_invested == 0:
        summary = {
            '종목': symbol,
            '구간 구분': f"-{abs_step}% 단위",
            '시트명': f"{symbol}_-{abs_step}-테스트",
            '총 매수 횟수': 0,
            '총 투자 금액': 0,
            '최종 평가 금액': 0,
            '최종 손익금': 0,
            '최종 수익률(%)': 0.0,
            '최종 주가': df.iloc[-1][price_col] if not df.empty else 0
        }
    else:
        final_price = df.iloc[-1][price_col]
        final_valuation = total_shares * final_price
        total_profit = final_valuation - total_invested
        total_return_pct = (total_profit / total_invested) * 100.0

        summary = {
            '종목': symbol,
            '구간 구분': f"-{abs_step}% 단위",
            '시트명': f"{symbol}_-{abs_step}-테스트",
            '총 매수 횟수': len(trade_df),
            '총 투자 금액': total_invested,
            '최종 평가 금액': round(final_valuation, 0),
            '최종 손익금': round(total_profit, 0),
            '최종 수익률(%)': round(total_return_pct, 2),
            '최종 주가': final_price
        }

    return trade_df, summary


def main():
    summary_list = []
    trade_results = {}

    for symbol in TARGET_SYMBOLS:
        file_path = INPUT_DIR / f"{symbol}.csv"

        if not file_path.exists():
            print(f"[{symbol}] 파일이 존재하지 않아 건너뜁니다: {file_path}")
            continue

        # CSV 읽기
        try:
            df = pd.read_csv(file_path, encoding='utf-8-sig')
        except UnicodeDecodeError:
            df = pd.read_csv(file_path, encoding='cp949')

        df.columns = df.columns.str.strip()
        df['날짜'] = pd.to_datetime(df['날짜'])
        df = df.sort_values('날짜').reset_index(drop=True)

        print(f"[{symbol}] 백테스트 진행 중...")

        # 각 단계별 백테스트 실행 (-5, -10, ..., -50)
        for step in STEPS:
            sheet_name = f"{symbol}_-{abs(step)}-테스트"
            trades, summary = run_drawdown_backtest_for_step(
                symbol=symbol,
                df=df,
                buy_amount=BUY_AMOUNT,
                step=step,
                price_col=PRICE_COL
            )
            summary_list.append(summary)
            trade_results[sheet_name] = trades

    if not summary_list:
        print("분석할 유효한 CSV 데이터가 없습니다.")
        return

    summary_df = pd.DataFrame(summary_list)

    # 엑셀 저장 (성과요약 + 종목별/단계별 시트)
    with pd.ExcelWriter(OUTPUT_EXCEL, engine='openpyxl') as writer:
        # 1. 성과요약 시트 작성 (종목별, 단계별 결과 한눈에 보기)
        summary_df.to_excel(writer, sheet_name='성과요약', index=False)
        
        # 2. 각 종목/단계별 매수 내역 시트 작성
        for sheet_name, trades_df in trade_results.items():
            if trades_df.empty:
                pd.DataFrame({'안내': ['해당 하락 구간 조건에 일치하는 매수 내역이 없습니다.']}).to_excel(
                    writer, sheet_name=sheet_name, index=False
                )
            else:
                trades_df.to_excel(writer, sheet_name=sheet_name, index=False)

        # 열 너비 자동 조정
        for sheet_name in writer.sheets:
            ws = writer.sheets[sheet_name]
            for col in ws.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = col[0].column_letter
                ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    print("\n=== TQQQ, SPY, QLD 구간별 백테스트 완료 ===")
    print(summary_df.head(15).to_string(index=False)) # 샘플 요약 출력
    print(f"\n엑셀 파일이 저장되었습니다:\n{OUTPUT_EXCEL}")


if __name__ == "__main__":
    main()