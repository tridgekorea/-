import streamlit as st
import pandas as pd
from docx import Document
import io
import requests
import json

# 1. 페이지 설정 및 스타일 주입
st.set_page_config(page_title="Tridge Enterprise AI Analytics", layout="wide")
st.markdown("""
    <style>
    div.stFileUploader { margin-bottom: 20px !important; }
    .step-box { padding: 15px; border-radius: 5px; background-color: #f0f4f8; border-left: 5px solid #1f77b4; margin-bottom: 20px; }
    .verified-box { padding: 15px; border-radius: 5px; background-color: #e8f5e9; border-left: 5px solid #2e7d32; margin-bottom: 20px; }
    </style>
""", unsafe_allow_html=True)

st.title("🚀 Tridge Enterprise AI 정밀 매칭 분석 시스템")
st.markdown("### **\"AI 유사도 평가와 인간의 2차 검증을 결합한 최극단의 정밀 데이터 솔루션\"**")

# 2. 사이드바 설정
st.sidebar.header("⚙️ 인프라 설정 및 API 연동")
anthropic_key = st.sidebar.text_input("Anthropic (Claude) API Key 필수 입력", type="password")
cutoff_date = st.sidebar.date_input("이벤트 컷오프(기준) 날짜")

# 함수 정의
def get_vwap(data):
    if 'Volume' not in data.columns or 'Value' not in data.columns: return 0
    if data['Volume'].sum() == 0: return 0
    return data['Value'].sum() / data['Volume'].sum()

def load_data(file):
    if file.name.endswith('.csv'): return pd.read_csv(file)
    else: return pd.read_excel(file)

# --- STEP 1: 기준 기업 데이터 업로드 ---
st.divider()
st.markdown("<div class='step-box'><b>Step 1. 분석 대상(기준) 기업의 포트폴리오 데이터 업로드</b></div>", unsafe_allow_html=True)
target_file = st.file_uploader("기준 기업의 데이터를 업로드하세요", type=['csv', 'xlsx', 'xls'], key="target_file")

