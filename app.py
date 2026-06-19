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
            
            product_col = 'Reported Product Name' if 'Reported Product Name' in df_target.columns else df_target.columns[1]
            st.caption(f"상품명 매칭 기준 열: `{product_col}`")
            
            target_products = df_target_filtered[product_col].dropna().unique().tolist()[:10]
            market_products = df_market_filtered[product_col].dropna().unique().tolist()[:10]

            matched_pairs = []
            
            if not anthropic_key:
                st.warning("⚠️ 사이드바에 Claude API Key를 입력하셔야 AI 유사도 평가 엔진이 가동됩니다.")
            else:
                if st.button("🤖 AI 유사도 평가 시작하기"):
                    with st.spinner("클로드 AI가 두 데이터의 상품명을 비교하여 무결성 검증을 수행하고 있습니다..."):
                        headers = {
                            "x-api-key": anthropic_key,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json"
                        }
                        
                        prompt_content = f"""
                        너는 데이터 분석가야. 아래 두 리스트를 비교해서 동일하거나 유사한 상품을 매칭해줘.
                        반드시 아래 JSON 배열 형식으로만 대답해:
                        [
                          {{"기준상품": "A", "경쟁사상품": "B", "유사도": "95%", "추천이유": "이유작성"}}
                        ]

                        [기준 기업 상품]: {target_products}
                        [시장/경쟁사 상품]: {market_products}
                        """
                        data = {
                            "model": "claude-3-5-sonnet-20241022",
                            "max_tokens": 1500,
                            "messages": [{"role": "user", "content": prompt_content}]
                        }
                        try:
                            res = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=data)
                            res_json = res.json()
                            
                            # API 에러 메시지가 있는지 먼저 확인하는 안전장치 추가!!
                            if 'error' in res_json:
                                st.error(f"❌ 클로드 API 서버 거절: {res_json['error'].get('message', '알 수 없는 에러')}")
                                st.info("💡 해결 팁: API Key가 정확한지, Anthropic 계정에 결제 카드 등록 및 크레딧(잔액)이 남아있는지 확인해 주세요.")
                            else:
                                raw_text = res_json['content'][0]['text']
                                start_idx = raw_text.find('[')
                                end_idx = raw_text.rfind(']') + 1
                                matched_pairs = json.loads(raw_text[start_idx:end_idx])
                                st.session_state['matched_pairs'] = matched_pairs
                                st.success("🤖 AI 유사도 매칭 완료!")
                        except Exception as e:
                            st.error(f"⚠️ 시스템 통신 오류: {e}")

            if 'matched_pairs' in st.session_state and len(matched_pairs) == 0:
                matched_pairs = st.session_state['matched_pairs']

            # --- STEP 4: 사용자 2차 검증 UI ---
            if matched_pairs:
                st.markdown("<div class='verified-box'><b>Step 4. 사용자 2차 확인 (Human-in-the-Loop)</b></div>", unsafe_allow_html=True)
                st.markdown("AI가 분석한 리스트입니다. **포함할 항목만 체크**해 주세요.")
                
                final_verified_market_products = []
                
                for idx, pair in enumerate(matched_pairs):
                    col1, col2, col3, col4 = st.columns([3, 3, 1, 3])
                    with col1: st.write(f"**기준:** {pair.get('기준상품')}")
                    with col2: st.write(f"**경쟁:** {pair.get('경쟁사상품')}")
                    with col3: st.write(f"🎯 {pair.get('유사도')}")
                    with col4:
                        is_checked = st.checkbox("포함하기", value=True, key=f"check_{idx}", help=pair.get('추천이유'))
                        if is_checked:
                            final_verified_market_products.append(pair.get('경쟁사상품'))

                # --- STEP 5: 최종 정밀 계산 ---
                st.divider()
                st.subheader("📊 최종 검증된 데이터 기반 분석 결과")
                
                if final_verified_market_products:
                    df_market_final = df_market_filtered[df_market_filtered[product_col].isin(final_verified_market_products)]
                else:
                    df_market_final = df_market_filtered

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

                def create_word_report():
                    doc = Document()
                    doc.add_heading('TRIDGE AI-HUMAN HYBRID REPORT', level=1)
                    doc.add_heading('AI 상품 매칭 및 검증 기반 원가 진단 보고서', level=2)
                    doc.add_paragraph(f"분석 카테고리: {', '.join(selected_categories)}")
                    doc.add_paragraph(f"인간 검증 완료된 매칭 상품 수: {len(final_verified_market_products)}개\n")
                    
                    doc.add_heading('💡 정밀 진단 결과', level=3)
                    doc.add_paragraph(f"시장 대비 구매 격차는 {gap_imp:.1f}%p 개선되었으며, 누적 절감액은 ${saved_usd:,.0f}입니다.")
                    
                    bio = io.BytesIO()
                    doc.save(bio)
                    return bio.getvalue()

                st.download_button(
                    label="📄 2차 검증 완료된 최고정밀 전략 보고서 다운로드",
                    data=create_word_report(),
                    file_name="트릿지_AI검증_보고서.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
