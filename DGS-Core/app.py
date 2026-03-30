import streamlit as st
import json
import concurrent.futures
from openai import OpenAI
from anthropic import Anthropic

# ==========================================
# 1. UI 초기 설정 및 사이드바
# ==========================================
st.set_page_config(page_title="DGS-Core v2.0", page_icon="🏛️", layout="wide")

with st.sidebar:
    st.header("🔑 API Keys 설정")
    st.caption("시스템 구동을 위해 API 키가 필요합니다. (저장되지 않습니다)")
    openai_key = st.text_input("OpenAI API Key (GPT-4o)", type="password")
    anthropic_key = st.text_input("Anthropic API Key (Claude)", type="password")

# ==========================================
# 2. 시스템 프롬프트 정의
# ==========================================
MEDIATOR_PROMPT = """
당신은 DGS-Core 시스템의 '질문 설계자'다. 사용자 쿼리를 분석하여, 각 AI의 훈련 철학이 가장 격렬하게 충돌할 질문으로 재설계하라.
반드시 아래 JSON 형식으로만 답변하라:
{{
  "designed_query": "[최종 설계 질문]",
  "conflict_axis": "[핵심 가치 충돌 축]",
  "meta_context": "[독해를 위한 최소 맥락]"
}}
사용자 쿼리: {user_query}
"""

RAW_PROMPT = """
아래 질문에 대해 중립화 시도나 회피 없이, 당신의 논리 구조가 도달하는 방향으로 명확히 응답하라.
질문: {designed_query}
"""

CROSS_EXAM_PROMPT = """
아래는 동일한 질문에 대한 다른 AI의 응답이다. 요약 없이 다음 기준으로 비판하라:
① 논리적 비약 ② 간과된 변수 ③ 가치 편향 ④ 극단적 시나리오에서의 맹점

[비판 대상 응답]
{opponent_response}
"""

# ==========================================
# 3. API 통신 함수
# ==========================================
def call_gpt(prompt: str, is_json: bool = False) -> str:
    client = OpenAI(api_key=openai_key)
    response = client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"} if is_json else {"type": "text"},
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

def call_claude(prompt: str) -> str:
    client = Anthropic(api_key=anthropic_key)
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text

# ==========================================
# 4. 파이프라인 엔진
# ==========================================
def run_dgs_pipeline(user_query: str):
    # STEP 1: 중재자 질문 설계 (GPT)
    mediator_raw = call_gpt(MEDIATOR_PROMPT.format(user_query=user_query), is_json=True)
    meta_data = json.loads(mediator_raw)
    designed_query = meta_data["designed_query"]

    raw_prompt = RAW_PROMPT.format(designed_query=designed_query)

    # STEP 2: 병렬 Raw 응답 수집
    with concurrent.futures.ThreadPoolExecutor() as executor:
        f_gpt    = executor.submit(call_gpt, raw_prompt)
        f_claude = executor.submit(call_claude, raw_prompt)
        raw_results = [f_gpt.result(), f_claude.result()]

    # STEP 3: 교차 비판
    with concurrent.futures.ThreadPoolExecutor() as executor:
        f_c1 = executor.submit(call_gpt,    CROSS_EXAM_PROMPT.format(opponent_response=raw_results[1]))
        f_c2 = executor.submit(call_claude, CROSS_EXAM_PROMPT.format(opponent_response=raw_results[0]))
        critique_results = [f_c1.result(), f_c2.result()]

    return meta_data, raw_results, critique_results

# ==========================================
# 5. 메인 화면 렌더링
# ==========================================
st.title("🏛️ DGS-Core v2.0: 불협화음 거버넌스 시스템")
st.caption("> *\"이 시스템은 답을 생산하지 않는다. 사고의 재료를 공급한다.\"*")

user_query = st.text_input("질문을 입력하세요:", placeholder="당신의 철학과 맞닿은 가장 날카로운 질문을 던져보세요.")

if st.button("시스템 가동 (Run DGS)"):
    if not (openai_key and anthropic_key):
        st.error("좌측 사이드바에 API 키 2개를 모두 입력해야 시스템이 가동됩니다.")
    elif user_query:
        with st.spinner("지성들을 소환하고 논리를 충돌시키는 중입니다. (약 15~30초 소요)..."):
            try:
                meta_data, raw_results, critique_results = run_dgs_pipeline(user_query)

                st.success("응답 수집 및 교차 비판이 완료되었습니다.")
                st.markdown(f"**실제 에이전트들에게 던져진 설계 질문:** `{meta_data['designed_query']}`")

                with st.expander("💡 독해 보조 가이드 (Reading Guide) - 클릭하여 펼치기", expanded=False):
                    st.markdown(f"**예상 충돌 축:** {meta_data['conflict_axis']}")
                    st.markdown(f"**메타 맥락:** {meta_data['meta_context']}")

                st.markdown("---")

                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("🤖 GPT-4o")
                    st.container(border=True).write(raw_results[0])
                with col2:
                    st.subheader("🧠 Claude")
                    st.container(border=True).write(raw_results[1])

                st.markdown("---")
                st.subheader("⚔️ 교차 비판 로그 (Cross-Examination)")

                with st.expander("GPT-4o ➔ Claude 비판 로그", expanded=False):
                    st.write(critique_results[0])
                with st.expander("Claude ➔ GPT-4o 비판 로그", expanded=False):
                    st.write(critique_results[1])

                st.markdown("---")
                st.markdown("<h4 style='text-align: center; color: gray;'>이 불협화음 속에서 당신이 발견한 제3의 길은 무엇입니까?</h4>", unsafe_allow_html=True)

            except Exception as e:
                st.error(f"시스템 구동 중 오류가 발생했습니다. 에러 내용: {e}")
    else:
        st.warning("질문을 입력해주세요.")
