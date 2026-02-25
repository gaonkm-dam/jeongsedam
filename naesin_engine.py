import datetime
import json
import naesin_database as db

DISCLAIMER = (
    "※ 이 예측은 현재 입력된 데이터를 기반으로 한 참고용 정보이며, 실제 입시 결과와 다를 수 있습니다. "
    "전형별 세부 기준·전형료·일정·가중치 등 변동 요인이 있으므로 반드시 대학 공식 입학처를 확인하세요."
)

OPTION_LABELS = {'A': '보수적(안정권)', 'B': '균형(적정권)', 'C': '공격적(도전권)'}

REGION_LABELS = {
    'seoul': '서울', 'gyeonggi': '경기', 'incheon': '인천',
    'busan': '부산', 'daejeon': '대전', 'gyeongbuk': '경북',
    'jeonnam': '전남', 'chungnam': '충남',
}

DEGREE_LABELS = {'four_year': '4년제', 'two_year': '2년제'}


def _shortfall_naesin(student_avg, cutoff_avg):
    if student_avg is None or cutoff_avg is None:
        return None
    return round(cutoff_avg - student_avg, 2)


def _zone_from_shortfall(sf):
    if sf is None:
        return '알수없음'
    if sf >= 0.3:
        return '안정'
    elif sf >= -0.3:
        return '적정'
    else:
        return '도전'


def _possibility_from_shortfall(sf):
    if sf is None:
        return '알수없음'
    if sf >= 0.5:
        return '높음'
    elif sf >= 0.0:
        return '보통'
    else:
        return '낮음'


def _shortfall_desc(sf, track='naesin'):
    if sf is None:
        return '데이터 없음'
    if track == 'naesin':
        if sf < 0:
            return f'내신 평균 {abs(sf):.1f}등급 부족'
        elif sf == 0:
            return '커트라인과 동일'
        else:
            return f'내신 평균 {sf:.1f}등급 여유'
    else:
        return f'활동점수 {abs(sf):.0f}점 {"부족" if sf < 0 else "여유"}'


def _evidence_naesin(student_avg, cutoff):
    ev = []
    if student_avg is not None:
        ev.append(f'학생 내신 평균 {student_avg:.2f}등급')
    if cutoff:
        ev.append(f'해당 학과 내신 컷 {cutoff:.1f}등급(2024 기준)')
    ev.append('전형 세부 조건은 대학 입학처 확인 필수')
    return ev


def _evidence_holistic(strength, cutoff_score):
    ev = []
    ev.append(f'학생 활동점수 산출값 {strength:.1f}/100')
    if cutoff_score:
        ev.append(f'해당 학과 학종 활동점수 기준 {cutoff_score}점')
    ev.append('교사 검증 완료 활동 수 반영')
    ev.append('전형 세부 조건은 대학 입학처 확인 필수')
    return ev


def _option_filter(sf, option):
    if option == 'A':
        return sf is not None and sf >= 0.3
    elif option == 'B':
        return sf is not None and -0.3 <= sf < 0.3
    elif option == 'C':
        return sf is not None and sf < -0.3
    else:
        return True


def recommend_naesin(student_id, option='B', degree_filter=None, region_filter=None,
                     category_filter=None, limit=10):
    student_avg = db.get_naesin_avg(student_id)
    if student_avg is None:
        return [], '내신 성적 데이터가 없습니다. 내신 성적을 먼저 입력해주세요.'

    departments = db.get_departments(
        university_id=None,
        category=category_filter
    )
    if degree_filter:
        departments = [d for d in departments if d['degree_type'] == degree_filter]
    if region_filter:
        departments = [d for d in departments if d['region_code'] == region_filter]

    results = []
    for dept in departments:
        cutoff_row = db.get_cutoffs(dept['department_id'], 'naesin', 2024)
        if not cutoff_row:
            continue
        cutoff_avg = cutoff_row['cutoff_value'].get('naesin_avg')
        sf = _shortfall_naesin(student_avg, cutoff_avg)

        if not _option_filter(sf, option):
            continue

        zone = _zone_from_shortfall(sf)
        possibility = _possibility_from_shortfall(sf)
        shortfall_desc = _shortfall_desc(sf, 'naesin')
        evidence = _evidence_naesin(student_avg, cutoff_avg)

        results.append({
            'university': dept['university_name'],
            'department': dept['name'],
            'degree_type': DEGREE_LABELS.get(dept['degree_type'], dept['degree_type']),
            'region': REGION_LABELS.get(dept['region_code'], dept['region_code']),
            'category': dept['category'],
            'zone': zone,
            'possibility': possibility,
            'shortfall': shortfall_desc,
            'evidence': evidence,
            'cutoff_naesin': cutoff_avg,
            'homepage_url': dept['homepage_url'],
            'department_url': dept.get('department_url'),
            'track': 'naesin',
        })

    results.sort(key=lambda x: (
        {'안정': 0, '적정': 1, '도전': 2, '알수없음': 3}.get(x['zone'], 3),
        x.get('cutoff_naesin', 9)
    ))

    return results[:limit], None


