import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone

JGRANTS_BASE_URL = os.environ.get("JGRANTS_BASE_URL", "https://api.jgrants-portal.go.jp/exp").rstrip("/")
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
ENABLE_LLM = os.environ.get("ENABLE_LLM", "true").lower() == "true"

SYSTEM_PROMPT = """あなたは「e-hojokin.ai」の補助金検索アシスタントです。
ユーザーとの会話から JグランツAPI で補助金候補を検索する条件を整理します。
制度名を最初から断定せず 条件が揃ったら ready を true にします。

# 出力ルール
- 出力は常にJSONのみ。Markdown・説明文・コードブロックは絶対に出さない。
- ユーザーに見せる文章は必ず message に入れる。フロントは message だけを表示する。
- 質問は1回につき1個まで。
- すでにユーザーが言った情報は再質問しない。
- 不足情報は必ず次の順番で質問する:
  1. 募集期間
  2. 会社所在地、または補助金を利用したい地域
  3. 会社の従業員数
  4. 補助金の利用目的
  5. 業種・業界
  6. 具体的な制度名

# 短い回答の解釈（重要）
直前に自分がした質問の文脈でユーザーの短い回答を解釈する:
- 従業員数を聞いた直後の「50」「50人」「約50名」「50くらい」→ すべて従業員数50
- 地域を聞いた直後の「東京」→ target_area_search: 東京都
- 使い道を聞いた直後の「エアコン」→ use_purpose: 省エネ
数詞や単位がなくても文脈から確定できる場合は確定させ 同じ質問を繰り返さない。

# 集める情報

1. business_summary — 事業内容の短い要約（内部用 検索には送らない）

2. acceptance_period — 募集期間の希望。募集中・受付中は acceptance: 1、すべて・未定は acceptance: 0

3. target_area_search — 都道府県名または「全国」に正規化
   東京 → 東京都 / 大阪 → 大阪府 / 全国対応 → 全国

4. industry — JグランツAPIの完全一致値のみ使用（読点は全角「，」）:
   農業，林業 / 漁業 / 建設業 / 製造業 / 情報通信業 / 運輸業，郵便業 /
   卸売業，小売業 / 金融業，保険業 / 不動産業，物品賃貸業 /
   宿泊業，飲食サービス業 / 生活関連サービス業，娯楽業 /
   教育，学習支援業 / 医療，福祉 / サービス業（他に分類されないもの）
   例: カフェ・レストラン → 宿泊業，飲食サービス業 / ネットショップ → 卸売業，小売業 /
   工場・部品加工 → 製造業 / IT・システム開発 → 情報通信業 /
   介護 → 医療，福祉 / コンサル・士業 → サービス業（他に分類されないもの）
   確信が持てない場合は "" のまま（絞らない方が安全）

5. use_purpose — 内部用。keyword生成に使う。検索には送らない。
   AI導入・システム・EC → IT導入 / 機械・厨房・製造ライン → 設備投資 /
   HP・広告・展示会・海外展開 → 販路開拓 / 研修・採用 → 人材育成 /
   空調・LED・電気代 → 省エネ / 新商品・試作 → 新規事業 / 改装・内装 → 店舗改装

6. target_number_of_employees — 数値で保持（「50」だけでも受け付ける）
   target_number_of_employees_band — APIに送る帯に変換:
   〜5 → 5名以下 / 6〜20 → 20名以下 / 21〜50 → 50名以下 /
   51〜100 → 100名以下 / 101〜300 → 300名以下 / 不明 → 従業員の制約なし

7. institution_name — 具体的な制度名。知らない・未定の場合は空でよい。

8. keyword — 1〜2語の短い日本語。最重要。
   地域名・業種名・「補助金」という語は入れない（別パラメータと重複し0件になる）
   use_purpose から公募頻出語を選ぶ: 省エネ / IT導入 / 設備投資 / 販路開拓 / 人材育成 / 事業承継
   どうしても作れない場合は「事業」にする（空にしない）

# ready 判定
- 上記6つの質問を順番に確認し終えたら ready を true にする。
- ready が true のとき message は「条件が揃いました。補助金候補を検索します。」
- 補助金と無関係な入力には message で一言だけ話題を戻す。

# 出力JSON形式
{
  "ready": false,
  "message": "",
  "business_summary": "",
  "acceptance_period": "",
  "acceptance": "",
  "target_area_search": "",
  "industry": "",
  "use_purpose": "",
  "target_number_of_employees": null,
  "target_number_of_employees_band": "",
  "institution_name": "",
  "keyword": "",
  "missing_fields": []
}

例1:
ユーザー: 東京都でIT導入に使える補助金を教えて
{
  "ready": true,
  "message": "条件が揃いました。補助金候補を検索します。",
  "business_summary": "",
  "acceptance_period": "募集中",
  "acceptance": "1",
  "target_area_search": "東京都",
  "industry": "",
  "use_purpose": "IT導入",
  "target_number_of_employees": null,
  "target_number_of_employees_band": "従業員の制約なし",
  "institution_name": "",
  "keyword": "IT導入",
  "missing_fields": []
}

例2:
（直前のAI質問: 従業員数を教えてください）
ユーザー: 50
{
  "ready": true,
  "message": "条件が揃いました。補助金候補を検索します。",
  "business_summary": "大阪府でカフェを運営",
  "acceptance_period": "募集中",
  "acceptance": "1",
  "target_area_search": "大阪府",
  "industry": "宿泊業，飲食サービス業",
  "use_purpose": "省エネ",
  "target_number_of_employees": 50,
  "target_number_of_employees_band": "50名以下",
  "institution_name": "",
  "keyword": "省エネ",
  "missing_fields": []
}
"""

