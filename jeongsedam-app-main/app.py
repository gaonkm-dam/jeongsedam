import streamlit as st
import json
import sqlite3
import time
from datetime import datetime, date
import os

from openai import OpenAI

from modules.mobile_ui import inject_mobile_css, copy_button, quick_ai_links
from modules.image_ai import render_image_ai
from typing import Any, Dict, Optional


from modules.action_buttons import render_ai_actions
from modules.video_ai import render_video_ai
from modules.export_utils import render_download_buttons



# =========================
# Page
# =========================
st.set_page_config(page_title="정세담 퍼포먼스 시스템", layout="wide")
inject_mobile_css()

# =========================
# OpenAI
# =========================
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY")
)

# =========================
# DB (SQLite)
# =========================
DB_PATH = "meetings.db"

def db_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_date TEXT NOT NULL,
            meeting_time TEXT NOT NULL,
            meeting_title TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            result_json TEXT NOT NULL,
            locked INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn

CONN = db_conn()

def db_insert_meeting(meeting_date: str, meeting_time: str, meeting_title: str,
                      payload: dict, result: dict, locked: int = 0) -> int:
    cur = CONN.cursor()
    cur.execute("""
        INSERT INTO meetings (meeting_date, meeting_time, meeting_title, payload_json, result_json, locked, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        meeting_date,
        meeting_time,
        meeting_title,
        json.dumps(payload, ensure_ascii=False),
        json.dumps(result, ensure_ascii=False),
        locked,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ))
    CONN.commit()
    return cur.lastrowid

def db_update_lock(meeting_id: int, locked: int):
    CONN.execute("UPDATE meetings SET locked=? WHERE id=?", (locked, meeting_id))
    CONN.commit()

def db_list_by_date(meeting_date: str):
    cur = CONN.cursor()
    cur.execute("""
        SELECT id, meeting_time, meeting_title, locked, created_at
        FROM meetings
        WHERE meeting_date=?
        ORDER BY meeting_time ASC, id ASC
    """, (meeting_date,))
    return cur.fetchall()

def db_load(meeting_id: int):
    cur = CONN.cursor()
    cur.execute("""
        SELECT id, meeting_date, meeting_time, meeting_title, payload_json, result_json, locked, created_at
        FROM meetings
        WHERE id=?
    """, (meeting_id,))
    row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "meeting_date": row[1],
        "meeting_time": row[2],
        "meeting_title": row[3],
        "payload": json.loads(row[4]),
        "result": json.loads(row[5]),
        "locked": bool(row[6]),
        "created_at": row[7],
    }

def db_search(keyword: str, limit: int = 30):
    kw = f"%{keyword}%"
    cur = CONN.cursor()
    cur.execute("""
        SELECT id, meeting_date, meeting_time, meeting_title, locked, created_at
        FROM meetings
        WHERE meeting_title LIKE ? OR payload_json LIKE ? OR result_json LIKE ?
        ORDER BY id DESC
        LIMIT ?
    """, (kw, kw, kw, limit))
    return cur.fetchall()

# =========================
# JSON robust parse
# =========================
def _strip_code_fences(s: str) -> str:
    s = (s or "").strip()
    if s.startswith("```"):
        s = s.replace("```json", "").replace("```", "").strip()
    return s

def try_parse_json(s: str) -> Optional[dict]:
    s = _strip_code_fences(s)
    try:
        return json.loads(s)
    except Exception:
        return None

def call_ai_json(prompt: str, model: str, max_tokens: int = 2600) -> (Optional[dict], str):
    res = client.responses.create(
        model=model,
        input=prompt,
        max_output_tokens=max_tokens
    )
    raw = getattr(res, "output_text", "") or ""
    data = try_parse_json(raw)
    if data is not None:
        return data, raw

    # retry once: force JSON only
    reprompt = f"""
너는 반드시 JSON만 출력한다. 설명/마크다운/코드블록/주석 금지.
아래 스키마를 지켜서 '완전한 JSON'만 다시 출력해.

원문(잘못된 출력):
{raw}
"""
    res2 = client.responses.create(
        model=model,
        input=reprompt,
        max_output_tokens=max_tokens
    )
    raw2 = getattr(res2, "output_text", "") or ""
    data2 = try_parse_json(raw2)
    return data2, raw2

# =========================
# Session State
# =========================
def ss_init():
    defaults = {
        "current_meeting_id": None,
        "current_result": None,
        "current_payload": None,
        "current_locked": False,
        "view_mode": "외부 퍼포먼스",
        "meeting_mode": True,
        "debug_raw": "",
        "selected_date": date.today(),
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

ss_init()

# =========================
# UI Header
# =========================
st.markdown("## 🧠 정세담 | 퍼포먼스 + 기록(달력) 시스템")
st.caption("내부 전용 / 기록 기반 / 외부에서도 URL로 바로 꺼내 쓰는 구조")

top1, top2, top3, top4 = st.columns([1.15, 1.2, 1.2, 1.45])

with top1:
    st.session_state.view_mode = st.radio(
        "뷰 모드",
        ["외부 퍼포먼스", "내부 심화"],
        horizontal=True
    )

with top2:
    st.session_state.meeting_mode = st.toggle(
        "⚡ 미팅 즉시 대응 모드",
        value=st.session_state.meeting_mode,
        help="ON: 단정/결정유도형 문장 강화. OFF: 근거/리스크/대안 강화."
    )

with top3:
    if st.button("🔒 현재 미팅 잠금/해제", use_container_width=True):
        if st.session_state.current_meeting_id is None:
            st.warning("먼저 미팅을 생성하거나 불러와야 잠금이 됩니다.")
        else:
            st.session_state.current_locked = not st.session_state.current_locked
            db_update_lock(st.session_state.current_meeting_id, 1 if st.session_state.current_locked else 0)
            st.success("잠금 상태가 변경되었습니다.")

with top4:
    if st.button("🧹 화면 초기화(새 작업)", use_container_width=True):
        st.session_state.current_meeting_id = None
        st.session_state.current_result = None
        st.session_state.current_payload = None
        st.session_state.current_locked = False
        st.session_state.debug_raw = ""

if st.session_state.current_locked:
    st.success("🔒 현재 불러온 미팅은 잠금 상태입니다. (필요할 때만 해제)")

st.divider()

# =========================
# Calendar / Daily meetings
# =========================
st.markdown("### 📅 오늘/선택일 미팅 스케줄 & 자료 불러오기")

cal1, cal2, cal3 = st.columns([1.0, 1.0, 2.0])

with cal1:
    st.session_state.selected_date = st.date_input("날짜 선택", value=st.session_state.selected_date)

with cal2:
    kw = st.text_input("검색(제목/내용)", placeholder="예: 대기질, 드론, ESG, ○○시", key="search_kw")

with cal3:
    if kw.strip():
        rows = db_search(kw.strip(), limit=30)
        st.caption(f"검색 결과 {len(rows)}건")
        for (mid, mdate, mtime, mtitle, locked, created_at) in rows:
            cols = st.columns([3.5, 1.2, 1.2, 1.0])
            cols[0].write(f"📌 [{mdate} {mtime}] {mtitle}")
            cols[1].write("🔒" if locked else "🔓")
            cols[2].write(created_at)
            if cols[3].button("불러오기", key=f"load_search_{mid}"):
                item = db_load(mid)
                st.session_state.current_meeting_id = item["id"]
                st.session_state.current_payload = item["payload"]
                st.session_state.current_result = item["result"]
                st.session_state.current_locked = item["locked"]
                st.success("✅ 미팅 자료를 불러왔습니다.")
    else:
        sel = st.session_state.selected_date.strftime("%Y-%m-%d")
        rows = db_list_by_date(sel)
        st.caption(f"{sel} 미팅 {len(rows)}건")
        if len(rows) == 0:
            st.info("이 날짜에는 저장된 미팅이 없습니다.")
        else:
            for (mid, mtime, mtitle, locked, created_at) in rows:
                cols = st.columns([3.5, 1.1, 1.1, 1.0])
                cols[0].write(f"🗓️ [{mtime}] {mtitle}")
                cols[1].write("🔒" if locked else "🔓")
                cols[2].write(created_at)
                if cols[3].button("불러오기", key=f"load_day_{mid}"):
                    item = db_load(mid)
                    st.session_state.current_meeting_id = item["id"]
                    st.session_state.current_payload = item["payload"]
                    st.session_state.current_result = item["result"]
                    st.session_state.current_locked = item["locked"]
                    st.success("✅ 미팅 자료를 불러왔습니다.")

st.divider()

# =========================
# Input (Meeting title 직접 입력)
# =========================
st.markdown("### 1️⃣ 입력 (미팅 제목 직접 입력)")

in1, in2 = st.columns([1.1, 1.0])

with in1:
    meeting_title = st.text_input("미팅 제목(직접 입력)", placeholder="예: 2026-01-22 ○○시 대기질 정책 미팅")
    meeting_date = st.date_input("미팅 날짜", value=date.today(), key="meeting_date_input")
    from datetime import datetime
import streamlit as st

# =========================
# 미팅 시간 입력 (현재 시간 기준, 고정)
# =========================
if "meeting_time" not in st.session_state:
    st.session_state.meeting_time = datetime.now().time()

meeting_time = st.time_input(
    "미팅 시간(HH:MM)",
    value=st.session_state.meeting_time,
    key="meeting_time"
)

preset = st.selectbox(
        "프리셋",
        ["선택 안 함", "환경(대기/미세먼지)", "안전(교통/사고)", "ESG(순환/폐기물)", "교육(학교/청소년)", "복지(취약계층)", "도시(청소/질서)", "산업(기업/규제)"],
        index=0
    )

package = st.radio("패키지", ["A 마케팅", "B 정책 설명", "C 풀 패키지"], horizontal=True)
target = st.selectbox("대상", ["시민", "지자체 공무원", "기관/공공", "기업", "의회/의원"])
tone = st.selectbox("톤", ["공공·신뢰형", "간결·속도형", "설득·결정유도형", "전문·근거형"])
video_len = st.selectbox("🎬 영상 길이", ["10초", "20초", "30초"], index=1)

    # 길이(심도) 선택: 사용자 요구 반영
depth = st.selectbox("출력 심도(추천: 깊게)", ["보통", "깊게", "매우 깊게"], index=1)

with in2:
    policy_title = st.text_input("정책/질문 제목", placeholder="예: 도시 대기질 실시간 관리 정책")
    question = st.text_area("질문/요구사항(길게 써도 OK)", height=180, placeholder="미팅에서 나온 요구사항/제약/예산/기간/현장 이슈를 그대로 붙여넣기")
    keywords = st.text_input("강조 키워드(쉼표)", placeholder="예: 시민수용성, 데이터기반, 안전, 실행가능, 신뢰")
    constraints = st.text_area("제약/조건(선택)", height=90, placeholder="예: 예산 최소, 3개월 시범, 기존 데이터 활용, 과장 금지, 한국 지자체 현실")

model_name = st.selectbox("모델", ["gpt-4o-2024-08-06", "gpt-4o-mini"], index=0)

# =========================
# Prompt (심도 확장: 요약+심화 동시 생성)
# =========================
def build_prompt(payload: dict) -> str:
    meeting_style = "단정적·결정유도형(회의에서 바로 읽는 문장)" if payload["meeting_mode"] else "근거·리스크·대안 포함(논리형)"

    # depth별 길이 가이드
    if payload["depth"] == "보통":
        video_cuts = {"10초":"4~5", "20초":"6~8", "30초":"8~10"}[payload["video_len"]]
        detail_lines_img = "7~9줄"
        talktrack_n = "4~6"
        explainer_n = "3~5"
        marketing_long_chars = "450~650자"
        policy_long_chars = "650~900자"
    elif payload["depth"] == "깊게":
        video_cuts = {"10초":"5~6", "20초":"8~10", "30초":"10~12"}[payload["video_len"]]
        detail_lines_img = "9~12줄"
        talktrack_n = "6~8"
        explainer_n = "5~7"
        marketing_long_chars = "650~900자"
        policy_long_chars = "900~1200자"
    else:  # 매우 깊게
        video_cuts = {"10초":"6~7", "20초":"10~12", "30초":"12~14"}[payload["video_len"]]
        detail_lines_img = "12~15줄"
        talktrack_n = "8~10"
        explainer_n = "7~9"
        marketing_long_chars = "900~1200자"
        policy_long_chars = "1200~1600자"

    return f"""
너는 '정세담'의 정책·마케팅 퍼포먼스 생성 AI다.
목표: 고객 미팅 자리에서 "와… 준비 진짜 잘했네"라는 반응이 나올 만큼, 설득 가능한 고퀄리티 결과를 만든다.

[절대 규칙]
- 출력은 반드시 JSON만. 설명/마크다운/코드블록/주석 금지.
- 무관한 통계/지표(예: 청년실업률 등) 절대 금지.
- 숫자를 단정해서 지어내지 말고: '측정 설계' + '예시 범위(추이/비율/구간)' 형태로 제시.
- 한국(대한민국) 맥락, 지자체/공공 현실, 민원/예산/기간/수용성 고려.
- 과장 금지. 대신 실행 가능한 설계와 논리로 신뢰를 만든다.

[입력]
프리셋: {payload["preset"]}
미팅 스타일: {meeting_style}
패키지: {payload["package"]} / 대상: {payload["target"]} / 톤: {payload["tone"]}
영상 길이: {payload["video_len"]} (컷 수 가이드: {video_cuts} 컷)
정책/질문 제목: {payload["policy_title"]}
질문 내용: {payload["question"]}
강조 키워드: {payload["keywords"]}
제약/조건: {payload["constraints"]}

[출력 JSON 스키마]
{{
  "meeting_summary": {{
    "one_liner": "미팅에서 바로 읽는 1문장(짧고 강함)",
    "decision": "지금 당장 권고/결론 1문장(결정 유도)",
    "talk_track": ["설명 포인트 {talktrack_n}개(각 1문장, 말로 읽기 좋게)"],
    "objection_handling": ["예상 반박/우려 4~6개 + 짧은 대응 논리(각 1문장)"]
  }},

  "performance": {{
    "positioning": "이 제안이 왜 '정세담답게' 강한지 4~7문장(속도/체계/리스크 관리/실행 중심)",
    "key_messages": ["상대가 기억해야 할 핵심 메시지 5~8개(짧게)"],
    "next_question_list": ["미팅에서 다음으로 물어볼 질문 6~10개(요구 파악/결정 유도)"]
  }},

  "video_plan": {{
    "duration": "{payload["video_len"]}",
    "creative_brief": {{
      "intent": "영상의 목적/감정/설득 포인트 5~8문장",
      "story_arc": ["도입-문제-전환-해결-결론 구조(각 1~2문장)"],
      "style": {{
        "visual": "현장감/다큐/뉴스/시네마틱 등 구체",
        "audio": "BGM/현장음/내레이션 톤(남/여, 속도, 감정)",
        "text_rules": "자막 규칙(한국어, 짧게, 과장 금지, 어떤 단어는 쓰지 말 것)"
      }}
    }},
    "timeline": [
      {{
        "t": "0-3s",
        "scene": "무엇을 보여주는지(구체적)",
        "why_this_scene": "왜 이 장면이 설득에 필요한지(1문장)",
        "camera": "구도/움직임/렌즈감/리듬",
        "on_screen_text": "한국어 짧은 자막",
        "voiceover": "내레이션 1~2문장(설득형)",
        "sfx": "현장음/효과음"
      }}
    ],
    "meeting_explainer": ["미팅에서 영상 기획을 설명하는 문장 {explainer_n}개(바로 읽기 좋게)"],
    "cta": "마지막 행동 유도/결론 자막 1문장(강함)"
  }},

  "image_prompts": {{
    "A": "상세 프롬프트({detail_lines_img} 이상). 한국 배경, 촬영/조명/구도/질감/인물/시간대/현장감/금지요소 포함. 마지막에 '이 이미지가 전달해야 할 메시지' 1줄 포함.",
    "B": "상세 프롬프트({detail_lines_img} 이상). A와 완전히 다른 각도/상황/장면. 마지막에 '이 이미지가 전달해야 할 메시지' 1줄 포함."
  }},

  "marketing": {{
    "slogan_30": "핵심 문구(30자 이내, 기억되는 문장)",
    "core_200": "핵심 내용(200자 이내, 설득력 높게)",
    "long_direction": "마케팅 방향성 심화({marketing_long_chars}). 타겟별(시민/기관/의사결정자) 메시지, 채널(보도자료/브리핑/현장캠페인/온라인), 톤&매너, 위험 표현 금지까지 포함.",
    "cta_variations": ["콜투액션 문구 8~12개(짧게, 다양한 톤)"]
  }},

  "policy": {{
    "summary_300": "정책 요약 300자 이내(실행/효과/리스크·보완 1줄씩 포함)",
    "deep_plan": "정책 내용 심화({policy_long_chars}). ①문제정의 ②목표 ③핵심전략(3~5개) ④실행단계(준비-시범-확대) ⑤예산/인력은 '범주'로 ⑥리스크&완화 ⑦법/행정 고려(가능한 범위)까지.",
    "implementation_steps": ["실행 단계 체크리스트 10~16개(현장형)"],
    "risk_register": ["리스크 8~12개: 원인-영향-완화(한 줄씩)"]
  }},

  "ppt_outline": {{
    "slides": [
      {{
        "title": "슬라이드 제목",
        "bullets": ["핵심 bullet 4~6개(짧고 강하게)"],
        "visual_hint": "그래프/지도/아이콘/현장 사진 등 힌트 1줄",
        "speaker_note": "발표자가 말할 멘트 2~3문장(설득형)"
      }}
    ]
  }},

  "stats_data": {{
    "what_to_measure": [
      {{
        "metric": "측정 항목(정책과 직접 연결)",
        "why": "왜 이게 중요한지(1문장)",
        "how": "어떻게 측정할지(센서/민원/행정데이터 등)",
        "frequency": "주기(일/주/월 등)"
      }}
    ],
    "example_ranges": ["예시 범위/형식(단정X, 추이/비율/구간) 6~10개"],
    "data_sources_hint": ["가능한 데이터 출처 힌트 4~8개(한국 공공데이터/기관/센서/민원 등)"],
    "interpretation_notes": ["지표 해석 시 주의 4~7개(오해 방지, 신뢰 강화)"]
  }},

  "kpi": {{
    "outcome_kpi": [
      {{
        "kpi": "성과 KPI(결과지표)",
        "meaning": "이 KPI가 좋아지면 무엇이 달라지는지(1문장)",
        "measurement": "측정 방법(1문장)",
        "target_style": "목표값은 범위/단계(초기/안정화)로 제시"
      }}
    ],
    "process_kpi": [
      {{
        "kpi": "운영 KPI(과정지표)",
        "meaning": "운영이 잘 굴러간다는 신호(1문장)",
        "measurement": "측정 방법(1문장)"
      }}
    ],
    "scorecard": ["성과지표를 1페이지로 요약하는 스코어카드 항목 8~12개(짧게)"]
  }}
}}

[필수 생성 규칙]
- video_plan.timeline: 영상 길이에 맞게 충분히 촘촘히 작성.
- image_prompts: 절대 짧게 쓰지 말고 반드시 상세하게.
- marketing.long_direction / policy.deep_plan: '감탄 나올 만큼' 논리적이고 실행 가능한 내용으로.
- 통계/지표는 주제 정확히 종속.
- JSON만 출력.
"""

# =========================
# Generate
# =========================
gen1, gen2, gen3 = st.columns([1.2, 1.2, 2.0])

with gen1:
    do_generate = st.button("🚀 생성 & 저장", use_container_width=True)

with gen2:
    do_regen = st.button("🔁 재생성(같은 입력)", use_container_width=True)

with gen3:
    st.caption("팁: 미팅 제목/정책 제목/질문 내용을 ‘현장 말 그대로’ 길게 넣을수록 결과가 좋아집니다.")

def can_generate():
    if not meeting_title.strip():
        st.error("미팅 제목을 입력해줘. (2번 선택 반영)")
        return False
    if not policy_title.strip():
        st.error("정책/질문 제목을 입력해줘.")
        return False
    if not question.strip():
        st.error("질문/요구사항을 입력해줘.")
        return False
    return True

if do_generate or do_regen:
    if not can_generate():
        st.stop()

    # 잠금이면 생성 금지(불러온 미팅일 때)
    if st.session_state.current_locked and st.session_state.current_meeting_id is not None:
        st.warning("🔒 현재 불러온 미팅이 잠금 상태라 생성/수정이 막혀 있습니다. 잠금 해제 후 진행하세요.")
        st.stop()

    payload = {
        "meeting_title": meeting_title.strip(),
        "meeting_date": meeting_date.strftime("%Y-%m-%d"),
        "meeting_time": meeting_time.strftime("%H:%M") if meeting_time else "00:00",
        "preset": preset,
        "package": package,
        "target": target,
        "tone": tone,
        "video_len": video_len,
        "depth": depth,
        "policy_title": policy_title.strip(),
        "question": question.strip(),
        "keywords": keywords.strip(),
        "constraints": constraints.strip(),
        "meeting_mode": st.session_state.meeting_mode,
        "view_mode": st.session_state.view_mode,
    }

    prompt = build_prompt(payload)

    with st.spinner("고퀄리티 퍼포먼스 생성 중..."):
        data, raw = call_ai_json(prompt=prompt, model=model_name, max_tokens=3200)
        st.session_state.debug_raw = raw

    if data is None:
        st.error("JSON 파싱 실패(모델이 형식을 어김). 아래 원문 확인 후 다시 눌러줘.")
    else:
        # 새 미팅으로 저장(생성/재생성 모두 새 기록 쌓는 구조)
        new_id = db_insert_meeting(
            meeting_date=payload["meeting_date"],
            meeting_time=payload["meeting_time"],
            meeting_title=payload["meeting_title"],
            payload=payload,
            result=data,
            locked=0
        )
        st.session_state.current_meeting_id = new_id
        st.session_state.current_payload = payload
        st.session_state.current_result = data
        st.session_state.current_locked = False
        st.success(f"✅ 생성 완료 & 저장됨 (미팅 ID: {new_id})")

st.divider()

# =========================
# Output
# =========================
r = st.session_state.current_result

if not isinstance(r, dict):
    st.stop()

st.markdown("## 2️⃣ 퍼포먼스 결과")
# === 영상 프롬프트 (복사용 원본) ===
영상_프롬프트 = """
Ultra-realistic documentary style, South Korea context.
Natural lighting, handheld camera feel.
One continuous generation if possible.
No English text on screen.

[프로젝트]
- 영상 길이: 20초
- 목적: 정책 설명 및 시민 이해도 향상

[스토리]
- 문제 제기
- 해결 방안 제시
- 정책 도입 효과
"""
copy_button(영상_프롬프트, "🎬 영상 프롬프트 복사")
quick_ai_links()
# =========================
# 📱 모바일 대응 결과 액션 UI
# =========================

tabs = st.tabs(["🧾 요약", "🎬 영상", "🖼 이미지", "📊 PPT"])

# -------------------------
# 1️⃣ 요약 탭
# -------------------------
with tabs[0]:
    st.markdown("### 미팅 요약 (외부 설명용)")
    summary_text = ""

    if isinstance(r, dict):
        ms = r.get("meeting_summary", {})
        summary_text = (
            f"한 줄 요약:\n{ms.get('one_liner','')}\n\n"
            f"결론:\n{ms.get('decision','')}\n\n"
            f"설명 포인트:\n" + "\n".join(ms.get("talk_track", []))
        )

    st.text_area("요약 내용", value=summary_text, height=220)
    st.code(summary_text, language="text")

# -------------------------
# 2️⃣ 영상 탭
# -------------------------
with tabs[1]:
    st.markdown("### 🎬 영상 프롬프트 (즉시 투입용)")

    vp = r.get("video_plan", {}) if isinstance(r, dict) else {}
    video_prompt = ""

    if vp:
        video_prompt = (
            f"영상 길이: {vp.get('duration','')}\n\n"
            f"의도:\n{vp.get('creative_brief',{}).get('intent','')}\n\n"
            f"타임라인:\n"
        )
        for t in vp.get("timeline", []):
            video_prompt += (
                f"- {t.get('t','')} | {t.get('scene','')} | {t.get('voiceover','')}\n"
            )

    st.text_area("영상 프롬프트", value=video_prompt, height=260)

    col1, col2, col3 = st.columns(3)
    col1.link_button("🚀 Sora 바로가기", "https://sora.openai.com")
    col2.link_button("🎞 Runway 바로가기", "https://runwayml.com")
    col3.link_button("🎥 Pika 바로가기", "https://pika.art")

    st.code(video_prompt, language="text")

# -------------------------
# 3️⃣ 이미지 탭
# -------------------------
with tabs[2]:
    st.markdown("### 🖼 이미지 프롬프트")

    ip = r.get("image_prompts", {}) if isinstance(r, dict) else {}
    img_a = ip.get("A", "")
    img_b = ip.get("B", "")

    st.text_area("이미지 A", value=img_a, height=200)
    st.code(img_a, language="text")

    st.text_area("이미지 B", value=img_b, height=200)
    st.code(img_b, language="text")

# -------------------------
# 4️⃣ PPT 탭
# -------------------------
with tabs[3]:
    st.markdown("### 📊 PPT 구성")

    ppt = r.get("ppt_outline", {}) if isinstance(r, dict) else {}
    slides = ppt.get("slides", [])

    ppt_text = ""
    for i, s in enumerate(slides, start=1):
        ppt_text += f"{i}. {s.get('title','')}\n"
        for b in s.get("bullets", []):
            ppt_text += f"   - {b}\n"
        ppt_text += "\n"

    st.text_area("PPT 구조", value=ppt_text, height=320)
    st.code(ppt_text, language="text")
render_video_ai(r)
render_download_buttons(r)



# 🖼 이미지 자동 생성
render_image_ai(r)

# ⚡ 외부 설득용 요약
if st.session_state.view_mode == "외부 퍼포먼스":
    st.markdown("### ⚡ 미팅 요약(외부 설득용)")

    ms = r.get("meeting_summary", {})

    st.write(f"**한 줄 요약:** {ms.get('one_liner','')}")
    st.write(f"**결론/권고:** {ms.get('decision','')}")

    talk = ms.get("talk_track", []) or []
    if talk:
        st.write("**설명 포인트**")
        for x in talk:
            st.write("•", x)

        oh = ms.get("objection_handling", []) or []
        if oh:
            st.write("**예상 반박/우려 대응**")
            for x in oh:
                st.write("•", x)

    # 2열 구성(어제 스타일 유지 + 더 길게/깊게)
left, right = st.columns([1.05, 1.0])

with left:
        st.markdown("### 🎯 퍼포먼스(설득 프레임)")
        perf = r.get("performance", {})
        st.text_area("포지셔닝(왜 정세담이 강한가)", value=perf.get("positioning", ""), height=150)
        km = perf.get("key_messages", []) or []
        nq = perf.get("next_question_list", []) or []
        st.text_area("핵심 메시지(기억 포인트)", value="\n".join([f"- {x}" for x in km]), height=160)
        st.text_area("다음 질문 리스트(결정 유도)", value="\n".join([f"- {x}" for x in nq]), height=170)

        st.markdown("### 🎬 영상 기획(심화)")
        vp = r.get("video_plan", {})
        cb = (vp.get("creative_brief", {}) or {})
        style = (cb.get("style", {}) or {})
        story_arc = cb.get("story_arc", []) or []

        st.text_area(
            "영상 크리에이티브 브리프",
            value=(
                f"[의도/설득 포인트]\n{cb.get('intent','')}\n\n"
                f"[스토리 아크]\n" + "\n".join([f"- {x}" for x in story_arc]) + "\n\n"
                f"[비주얼]\n{style.get('visual','')}\n"
                f"[오디오]\n{style.get('audio','')}\n"
                f"[자막 규칙]\n{style.get('text_rules','')}\n\n"
                f"[CTA]\n{vp.get('cta','')}"
            ).strip(),
            height=260
        )

        tl = vp.get("timeline", []) or []
        tl_txt = ""
        for s in tl:
            tl_txt += (
                f"- {s.get('t','')}\n"
                f"  장면: {s.get('scene','')}\n"
                f"  이유: {s.get('why_this_scene','')}\n"
                f"  카메라: {s.get('camera','')}\n"
                f"  자막: {s.get('on_screen_text','')}\n"
                f"  내레이션: {s.get('voiceover','')}\n"
                f"  효과음: {s.get('sfx','')}\n\n"
            )
        st.text_area("타임라인(컷 구성)", value=tl_txt.strip(), height=340)

        me = vp.get("meeting_explainer", []) or []
        st.text_area("미팅용 해설(바로 읽기)", value="\n".join([f"- {x}" for x in me]), height=140)

        st.markdown("### 🖼 이미지 프롬프트(2종 · 고퀄)")
        ip = r.get("image_prompts", {}) or {}
        st.text_area("이미지 A", value=ip.get("A",""), height=260)
        st.text_area("이미지 B", value=ip.get("B",""), height=260)

        st.markdown("### 📊 PPT 구성(10장 내외 · 스피커 노트 포함)")
        po = (r.get("ppt_outline", {}) or {}).get("slides", []) or []
        ppt_txt = ""
        for i, sl in enumerate(po, start=1):
            ppt_txt += f"{i}. {sl.get('title','')}\n"
            for b in (sl.get("bullets", []) or [])[:8]:
                ppt_txt += f"   - {b}\n"
            ppt_txt += f"   (비주얼) {sl.get('visual_hint','')}\n"
            ppt_txt += f"   (발표 멘트) {sl.get('speaker_note','')}\n\n"
        st.text_area("PPT 구성", value=ppt_txt.strip(), height=420)

with right:
        st.markdown("### 📣 마케팅(요약 + 심화)")
        mk = r.get("marketing", {}) or {}
        st.text_area("핵심 문구(30자)", value=mk.get("slogan_30",""), height=70)
        st.text_area("핵심 내용(200자)", value=mk.get("core_200",""), height=120)
        st.text_area("심화 방향성(감탄 나오는 버전)", value=mk.get("long_direction",""), height=300)
        ctas = mk.get("cta_variations", []) or []
        st.text_area("CTA 문구(다양한 버전)", value="\n".join([f"- {x}" for x in ctas]), height=160)

        st.markdown("### 📄 정책(요약 + 심화)")
        pol = r.get("policy", {}) or {}
        st.text_area("정책 요약(300자)", value=pol.get("summary_300",""), height=160)
        st.text_area("정책 심화(설득용/실행용)", value=pol.get("deep_plan",""), height=360)

        steps = pol.get("implementation_steps", []) or []
        risks = pol.get("risk_register", []) or []
        st.text_area("실행 체크리스트", value="\n".join([f"- {x}" for x in steps]), height=220)
        st.text_area("리스크 레지스터(원인-영향-완화)", value="\n".join([f"- {x}" for x in risks]), height=240)

        st.markdown("### 📊 통계 데이터(측정 설계 중심)")
        sd = r.get("stats_data", {}) or {}
        wt = sd.get("what_to_measure", []) or []
        wt_txt = ""
        for x in wt:
            wt_txt += (
                f"- {x.get('metric','')}\n"
                f"  · 왜: {x.get('why','')}\n"
                f"  · 측정: {x.get('how','')}\n"
                f"  · 주기: {x.get('frequency','')}\n\n"
            )
        st.text_area("무엇을 어떻게 측정할까", value=wt_txt.strip(), height=320)

        er = sd.get("example_ranges", []) or []
        ds = sd.get("data_sources_hint", []) or []
        notes = sd.get("interpretation_notes", []) or []
        st.text_area("예시 범위/형식(단정X)", value="\n".join([f"- {x}" for x in er]), height=170)
        st.text_area("데이터 출처 힌트", value="\n".join([f"- {x}" for x in ds]), height=170)
        st.text_area("해석 주의(신뢰 강화)", value="\n".join([f"- {x}" for x in notes]), height=170)

        st.markdown("### 📈 성과 지표(KPI · 의미/측정/목표스타일 포함)")
        kpi = r.get("kpi", {}) or {}
        ok = kpi.get("outcome_kpi", []) or []
        pk = kpi.get("process_kpi", []) or []
        ok_txt = ""
        for x in ok:
            ok_txt += (
                f"- {x.get('kpi','')}\n"
                f"  · 의미: {x.get('meaning','')}\n"
                f"  · 측정: {x.get('measurement','')}\n"
                f"  · 목표: {x.get('target_style','')}\n\n"
            )
        pk_txt = ""
        for x in pk:
            pk_txt += (
                f"- {x.get('kpi','')}\n"
                f"  · 의미: {x.get('meaning','')}\n"
                f"  · 측정: {x.get('measurement','')}\n\n"
            )
        st.text_area("성과 KPI(결과지표)", value=ok_txt.strip(), height=320)
        st.text_area("운영 KPI(과정지표)", value=pk_txt.strip(), height=260)

        sc = kpi.get("scorecard", []) or []
        st.text_area("1페이지 스코어카드", value="\n".join([f"- {x}" for x in sc]), height=220)

        with st.expander("원문(JSON/디버그)", expanded=False):
            st.code(st.session_state.debug_raw or "", language="json")















