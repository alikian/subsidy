import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone

JGRANTS_BASE_URL = os.environ.get("JGRANTS_BASE_URL", "https://api.jgrants-portal.go.jp/exp").rstrip("/")
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
ENABLE_LLM = os.environ.get("ENABLE_LLM", "true").lower() == "true"

SYSTEM_PROMPT = """あなたは日本の補助金申請に詳しいAIアシスタントです。
目的は、JGrants公開APIで候補検索できるだけの情報を会話で集めることです。

必ず守ること:
- 最初から制度を断定せず、足りない情報があれば自然な日本語で1つか2つだけ質問する。
- 必要情報は business_summary, target_area_search, industry, use_purpose, target_number_of_employees, keyword。
- target_area_search は都道府県または全国。
- industry と use_purpose は、提示された選択肢に最も近い正式名称に正規化する。
- 十分に情報が揃ったら ready を true にする。
- 出力はJSONだけ。説明文やMarkdownは出さない。

JSON schema:
{
  "ready": boolean,
  "profile": {
    "business_summary": string,
    "target_area_search": string,
    "industry": string,
    "use_purpose": string,
    "target_number_of_employees": string,
    "keyword": string
  },
  "missing": string[],
  "question": string
}
"""

REQUIRED_PROFILE_FIELDS = [
    "business_summary",
    "target_area_search",
    "industry",
    "use_purpose",
    "target_number_of_employees",
    "keyword",
]

AREA_KEYWORDS = [
    "全国",
    "北海道",
    "青森県",
    "岩手県",
    "宮城県",
    "秋田県",
    "山形県",
    "福島県",
    "茨城県",
    "栃木県",
    "群馬県",
    "埼玉県",
    "千葉県",
    "東京都",
    "神奈川県",
    "新潟県",
    "富山県",
    "石川県",
    "福井県",
    "山梨県",
    "長野県",
    "岐阜県",
    "静岡県",
    "愛知県",
    "三重県",
    "滋賀県",
    "京都府",
    "大阪府",
    "兵庫県",
    "奈良県",
    "和歌山県",
    "鳥取県",
    "島根県",
    "岡山県",
    "広島県",
    "山口県",
    "徳島県",
    "香川県",
    "愛媛県",
    "高知県",
    "福岡県",
    "佐賀県",
    "長崎県",
    "熊本県",
    "大分県",
    "宮崎県",
    "鹿児島県",
    "沖縄県",
]

PURPOSE_HINTS = {
    "IT": "設備整備・IT導入をしたい",
    "DX": "設備整備・IT導入をしたい",
    "システム": "設備整備・IT導入をしたい",
    "設備": "設備整備・IT導入をしたい",
    "省エネ": "エコ・SDGs活動支援がほしい",
    "SDGs": "エコ・SDGs活動支援がほしい",
    "販路": "販路拡大・海外展開をしたい",
    "海外": "販路拡大・海外展開をしたい",
    "研究": "研究開発・実証事業を行いたい",
    "開発": "研究開発・実証事業を行いたい",
    "雇用": "雇用・職場環境を改善したい",
    "人材": "人材育成を行いたい",
    "防災": "安全・防災対策支援がほしい",
}

INDUSTRY_HINTS = {
    "製造": "製造業",
    "建設": "建設業",
    "飲食": "宿泊業、飲食サービス業",
    "宿泊": "宿泊業、飲食サービス業",
    "小売": "卸売業、小売業",
    "卸売": "卸売業、小売業",
    "農業": "農業、林業",
    "漁業": "漁業",
    "医療": "医療、福祉",
    "福祉": "医療、福祉",
    "IT": "情報通信業",
    "情報通信": "情報通信業",
}