def recommend_holistic(student_id, option='B', degree_filter=None, region_filter=None,
                       category_filter=None, limit=10):
    strength = db.get_activity_strength(student_id)
    acts = db.get_activities(student_id)
    if not acts:
        return [], '활동 데이터가 없습니다. 학종 활동을 먼저 입력해주세요.'

    reviews = db.get_activity_reviews_for_student(student_id)
    pending_count = sum(1 for r in reviews if r['status'] == 'pending')

    departments = db.get_departments(
        university_id=None,
        category=category_filter
    )
    if degree_filter:
        departments = [d for d in departments if d['degree_type'] == degree_filter]
    if region_filter:
        departments = [d for d in departments if d['region_code'] == region_filter]

    results = []
    for dept in departments:
        cutoff_row = db.get_cutoffs(dept['department_id'], 'holistic', 2024)
        if not cutoff_row:
            continue
        score_min = cutoff_row['cutoff_value'].get('activity_score_min', 50)
        sf = round(score_min - strength, 1)

        if option == 'A' and sf > -10:
            continue
        elif option == 'B' and not (-10 <= sf <= 10):
            continue
        elif option == 'C' and sf <= 10:
            continue

        if sf <= -10:
            zone = '안정'
            possibility = '높음'
        elif -10 < sf <= 10:
            zone = '적정'
            possibility = '보통'
        else:
            zone = '도전'
            possibility = '낮음'

        shortfall_desc = _shortfall_desc(-sf, 'holistic')
        evidence = _evidence_holistic(strength, score_min)

        pending_note = f' (교사 검증 대기 {pending_count}건)' if pending_count > 0 else ''

        results.append({
            'university': dept['university_name'],
            'department': dept['name'],
            'degree_type': DEGREE_LABELS.get(dept['degree_type'], dept['degree_type']),
            'region': REGION_LABELS.get(dept['region_code'], dept['region_code']),
            'category': dept['category'],
            'zone': zone,
            'possibility': possibility,
            'shortfall': shortfall_desc + pending_note,
            'evidence': evidence,
            'activity_strength': strength,
            'score_min': score_min,
            'pending_count': pending_count,
            'homepage_url': dept['homepage_url'],
            'department_url': dept.get('department_url'),
            'track': 'holistic',
        })

    results.sort(key=lambda x: (
        {'안정': 0, '적정': 1, '도전': 2}.get(x['zone'], 3),
        x.get('score_min', 0)
    ), reverse=False)
    results.sort(key=lambda x: x.get('score_min', 0), reverse=True)

    return results[:limit], None


# ─────────────────────────────────────────────────────────
# 변화 계산
# ─────────────────────────────────────────────────────────

def calculate_changes(student_id, days=7):
    today = datetime.date.today()
    half = days // 2 or 1

    logs = db.get_learning_logs(student_id, days)
    states = db.get_state_checks(student_id, days)
    assessments = db.get_self_assessments(student_id, days)

    def avg(lst, key):
        vals = [r[key] for r in lst if r.get(key) is not None]
        return round(sum(vals) / len(vals), 2) if vals else None

    def trend(lst, key, split_days):
        cutoff = (today - datetime.timedelta(days=split_days)).isoformat()
        recent = [r[key] for r in lst if r.get('date', '') >= cutoff and r.get(key) is not None]
        older = [r[key] for r in lst if r.get('date', '') < cutoff and r.get(key) is not None]
        if not recent or not older:
            return None
        r_avg = sum(recent) / len(recent)
        o_avg = sum(older) / len(older)
        return round(r_avg - o_avg, 2)

    study_avg = avg(logs, 'study_minutes')
    study_trend = trend(logs, 'study_minutes', half)

    focus_avg = avg(states, 'focus')
    stress_avg = avg(states, 'stress')
    fatigue_avg = avg(states, 'fatigue')
    motivation_avg = avg(states, 'motivation')
    state_trend = trend(states, 'motivation', half)

    perf_avg = avg(assessments, 'performance_level')
    under_avg = avg(assessments, 'understanding_level')

    return {
        'period_days': days,
        'study_minutes_avg': study_avg,
        'study_minutes_trend': study_trend,
        'focus_avg': focus_avg,
        'stress_avg': stress_avg,
        'fatigue_avg': fatigue_avg,
        'motivation_avg': motivation_avg,
        'motivation_trend': state_trend,
        'performance_avg': perf_avg,
        'understanding_avg': under_avg,
        'log_days': len(logs),
        'state_days': len(states),
    }