REQUIRED_PROFILE_FIELDS = [
    "business_summary",
    "acceptance_period",
    "acceptance",
    "target_area_search",
    "industry",
    "use_purpose",
    "target_number_of_employees",
    "institution_name",
    "keyword",
]
QUESTION_ORDER = [
    "acceptance_period",
    "target_area_search",
    "target_number_of_employees",
    "use_purpose",
    "industry",
    "institution_name",
]
QUESTION_TEXT = {
    "acceptance_period": "お探しの補助金の募集期間はご存じでしょうか？\n例：募集中、来月まで、未定など",
    "target_area_search": "会社所在地、または補助金を利用したい地域を入力してください。\n例：東京都、東北地方、全国など",
    "target_number_of_employees": "会社の従業員数を入力してください。\n例：10名、50名、100名など",
    "use_purpose": "補助金の利用目的を入力してください。\n例：販路拡大、設備投資、人材育成、IT導入など",
    "industry": "貴社の業種・業界を入力してください。\n例：農業、製造業、小売業、ITサービス業など",
    "institution_name": "お探しの具体的な制度名をご存じでしたら入力してください。\n例：IT導入補助金、ものづくり補助金、小規模事業者持続化補助金など",
}

AREA_KEYWORDS = [
    "全国",
    "北海道地方",
    "東北地方",
    "関東・甲信越地方",
    "東海・北陸地方",
    "近畿地方",
    "中国地方",
    "四国地方",
    "九州・沖縄地方",
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
    "海外",
]

PURPOSE_HINTS = {
    "IT導入": "設備整備・IT導入をしたい",
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
    "情報通信": "情報通信業",
    "ITサービス": "情報通信業",
    "IT企業": "情報通信業",
    "システム開発": "情報通信業",
    "ソフトウェア": "情報通信業",
    "アプリ開発": "情報通信業",
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
    asked_fields = asked_question_fields(history)
    heuristic_profile = merge_profiles(infer_profile(conversation), infer_answered_question_profile(message, history))
    llm_decision = invoke_intake_llm(message, history)
    if llm_decision:
        llm_profile = extract_llm_profile(llm_decision)
        profile = sanitize_profile(merge_profiles(heuristic_profile, llm_profile), conversation)
        missing = missing_intake_fields(profile, asked_fields)
        return {
            "ready": len(missing) == 0,
            "profile": profile,
            "missing": missing,
            "question": next_question(missing, profile),
        }

    heuristic_profile = sanitize_profile(heuristic_profile, conversation)
    missing = missing_intake_fields(heuristic_profile, asked_fields)
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
        "acceptance_period": criteria.get("acceptance_period", ""),
        "acceptance": criteria.get("acceptance", ""),
        "target_area_search": criteria.get("target_area_search", ""),
        "industry": criteria.get("industry", ""),
        "use_purpose": criteria.get("use_purpose", ""),
        "target_number_of_employees": criteria.get("target_number_of_employees", ""),
        "institution_name": criteria.get("institution_name", ""),
        "keyword": criteria.get("keyword", ""),
    }
    return clean_profile(profile)