def lambda_handler(event, _context):
    if event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        return response(204, {})

    try:
        body = json.loads(event.get("body") or "{}")
        message = str(body.get("message") or "").strip()
        history = normalize_history(body.get("history"))
        if len(message) < 2:
            return response(400, {"message": "相談内容を2文字以上で入力してください。"})

        decision = get_intake_decision(message, history)
        if not decision["ready"]:
            return response(
                200,
                {
                    "answer": decision["question"],
                    "recommendations": [],
                    "intake": {
                        "ready": False,
                        "missing": decision["missing"],
                        "profile": decision["profile"],
                    },
                },
            )

        criteria = criteria_from_profile(decision["profile"])
        subsidies, effective_criteria = search_with_fallback(criteria)
        recommendations = [to_recommendation(item, effective_criteria) for item in subsidies[:5]]
        return response(
            200,
            {
                "answer": build_answer(message, criteria, effective_criteria, recommendations, decision["profile"]),
                "recommendations": recommendations,
                "intake": {
                    "ready": True,
                    "missing": [],
                    "profile": decision["profile"],
                },
            },
        )
    except Exception as exc:
        return response(500, {"message": f"チャット処理に失敗しました: {exc}"})


def normalize_history(history):
    if not isinstance(history, list):
        return []

    normalized = []
    for item in history[-10:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = str(item.get("content") or item.get("text") or "").strip()
        if role in {"user", "assistant"} and content:
            normalized.append({"role": role, "content": content[:1200]})
    return normalized


def get_intake_decision(message, history):
    conversation = conversation_text(message, history)
    heuristic_profile = infer_profile(conversation)
    llm_decision = invoke_intake_llm(message, history)
    if llm_decision:
        profile = merge_profiles(heuristic_profile, clean_profile(llm_decision.get("profile")))
        missing = missing_fields(profile)
        return {
            "ready": len(missing) == 0,
            "profile": profile,
            "missing": missing,
            "question": llm_decision.get("question") or next_question(missing, profile),
        }

    missing = missing_fields(heuristic_profile)
    return {
        "ready": len(missing) == 0,
        "profile": heuristic_profile,
        "missing": missing,
        "question": next_question(missing, heuristic_profile),
    }


def invoke_intake_llm(message, history):
    if not ENABLE_LLM:
        return None

    try:
        import boto3

        user_prompt = {
            "role": "user",
            "content": build_llm_user_prompt(message, history),
        }
        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 700,
            "temperature": 0.2,
            "system": SYSTEM_PROMPT,
            "messages": [user_prompt],
        }
        client = boto3.client("bedrock-runtime")
        result = client.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            body=json.dumps(payload).encode("utf-8"),
            contentType="application/json",
            accept="application/json",
        )
        raw = json.loads(result["body"].read())
        text = "".join(block.get("text", "") for block in raw.get("content", []) if block.get("type") == "text")
        return parse_json_object(text)
    except Exception as exc:
        print(f"LLM intake fallback used: {exc}")
        return None


def build_llm_user_prompt(message, history):
    transcript = "\n".join(
        f"{item['role']}: {item['content']}" for item in [*history, {"role": "user", "content": message}]
    )
    return f"""会話履歴:
{transcript}

use_purpose options:
{json.dumps(list(PURPOSE_HINTS.values()), ensure_ascii=False)}

industry options:
{json.dumps(sorted(set(INDUSTRY_HINTS.values())), ensure_ascii=False)}

target_area_search options:
{json.dumps(AREA_KEYWORDS, ensure_ascii=False)}

この会話から検索に必要な情報を抽出し、不足があれば次の質問を返してください。"""


def parse_json_object(text):
    if not text:
        return None
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def conversation_text(message, history):
    return "\n".join(item["content"] for item in history if item["role"] == "user") + "\n" + message


def infer_profile(text):
    criteria = infer_criteria(text)
    profile = {
        "business_summary": infer_business_summary(text),
        "target_area_search": criteria.get("target_area_search", ""),
        "industry": criteria.get("industry", ""),
        "use_purpose": criteria.get("use_purpose", ""),
        "target_number_of_employees": criteria.get("target_number_of_employees", ""),
        "keyword": criteria.get("keyword", ""),
    }
    return clean_profile(profile)