def detect_burnout_risk(changes_7d):
    score = 0
    reasons = []
    if changes_7d.get('study_minutes_avg') is not None:
        if changes_7d['study_minutes_avg'] < 60:
            score += 2
            reasons.append('일평균 학습 60분 미만')
    if changes_7d.get('stress_avg') is not None and changes_7d['stress_avg'] >= 4:
        score += 2
        reasons.append('스트레스 평균 4 이상')
    if changes_7d.get('fatigue_avg') is not None and changes_7d['fatigue_avg'] >= 4:
        score += 2
        reasons.append('피로도 평균 4 이상')
    if changes_7d.get('motivation_avg') is not None and changes_7d['motivation_avg'] <= 2:
        score += 2
        reasons.append('의욕 평균 2 이하')
    if changes_7d.get('motivation_trend') is not None and changes_7d['motivation_trend'] < -0.5:
        score += 1
        reasons.append('최근 의욕 하락 추세')
    level = '낮음' if score <= 2 else ('보통' if score <= 4 else '높음')
    return {'score': score, 'level': level, 'reasons': reasons}


# ─────────────────────────────────────────────────────────
# 예측 생성 (단정 금지 형식)
# ─────────────────────────────────────────────────────────

def generate_forecasts(student_id, mode='demo_instant'):
    today = datetime.date.today().isoformat()
    naesin_avg = db.get_naesin_avg(student_id)
    strength = db.get_activity_strength(student_id)
    changes_7 = calculate_changes(student_id, 7)
    changes_30 = calculate_changes(student_id, 30)
    burnout = detect_burnout_risk(changes_7)

    forecasts = []

    # ── naesin_avg d7 ──
    if naesin_avg is not None:
        trend_7 = changes_7.get('study_minutes_trend') or 0
        d7_adj = round(naesin_avg + (-0.05 if trend_7 > 30 else (0.05 if trend_7 < -30 else 0)), 2)
        forecasts.append({
            'metric': 'naesin_avg', 'window': 'd7',
            'value': {
                'current': naesin_avg,
                'estimate': d7_adj,
                'range': [round(d7_adj - 0.2, 2), round(d7_adj + 0.2, 2)],
                'zone': _zone_from_shortfall(0),
                'possibility': '보통',
                'basis': ['최근 7일 학습 시간 추세 반영', '성적 변화는 실제 시험 후 확정'],
                'condition': '이 예측은 최근 학습 패턴 기준이며 실제 시험 결과와 다를 수 있음',
            },
            'confidence': 'low',
            'disclaimer': DISCLAIMER,
        })
        d30_adj = round(naesin_avg + (-0.1 if changes_30.get('study_minutes_avg', 0) > 150 else
                                      (0.1 if changes_30.get('study_minutes_avg', 120) < 60 else 0)), 2)
        forecasts.append({
            'metric': 'naesin_avg', 'window': 'd30',
            'value': {
                'current': naesin_avg,
                'estimate': d30_adj,
                'range': [round(d30_adj - 0.3, 2), round(d30_adj + 0.3, 2)],
                'basis': ['30일 평균 학습시간 추세 반영', '성적 변화는 실제 시험 후 확정'],
                'condition': '30일 기준 참고값. 단정할 수 없음',
            },
            'confidence': 'low',
            'disclaimer': DISCLAIMER,
        })

    # ── activity_strength d7 ──
    forecasts.append({
        'metric': 'activity_strength', 'window': 'd7',
        'value': {
            'current': strength,
            'trend': '유지' if strength > 50 else '활동 추가 필요',
            'basis': ['활동 다양성·전공연계·교사검증 반영'],
            'condition': '활동 추가 및 교사 검증 완료 시 점수 상승 가능',
        },
        'confidence': 'mid',
        'disclaimer': DISCLAIMER,
    })

    # ── burnout_risk ──
    forecasts.append({
        'metric': 'burnout_risk', 'window': 'd7',
        'value': {
            'level': burnout['level'],
            'score': burnout['score'],
            'reasons': burnout['reasons'],
            'advice': '번아웃 위험 신호가 감지됩니다. 짧은 휴식과 수면 관리를 권장합니다.' if burnout['level'] == '높음'
                      else '현재 상태를 유지하면서 꾸준히 진행하세요.',
        },
        'confidence': 'mid',
        'disclaimer': DISCLAIMER,
    })

    # ── admission_readiness AI ──
    readiness = 0
    basis_ai = []
    if naesin_avg is not None:
        r_score = max(0, 100 - (naesin_avg - 1) * 15)
        readiness += r_score * 0.5
        basis_ai.append(f'내신 평균 {naesin_avg}등급 → 교과 준비도 {r_score:.0f}/100')
    if strength > 0:
        readiness += strength * 0.3
        basis_ai.append(f'활동점수 {strength:.1f}/100 → 학종 준비도 기여')
    study_score = min(100, (changes_30.get('study_minutes_avg') or 0) / 180 * 100)
    readiness += study_score * 0.2
    basis_ai.append(f'30일 평균 학습 {changes_30.get("study_minutes_avg") or 0:.0f}분 → 학습 지속성 기여')
    readiness = round(min(readiness, 100), 1)

    forecasts.append({
        'metric': 'admission_readiness', 'window': 'ai',
        'value': {
            'score': readiness,
            'level': '낮음' if readiness < 40 else ('보통' if readiness < 70 else '높음'),
            'basis': basis_ai,
            'missing': _readiness_missing(naesin_avg, strength, changes_30),
            'next_actions': _next_actions(naesin_avg, strength, burnout),
            'condition': '이 점수는 규칙 기반 산출값이며 실제 합격을 보장하지 않습니다.',
        },
        'confidence': 'low',
        'disclaimer': DISCLAIMER,
    })

    for f in forecasts:
        db.save_forecast(student_id, f['metric'], f['window'], f['value'], f['confidence'], f['disclaimer'])

    return forecasts