def infer_answered_question_profile(message, history):
    profile = {}
    transcript = [*history, {"role": "user", "content": message}]
    for index, item in enumerate(transcript[:-1]):
        if item.get("role") != "assistant":
            continue
        field = question_field_from_text(item.get("content", ""))
        if not field:
            continue
        answer = next(
            (future.get("content", "") for future in transcript[index + 1 :] if future.get("role") == "user"),
            "",
        )
        profile = merge_profiles(profile, parse_answer_for_field(field, answer))
    return profile


def parse_answer_for_field(field, answer):
    answer = answer.strip()
    if not answer:
        return {}

    if re.search(r"(なし|無い|ない|未定|不明|わからない|分からない|知らない|指定なし)", answer):
        if field == "acceptance_period":
            return {"acceptance_period": answer, "acceptance": "0"}
        return {field: ""}

    if field == "acceptance_period":
        acceptance_period, acceptance = infer_acceptance(answer)
        return {"acceptance_period": acceptance_period or answer, "acceptance": acceptance or "1"}
    if field == "target_area_search":
        return {"target_area_search": infer_area(answer)}
    if field == "target_number_of_employees":
        return {"target_number_of_employees": employee_band(answer)}
    if field == "use_purpose":
        use_purpose = next((purpose for hint, purpose in PURPOSE_HINTS.items() if hint.lower() in answer.lower()), answer)
        return {"use_purpose": use_purpose, "keyword": pick_keyword(answer) or answer}
    if field == "industry":
        industry = next((industry for hint, industry in INDUSTRY_HINTS.items() if hint.lower() in answer.lower()), answer)
        return {"industry": industry}
    if field == "institution_name":
        return {"institution_name": answer}
    return {}


def question_field_from_text(content):
    for field, question in QUESTION_TEXT.items():
        if question.splitlines()[0] in content:
            return field
    return ""


def clean_profile(profile):
    if not isinstance(profile, dict):
        profile = {}
    cleaned = {}
    for field in REQUIRED_PROFILE_FIELDS:
        value = str(profile.get(field) or "").strip()
        cleaned[field] = "" if value in {"未設定", "不明", "なし", "None", "null"} else value[:255]
    return cleaned


def extract_llm_profile(decision):
    if not isinstance(decision, dict):
        return {}

    profile = decision.get("profile") if isinstance(decision.get("profile"), dict) else {}
    merged = dict(profile)
    for field in REQUIRED_PROFILE_FIELDS:
        if decision.get(field) not in (None, ""):
            merged[field] = decision.get(field)
    if decision.get("target_number_of_employees_band"):
        merged["target_number_of_employees"] = decision["target_number_of_employees_band"]
    elif decision.get("target_number_of_employees") not in (None, ""):
        merged["target_number_of_employees"] = employee_band(decision["target_number_of_employees"])
    return merged


def merge_profiles(primary, secondary):
    merged = clean_profile(primary)
    for key, value in clean_profile(secondary).items():
        if value:
            merged[key] = value
    return merged


def sanitize_profile(profile, conversation):
    profile = clean_profile(profile)
    if profile.get("industry") == "情報通信業" and is_it_adoption_request(conversation):
        profile["industry"] = ""
    if profile.get("keyword") == "IT":
        profile["keyword"] = "IT導入"
    return profile