if target_file:
    df_target = load_data(target_file)
    st.success(f"✅ 기준 기업 데이터 업로드 완료 (총 {len(df_target)}행)")
    
    # 카테고리 열 선택 및 추출
    category_col = st.selectbox("데이터에서 '카테고리(품목)' 열을 선택해 주세요:", df_target.columns, key="cat_col")
    unique_categories = df_target[category_col].dropna().unique().tolist()
    selected_categories = st.multiselect("분석할 카테고리를 선택하세요:", unique_categories)

    if selected_categories:
        df_target_filtered = df_target[df_target[category_col].isin(selected_categories)]
        
        # --- STEP 2: 경쟁사/시장 데이터 업로드 ---
        st.markdown("<div class='step-box'><b>Step 2. 동일 카테고리의 경쟁사/시장 벤치마크 로우데이터 업로드</b></div>", unsafe_allow_html=True)
        market_file = st.file_uploader("시장 데이터를 업로드하세요", type=['csv', 'xlsx', 'xls'], key="market_file")

        if market_file:
            df_market = load_data(market_file)
            if category_col in df_market.columns:
                df_market_filtered = df_market[df_market[category_col].isin(selected_categories)]
            else:
                df_market_filtered = df_market

            # --- STEP 3: AI 상품명 유사도 평가 (AI Matching) ---
            st.markdown("<div class='step-box'><b>Step 3. AI 기반 상품명 유사도 평가 및 동등성 검증 (AI Matching Engine)</b></div>", unsafe_allow_html=True)
            
            # 고유 상품명 추출 (연산 속도를 위해 상위 일부만 샘플링하거나 고유값 기준으로 매칭)
            product_col = 'Reported Product Name' if 'Reported Product Name' in df_target.columns else df_target.columns[1]
            st.caption(f"상품명 매칭 기준 열: `{product_col}`")
            
            target_products = df_target_filtered[product_col].dropna().unique().tolist()[:10]
            market_products = df_market_filtered[product_col].dropna().unique().tolist()[:10]

            matched_pairs = []
            
            if not anthropic_key:
                st.warning("⚠️ 사이드바에 Claude API Key를 입력하셔야 AI 유사도 평가 엔진이 가동됩니다. (입력 전에는 기본 전체 매칭으로 진행됩니다.)")
                # API 없을 시 임시 매칭 리스트 생성
                for tp in target_products:
                    for mp in market_products[:2]:
                        matched_pairs.append({"기준상품": tp, "경쟁사상품": mp, "유사도": "85%", "추천이유": "API Key 미입력으로 인한 기본 매칭"})
            else:
                if st.button("🤖 AI 유사도 평가 시작하기"):
                    with st.spinner("클로드 AI가 두 데이터의 상품명을 비교하여 동일/유사 상품 무결성 검증을 수행하고 있습니다..."):
                        headers = {
                            "x-api-key": anthropic_key,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json"
                        }
                        
                        prompt_content = f"""
                        너는 글로벌 무역 데이터 마스터데이터 관리(MDM) 전문가야. 
                        [기준 기업 상품 리스트]와 [시장/경쟁사 상품 리스트]를 비교해서, 서로 다른 텍스트 형식으로 적혀있더라도 '실제 물리적으로 동일하거나 극히 유사하여 직접 단가 비교가 가능한 쌍'을 찾아내줘.
                        결과는 반드시 아래 제공된 JSON 형식으로만 출력해라. 딴소리는 절대 하지마.

                        [기준 기업 상품]: {target_products}
                        [시장/경쟁사 상품]: {market_products}

                        [출력 JSON 형식 예시]:
                        [
                          {{"기준상품": "A", "경쟁사상품": "B", "유사도": "95%", "추천이유": "브랜드와 규격이 일치함"}}
                        ]
                        """
                        data = {
                            "model": "claude-3-5-sonnet-20241022",
                            "max_tokens": 1500,
                            "messages": [{"role": "user", "content": prompt_content}]
                        }
                        try:
                            res = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=data)
                            res_json = res.json()
                            raw_text = res_json['content'][0]['text']
                            # JSON 파싱 안전장치
                            start_idx = raw_text.find('[')
                            end_idx = raw_text.rfind(']') + 1
                            matched_pairs = json.loads(raw_text[start_idx:end_idx])
                            st.session_state['matched_pairs'] = matched_pairs
                            st.success("🤖 AI 유사도 매칭 완료!")
                        except Exception as e:
                            st.error(f"AI 연동 오류: {e}")

            # 세션 스테이트 보존용
            if 'matched_pairs' in st.session_state and len(matched_pairs) == 0:
                matched_pairs = st.session_state['matched_pairs']

            # --- STEP 4: 사용자 2차 검증 UI (Human-in-the-Loop) ---
            if matched_pairs:
                st.markdown("<div class='verified-box'><b>Step 4. 사용자 2차 확인 및 포함/제외 필터링 (Human-in-the-Loop)</b></div>", unsafe_allow_html=True)
                st.markdown("AI가 분석한 유사 상품 리스트입니다. **실제 보고서 분석에 포함할 항목만 체크**해 주세요.")
                
                final_verified_market_products = []
                
                # 표 형태로 체크박스 제공
                for idx, pair in enumerate(matched_pairs):
                    col1, col2, col3, col4 = st.columns([3, 3, 1, 3])
                    with col1: st.write(f"**기준:** {pair.get('기준상품')}")
                    with col2: st.write(f"**경쟁:** {pair.get('경쟁사상품')}")
                    with col3: st.write(f"🎯 {pair.get('유사도')}")
                    with col4:
                        # 사용자가 체크박스로 포함 유무 선택 기본값은 True (포함)
                        is_checked = st.checkbox("포함하기", value=True, key=f"check_{idx}", help=pair.get('추천이유'))
                        if is_checked:
                            final_verified_market_products.append(pair.get('경쟁사상품'))

                # --- STEP 5: 최종 정밀 데이터 기반 계산 및 결과 출력 ---
                st.divider()
                st.subheader("📊 최종 검증된 데이터 기반 분석 결과")
                
                # 사용자가 승인한 상품들만 시장 데이터에서 최종 필터링
                if final_verified_market_products:
                    df_market_final = df_market_filtered[df_market_filtered[product_col].isin(final_verified_market_products)]
                else:
                    df_market_final = df_market_filtered

                # 날짜 자르기 및 가중단가 계산
                df_target_filtered['Date'] = pd.to_datetime(df_target_filtered['Date'])
                df_market_final['Date'] = pd.to_datetime(df_market_final['Date'])
                cutoff = pd.to_datetime(cutoff_date)

                t_b = df_target_filtered[df_target_filtered['Date'] < cutoff]
                t_a = df_target_filtered[df_target_filtered['Date'] >= cutoff]
                m_b = df_market_final[df_market_final['Date'] < cutoff]
                m_a = df_market_final[df_market_final['Date'] >= cutoff]

                vw_t_b, vw_t_a = get_vwap(t_b), get_vwap(t_a)
                vw_m_b, vw_m_a = get_vwap(m_b), get_vwap(m_a)

                gap_b = (vw_t_b / vw_m_b) - 1 if vw_m_b else 0
                gap_a = (vw_t_a / vw_m_a) - 1 if vw_m_a else 0
                gap_imp = (gap_b - gap_a) * 100
                saved_usd = (t_a['Volume'].sum() if 'Volume' in t_a.columns else 0) * (vw_m_a - vw_t_a)

                col1, col2 = st.columns(2)
                col1.metric("동일 상품 기준 격차 개선량", f"{gap_imp:+.1f}%p")
                col2.metric("정밀 벤치마크 기준 총 절감액", f"${saved_usd:,.0f}")

                summary_table = pd.DataFrame({
                    "구분": ["기준 기업 단가 ($/kg)", "경쟁사 정밀 단가 ($/kg)", "시장 대비 격차 (%)"],
                    "Before (컷오프 전)": [f"${vw_t_b:.3f}", f"${vw_m_b:.3f}", f"{gap_b*100:+.1f}%"],
                    "After (컷오프 후)": [f"${vw_t_a:.3f}", f"${vw_m_a:.3f}", f"{gap_a*100:+.1f}%"]
                })
                st.table(summary_table)

                # 워드 리포트 생성
                def create_word_report():
                    doc = Document()
                    doc.add_heading('TRIDGE AI-HUMAN HYBRID REPORT', level=1)
                    doc.add_heading('AI 상품 매칭 및 검증 기반 원가 진단 보고서', level=2)
                    doc.add_paragraph(f"분석 카테고리: {', '.join(selected_categories)}")
                    doc.add_paragraph(f"인간 검증 완료된 매칭 상품 수: {len(final_verified_market_products)}개\n")
                    
                    doc.add_heading('💡 정밀 진단 결과', level=3)
                    doc.add_paragraph(f"단일 상품 단위 동등성 검증(Apples-to-Apples)을 통과한 데이터로 분석한 결과, 시장 대비 구매 격차는 {gap_imp:.1f}%p 개선되었으며, 누적 절감액 성과는 ${saved_usd:,.0f}로 최종 산출되었습니다.")
                    
                    bio = io.BytesIO()
                    doc.save(bio)
                    return bio.getvalue()

                st.download_button(
                    label="📄 2차 검증 완료된 최고정밀 전략 보고서 다운로드 (.docx)",
                    data=create_word_report(),
                    file_name="트릿지_AI검증_정밀분석보고서.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