def clean_profile(profile):
    if not isinstance(profile, dict):
        profile = {}
    cleaned = {}
    for field in REQUIRED_PROFILE_FIELDS:
        value = str(profile.get(field) or "").strip()
        cleaned[field] = "" if value in {"未設定", "不明", "なし", "None", "null"} else value[:255]
    return cleaned


def merge_profiles(primary, secondary):
    merged = clean_profile(primary)
    for key, value in clean_profile(secondary).items():
        if value:
            merged[key] = value
    return merged


def missing_fields(profile):
    missing = [field for field in REQUIRED_PROFILE_FIELDS if not profile.get(field)]
    if profile.get("keyword") in {"補助金", "助成金", "制度"}:
        missing.append("keyword")
    return list(dict.fromkeys(missing))


def next_question(missing, profile):
    if not missing:
        return "必要な情報は揃いました。候補を検索します。"
    if "business_summary" in missing:
        return "まず、どんな事業をしていて、今回どのような取り組みに補助金を使いたいですか？"
    if "target_area_search" in missing:
        return "対象地域はどこですか？都道府県名、または全国で教えてください。"
    if "industry" in missing:
        return "業種を教えてください。例: 製造業、飲食サービス業、情報通信業、小売業など。"
    if "use_purpose" in missing:
        return "補助金の使い道は何ですか？例: IT導入、設備投資、販路拡大、人材育成、省エネなど。"
    if "target_number_of_employees" in missing:
        return "従業員数は何名くらいですか？"
    return f"検索キーワードを1つ教えてください。例: {profile.get('use_purpose') or 'IT導入'}"


def infer_business_summary(text):
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) < 8:
        return ""
    return cleaned[:160]


def criteria_from_profile(profile):
    criteria = {
        "keyword": profile.get("keyword") or pick_keyword(profile.get("business_summary", "")),
        "sort": "acceptance_end_datetime",
        "order": "ASC",
        "acceptance": "1",
    }
    for source, target in [
        ("use_purpose", "use_purpose"),
        ("industry", "industry"),
        ("target_number_of_employees", "target_number_of_employees"),
        ("target_area_search", "target_area_search"),
    ]:
        if profile.get(source):
            criteria[target] = profile[source]
    return criteria


def infer_criteria(message):
    keyword = pick_keyword(message)
    criteria = {
        "keyword": keyword,
        "sort": "acceptance_end_datetime",
        "order": "ASC",
        "acceptance": "1",
    }

    area = next((area for area in AREA_KEYWORDS if area in message), None)
    if area:
        criteria["target_area_search"] = area
    else:
        criteria["target_area_search"] = os.environ.get("DEFAULT_REGION", "全国")

    for hint, purpose in PURPOSE_HINTS.items():
        if hint.lower() in message.lower():
            criteria["use_purpose"] = purpose
            break

    for hint, industry in INDUSTRY_HINTS.items():
        if hint.lower() in message.lower():
            criteria["industry"] = industry
            break

    employee_match = re.search(r"(\d+)\s*(名|人)", message)
    if employee_match:
        employee_count = int(employee_match.group(1))
        if employee_count <= 5:
            criteria["target_number_of_employees"] = "5名以下"
        elif employee_count <= 20:
            criteria["target_number_of_employees"] = "20名以下"
        elif employee_count <= 50:
            criteria["target_number_of_employees"] = "50名以下"
        elif employee_count <= 100:
            criteria["target_number_of_employees"] = "100名以下"
        elif employee_count <= 300:
            criteria["target_number_of_employees"] = "300名以下"
        elif employee_count <= 900:
            criteria["target_number_of_employees"] = "900名以下"
        else:
            criteria["target_number_of_employees"] = "901名以上"

    return criteria