def is_it_adoption_request(text):
    if not re.search(r"(IT導入|DX|システム導入|デジタル化)", text, re.IGNORECASE):
        return False
    explicit_it_industry = re.search(
        r"(情報通信業|ITサービス|IT企業|システム開発|ソフトウェア|アプリ開発|Web制作)",
        text,
        re.IGNORECASE,
    )
    return explicit_it_industry is None


def employee_band(value):
    if isinstance(value, str) and value.endswith("以下"):
        return value
    match = re.search(r"\d+", str(value))
    if not match:
        return ""
    employee_count = int(match.group(0))
    if employee_count <= 5:
        return "5名以下"
    if employee_count <= 20:
        return "20名以下"
    if employee_count <= 50:
        return "50名以下"
    if employee_count <= 100:
        return "100名以下"
    if employee_count <= 300:
        return "300名以下"
    if employee_count <= 900:
        return "900名以下"
    return "901名以上"


def asked_question_fields(history):
    asked = set()
    for item in history:
        if item.get("role") != "assistant":
            continue
        field = question_field_from_text(item.get("content", ""))
        if field:
            asked.add(field)
    return asked


def missing_intake_fields(profile, asked_fields):
    missing = []
    for field in QUESTION_ORDER:
        if field in asked_fields or profile.get(field):
            continue
        missing.append(field)
    return missing


def next_question(missing, profile):
    if not missing:
        return "必要な情報は揃いました。候補を検索します。"
    return QUESTION_TEXT.get(missing[0], "検索条件を入力してください。")


def infer_business_summary(text):
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) < 8:
        return ""
    return cleaned[:160]


def criteria_from_profile(profile):
    criteria = {
        "keyword": profile.get("keyword") or pick_keyword(profile.get("business_summary", "")) or "事業",
        "sort": "acceptance_end_datetime",
        "order": "ASC",
        "acceptance": profile.get("acceptance") or "1",
    }
    for source, target in [
        ("use_purpose", "use_purpose"),
        ("institution_name", "institution_name"),
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
    }

    acceptance_period, acceptance = infer_acceptance(message)
    if acceptance_period:
        criteria["acceptance_period"] = acceptance_period
    if acceptance:
        criteria["acceptance"] = acceptance

    area = infer_area(message)
    if area:
        criteria["target_area_search"] = area

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

    institution_name = infer_institution_name(message)
    if institution_name:
        criteria["institution_name"] = institution_name

    return criteria


def infer_acceptance(message):
    if re.search(r"(募集中|受付中|公募中|今|現在|来月|今月|締切|期限|まで)", message):
        return "募集中", "1"
    if re.search(r"(未定|不明|わからない|分からない|すべて|全て|指定なし)", message):
        return "未定", "0"
    return "", ""


def infer_area(message):
    area_aliases = {
        "東京": "東京都",
        "大阪": "大阪府",
        "京都": "京都府",
        "北海道": "北海道",
        "全国": "全国",
    }
    for alias, area in area_aliases.items():
        if alias in message:
            return area
    return next((area for area in AREA_KEYWORDS if area in message), "")


def infer_institution_name(message):
    match = re.search(r"([^\s、。]*補助金)", message)
    if not match:
        return ""
    name = match.group(1).strip()
    if name in {"補助金", "助成金"}:
        return ""
    return name[:255]


def pick_keyword(message):
    for hint in list(PURPOSE_HINTS.keys()) + list(INDUSTRY_HINTS.keys()):
        if hint.lower() in message.lower() and len(hint) >= 2:
            return hint[:64]

    candidates = re.findall(r"[A-Za-z0-9]{2,}|[\u3040-\u30ff\u3400-\u9fff]{2,}", message)
    ignored = {"補助金", "助成金", "制度", "教えて", "ください", "受付中", "使える", "探して", "探したい"}
    for candidate in candidates:
        normalized = re.sub(r"(で|に|の|を|は)$", "", candidate)
        if (
            normalized not in ignored
            and normalized not in AREA_KEYWORDS
            and not any(token in normalized for token in ["補助金", "助成金", "制度"])
        ):
            return normalized[:64]
    return ""


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
