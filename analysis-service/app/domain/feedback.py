from __future__ import annotations

from app.domain.entities import FeedbackItemInput, MetricScoreInput

_TEMPLATES: dict[str, dict[str, tuple[str, str]]] = {
    "SPEED": {
        "improvement": ("말 속도 조절", "평소보다 다소 느리거나 빠르게 말한 편이에요. 분당 300~450음절 구간을 목표로 조절해보세요."),
        "strength": ("말 속도", "적정 속도로 안정적으로 발표했어요."),
    },
    "FILLER": {
        "improvement": ("필러 단어 줄이기", '"어", "음" 같은 필러 단어가 자주 등장했어요. 문장 사이에 짧게 멈추는 연습이 도움이 됩니다.'),
        "strength": ("깔끔한 발화", "필러 단어 없이 깔끔하게 말했어요."),
    },
    "PRONUNCIATION": {
        "improvement": ("발음 명료도", "일부 구간에서 발음이 명확하게 전달되지 않았어요. 문장 끝까지 또박또박 말해보세요."),
        "strength": ("발음 명료도", "발음이 명확해서 알아듣기 쉬웠어요."),
    },
    "STRUCTURE": {
        "improvement": ("발표 구조 보완", "서론-본론-결론 구분이 뚜렷하지 않아요. 시작과 마무리 문장을 명확히 해보세요."),
        "strength": ("발표 구조", "서론-본론-결론 구조가 잘 드러났어요. 이 구조를 계속 유지하세요."),
    },
    "DELIVERY": {
        "improvement": ("전달력 보완", "발화 구간 길이가 고르지 않아요. 문장 길이를 비슷하게 맞춰보면 더 안정적으로 들립니다."),
        "strength": ("전달력", "안정적인 리듬으로 말했어요."),
    },
    "FLUENCY": {
        "improvement": ("유창성 보완", "침묵 구간이나 긴 휴지가 잦았어요. 다음 문장을 미리 떠올리며 끊김 없이 이어가 보세요."),
        "strength": ("유창성", "끊김 없이 자연스럽게 이어서 말했어요."),
    },
}

_COMMENT_HINTS = {
    "SPEED": " 말 속도만 조절하면 훨씬 편안하게 들릴 거예요.",
    "FILLER": " 필러 단어만 줄여도 전달력이 크게 좋아질 거예요.",
    "PRONUNCIATION": " 문장을 또박또박 마무리하면 더 명확하게 들릴 거예요.",
    "STRUCTURE": " 발표 구조를 조금만 다듬으면 완성도가 높아질 거예요.",
    "DELIVERY": " 발화 리듬을 조금 더 일정하게 가져가 보세요.",
    "FLUENCY": " 문장 사이 끊김만 줄여도 훨씬 유창하게 들릴 거예요.",
}


def _pick(metric_code: str, score: int) -> tuple[str, str, str] | None:
    templates = _TEMPLATES.get(metric_code)
    if not templates:
        return None
    if score < 70 and "improvement" in templates:
        title, description = templates["improvement"]
        return "improvement", title, description
    if score >= 85 and "strength" in templates:
        title, description = templates["strength"]
        return "strength", title, description
    return None


def build_coach_comment(overall_score: int, metrics: list[MetricScoreInput]) -> str:
    if overall_score >= 85:
        base = "전반적으로 안정적인 발표였어요!"
    elif overall_score >= 70:
        base = "무난하게 발표를 마쳤어요."
    else:
        base = "조금 더 연습하면 확실히 나아질 발표예요."

    weakest = min(metrics, key=lambda m: m.score, default=None)
    if weakest is not None and weakest.score < 70:
        base += _COMMENT_HINTS.get(weakest.metric_code, "")

    return base


def build_feedback_items(
    overall_score: int, coach_comment: str, metrics: list[MetricScoreInput]
) -> list[FeedbackItemInput]:
    items: list[FeedbackItemInput] = [
        FeedbackItemInput(
            item_type="summary",
            title="종합 총평",
            description=coach_comment,
            metric_code=None,
            sort_order=0,
        )
    ]

    for order, metric in enumerate(metrics, start=1):
        picked = _pick(metric.metric_code, metric.score)
        if not picked:
            continue
        item_type, title, description = picked
        items.append(
            FeedbackItemInput(
                item_type=item_type,
                title=title,
                description=description,
                metric_code=metric.metric_code,
                evidence={"score": metric.score, "rawValue": metric.raw_value, "unit": metric.unit},
                sort_order=order,
            )
        )
    return items
