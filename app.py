import streamlit as st
import pandas as pd
from docx import Document
import io

# 1. 앱 기본 설정 및 제목
st.set_page_config(page_title="Tridge Analysis Playbook", layout="wide")
st.title("📊 통합 데이터 분석 및 전략 리포트 자동화")
st.markdown("**부제 — 절대값을 버리고, 시장 대비 위치를 측정하라**")

# 2. 파일 업로드 섹션
st.sidebar.header("1. 데이터 업로드 및 설정")
uploaded_file = st.sidebar.file_uploader("Tridge CSV 데이터를 업로드하세요", type=['csv', 'xlsx'])

target_company = st.sidebar.text_input("분석 대상 기업명 (예: 샘표식품)")
cutoff_date = st.sidebar.date_input("이벤트 컷오프 날짜")

if uploaded_file and target_company:
    # 데이터 읽기
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
        
    st.subheader("데이터 미리보기")
    st.dataframe(df.head())

    # --- 핵심 연산 로직 (Analysis Playbook) ---
    # 실제 데이터 컬럼명에 맞춰 아래 'Company', 'Date', 'Value', 'Weight' 등을 수정하여 사용합니다.
    try:
        # 데이터 타입 변환 및 전처리 (예시 컬럼명 사용)
        df['Date'] = pd.to_datetime(df['Date'])
        cutoff = pd.to_datetime(cutoff_date)
        
        # Before / After 분할
        df_before = df[df['Date'] < cutoff]
        df_after = df[df['Date'] >= cutoff]

        # 계산 함수: 물량가중 평균 단가 산출
        def get_vwap(data):
            if data['Weight'].sum() == 0: return 0
            return data['Value'].sum() / data['Weight'].sum()

        # 대상 기업 데이터 vs 벤치마크(대상 제외) 데이터 분리
        target_before = df_before[df_before['Company'].str.contains(target_company, na=False)]
        target_after = df_after[df_after['Company'].str.contains(target_company, na=False)]
        
        market_before = df_before[~df_before['Company'].str.contains(target_company, na=False)]
        market_after = df_after[~df_after['Company'].str.contains(target_company, na=False)]

        # 물량가중 단가 계산
        vw_target_before = get_vwap(target_before)
        vw_target_after = get_vwap(target_after)
        vw_market_before = get_vwap(market_before)
        vw_market_after = get_vwap(market_after)

        # 격차(Premium) 계산: (대상/시장) - 1
        gap_before = (vw_target_before / vw_market_before) - 1 if vw_market_before else 0
        gap_after = (vw_target_after / vw_market_after) - 1 if vw_market_after else 0
        gap_improvement = (gap_before - gap_after) * 100 # %p 개선량 (양수일수록 우위)

        # 절감액 산출 (Σ물량 × (시장단가 − 대상단가))
        saved_usd = target_after['Weight'].sum() * (vw_market_after - vw_target_after)

        # --- 대시보드 화면 출력 ---
        st.divider()
        st.subheader(f"💡 {target_company} 성과 요약 (컷오프: {cutoff_date})")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("시장 대비 단가 격차 개선", f"+{gap_improvement:.1f}%p", "격차 축소 및 우위 확보")
        col2.metric("시장 평균가 대비 절감액", f"${saved_usd:,.0f}", "After 기간 기준")
        col3.metric("시장 단가 변동 (시장 노이즈)", f"${vw_market_before:.2f} → ${vw_market_after:.2f}", "시장 전체 공통 요인")

        # --- 워드(.docx) 리포트 생성 기능 ---
        st.divider()
        st.subheader("📥 전략 보고서 다운로드")
        st.write("위 분석 결과를 바탕으로 샘표식품 초기미팅 형태의 전략 리포트를 생성합니다.")

        def create_word_report():
            doc = Document()
            doc.add_heading(f'{target_company} 수입 원가 및 소싱 경쟁력 분석 보고서', 0)
            
            doc.add_heading('1. 핵심 성과 요약', level=1)
            doc.add_paragraph(f"이벤트({cutoff_date}) 기점, 시장 대비 단가 격차가 {gap_improvement:.1f}%p 개선되었습니다.")
            doc.add_paragraph(f"시장 평균가 대비 약 ${saved_usd:,.0f}의 비용을 절감한 것으로 분석됩니다.")
            
            doc.add_heading('2. 상세 단가 변동 내역 (물량가중 평균 기준)', level=1)
            doc.add_paragraph(f"- 벤치마크(시장) 단가: ${vw_market_before:.2f}/kg → ${vw_market_after:.2f}/kg")
            doc.add_paragraph(f"- {target_company} 단가: ${vw_target_before:.2f}/kg → ${vw_target_after:.2f}/kg")
            
            doc.add_heading('3. 전략 컨설턴트 분석 (Action Item)', level=1)
            doc.add_paragraph("본 개선 성과는 원자재 하락 등 시장 공통 요인을 벤치마크(ex-subject)로 철저히 통제한 후 도출된 결과로, 고객사의 성공적인 소싱 전략 다변화를 증명합니다. (단, 본 분석은 인과관계가 아닌 시점의 동행성을 바탕으로 합니다.)")
            doc.add_paragraph("→ 트릿지 데이터를 활용하여 단가가 지속 상승 중인 취약 품목의 대체 소싱처 발굴을 제안합니다.")
            
            bio = io.BytesIO()
            doc.save(bio)
            return bio.getvalue()

        docx_file = create_word_report()
        st.download_button(
            label="보고서 다운로드 (.docx)",
            data=docx_file,
            file_name=f"{target_company}_전략보고서.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    except Exception as e:
        st.error(f"데이터 계산 중 오류가 발생했습니다. CSV 파일의 열 이름(Company, Date, Value, Weight 등)이 맞는지 확인해 주세요. (상세 오류: {e})")