def pick_keyword(message):
    for hint in list(PURPOSE_HINTS.keys()) + list(INDUSTRY_HINTS.keys()):
        if hint.lower() in message.lower() and len(hint) >= 2:
            return hint[:64]

    candidates = re.findall(r"[A-Za-z0-9]{2,}|[\u3040-\u30ff\u3400-\u9fff]{2,}", message)
    ignored = {"補助金", "助成金", "制度", "教えて", "ください", "受付中", "使える", "探して"}
    for candidate in candidates:
        normalized = re.sub(r"(で|に|の|を|は)$", "", candidate)
        if normalized not in ignored and normalized not in AREA_KEYWORDS:
            return normalized[:64]
    return "IT"


def search_jgrants(criteria):
    query = urllib.parse.urlencode(criteria)
    url = f"{JGRANTS_BASE_URL}/v1/public/subsidies?{query}"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=12) as api_response:
        payload = json.loads(api_response.read().decode("utf-8"))
    return payload.get("result") or []


def search_with_fallback(criteria):
    attempts = [
        criteria,
        without(criteria, "industry"),
        without(criteria, "industry", "target_area_search"),
        without(criteria, "industry", "target_area_search", "use_purpose"),
    ]
    seen = set()
    for attempt in attempts:
        key = tuple(sorted(attempt.items()))
        if key in seen:
            continue
        seen.add(key)
        results = search_jgrants(attempt)
        if results:
            return results, attempt
    return [], criteria


def without(criteria, *keys):
    next_criteria = dict(criteria)
    for key in keys:
        next_criteria.pop(key, None)
    return next_criteria


def to_recommendation(item, criteria):
    title = item.get("title") or item.get("name") or "名称未設定"
    reason_parts = []
    if criteria.get("target_area_search"):
        reason_parts.append(f"{criteria['target_area_search']}の条件")
    if criteria.get("use_purpose"):
        reason_parts.append(criteria["use_purpose"])
    if criteria.get("industry"):
        reason_parts.append(criteria["industry"])
    reason = "、".join(reason_parts) + "に近い候補です。" if reason_parts else "相談内容に近い候補です。"
    return {
        "id": item.get("id") or item.get("name") or title,
        "title": title,
        "institution": item.get("institution_name"),
        "deadline": item.get("acceptance_end_datetime"),
        "amount": item.get("subsidy_max_limit"),
        "area": item.get("target_area_search"),
        "reason": reason,
        "url": item.get("front_subsidy_detail_page_url"),
    }


def build_answer(message, requested_criteria, criteria, recommendations, profile=None):
    if not recommendations:
        return (
            "条件に一致する受付中の補助金が見つかりませんでした。地域を「全国」に広げる、"
            "または用途を少し広い言葉にして再度相談してください。"
        )

    criteria_labels = [f"キーワード「{criteria['keyword']}」"]
    for key in ["target_area_search", "use_purpose", "industry", "target_number_of_employees"]:
        if criteria.get(key):
            criteria_labels.append(criteria[key])

    relaxed = sorted(set(requested_criteria.keys()) - set(criteria.keys()))
    relaxed_note = ""
    if relaxed:
        relaxed_note = " 該当件数を出すため、一部の絞り込みを広げています。"

    top = recommendations[0]
    deadline = format_datetime(top.get("deadline"))
    business_note = ""
    if profile and profile.get("business_summary"):
        business_note = " 相談内容をもとに候補を絞りました。"
    return (
        f"{' / '.join(criteria_labels)}で受付中の制度を確認しました。"
        f"まずは「{top['title']}」が近そうです。上限額は{format_amount(top.get('amount'))}、"
        f"締切は{deadline}です。{business_note}{relaxed_note}下の候補から制度名、金額、締切を比べてください。"
    )


def format_amount(value):
    if value in (None, ""):
        return "未設定"
    try:
        return f"{int(value):,}円"
    except (TypeError, ValueError):
        return str(value)


def format_datetime(value):
    if not value:
        return "未設定"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d")
    except ValueError:
        return value


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "content-type",
            "Access-Control-Allow-Methods": "POST,OPTIONS",
            "Content-Type": "application/json; charset=utf-8",
        },
        "body": json.dumps(body, ensure_ascii=False),
    }