def _readiness_missing(naesin_avg, strength, changes_30):
    missing = []
    if naesin_avg is None:
        missing.append('내신 성적 입력 필요')
    elif naesin_avg > 3.0:
        missing.append(f'내신 평균 {naesin_avg}등급 → 목표 대학에 따라 향상 필요')
    if strength < 40:
        missing.append('활동 강도 부족 → 동아리·봉사·수상 등 다양한 활동 추가 권장')
    study_avg = changes_30.get('study_minutes_avg') or 0
    if study_avg < 90:
        missing.append(f'30일 평균 학습 {study_avg:.0f}분 → 최소 90분 이상 유지 권장')
    return missing or ['현재 수준 유지 및 꾸준한 기록 지속']


def _next_actions(naesin_avg, strength, burnout):
    actions = []
    if naesin_avg is not None and naesin_avg > 2.5:
        actions.append('약점 과목 집중 복습 (내신 향상)')
    if strength < 50:
        actions.append('교사 검증 요청 또는 활동 1~2개 추가')
    if burnout['level'] in ('보통', '높음'):
        actions.append('수면·운동 등 회복 활동 병행')
    if not actions:
        actions.append('현재 페이스 유지, 매일 기록 지속')
    return actions[:2]


# ─────────────────────────────────────────────────────────
# 추천 + 스냅샷 저장 통합 함수
# ─────────────────────────────────────────────────────────

def get_recommendations_with_snapshot(student_id, track, option='B',
                                       degree_filter=None, region_filter=None,
                                       category_filter=None, limit=10):
    if track == 'naesin':
        results, err = recommend_naesin(student_id, option, degree_filter, region_filter, category_filter, limit)
    else:
        results, err = recommend_holistic(student_id, option, degree_filter, region_filter, category_filter, limit)

    if results:
        filters = {
            'option': option,
            'degree_filter': degree_filter,
            'region_filter': region_filter,
            'category_filter': category_filter,
        }
        db.save_snapshot(student_id, track, results, filters)

    return results, err


# ─────────────────────────────────────────────────────────
# 학급 위험군 분석 (교사용)
# ─────────────────────────────────────────────────────────

def analyze_class_risk(student_ids):
    risk_list = []
    for sid in student_ids:
        changes = calculate_changes(sid, 7)
        burnout = detect_burnout_risk(changes)
        today_check = db.check_today_logs(sid)
        acts = db.get_activities(sid)
        reviews = db.get_activity_reviews_for_student(sid)
        pending = sum(1 for r in reviews if r['status'] == 'pending')

        risk_list.append({
            'student_id': sid,
            'burnout_level': burnout['level'],
            'burnout_score': burnout['score'],
            'burnout_reasons': burnout['reasons'],
            'today_learning_done': today_check['learning'],
            'today_state_done': today_check['state'],
            'activity_count': len(acts),
            'pending_reviews': pending,
            'study_avg_7d': changes.get('study_minutes_avg'),
            'motivation_avg_7d': changes.get('motivation_avg'),
        })
    return risk_list
