import React, { FormEvent, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowDownUp,
  Bot,
  Download,
  ExternalLink,
  FileText,
  Filter,
  Loader2,
  MessageCircle,
  RefreshCw,
  Search,
  Send,
  Sparkles,
  User,
  X,
} from "lucide-react";
import "./styles.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";
const AI_API_BASE_URL =
  import.meta.env.VITE_AI_API_BASE_URL || "https://etox6lj346.execute-api.ap-northeast-1.amazonaws.com";

const employeeOptions = [
  "従業員数の制約なし",
  "5名以下",
  "20名以下",
  "50名以下",
  "100名以下",
  "300名以下",
  "900名以下",
  "901名以上",
];

const targetAreaOptions = [
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
];

const purposeOptions = [
  "新たな事業を行いたい",
  "販路拡大・海外展開をしたい",
  "イベント・事業運営支援がほしい",
  "事業を引き継ぎたい",
  "研究開発・実証事業を行いたい",
  "人材育成を行いたい",
  "資金繰りを改善したい",
  "設備整備・IT導入をしたい",
  "雇用・職場環境を改善したい",
  "エコ・SDGs活動支援がほしい",
  "災害（自然災害、感染症等）支援がほしい",
  "教育・子育て・少子化支援がほしい",
  "スポーツ・文化支援がほしい",
  "安全・防災対策支援がほしい",
  "まちづくり・地域振興支援がほしい",
];

const industryOptions = [
  "農業、林業",
  "漁業",
  "鉱業、採石業、砂利採取業",
  "建設業",
  "製造業",
  "電気・ガス・熱供給・水道業",
  "情報通信業",
  "運輸業、郵便業",
  "卸売業、小売業",
  "金融業、保険業",
  "不動産業、物品賃貸業",
  "学術研究、専門・技術サービス業",
  "宿泊業、飲食サービス業",
  "生活関連サービス業、娯楽業",
  "教育、学習支援業",
  "医療、福祉",
  "複合サービス事業",
  "サービス業（他に分類されないもの）",
  "公務（他に分類されるものを除く）",
  "分類不能の産業",
];

type SearchRequest = {
  keyword: string;
  sort: "created_date" | "acceptance_start_datetime" | "acceptance_end_datetime";
  order: "ASC" | "DESC";
  acceptance: "0" | "1";
  use_purpose?: string;
  industry?: string;
  target_number_of_employees?: string;
  target_area_search?: string;
  institution_name?: string;
};

type SubsidySummary = {
  id: string;
  name: string;
  title?: string;
  target_area_search?: string;
  subsidy_max_limit?: number;
  acceptance_start_datetime?: string;
  acceptance_end_datetime?: string;
  target_number_of_employees?: string;
  institution_name?: string;
};

type ResultFile = {
  name?: string;
  data?: string;
};

type Workflow = {
  id?: string;
  target_area_search?: string;
  target_area_detail?: string;
  fiscal_year_round?: string;
  acceptance_start_datetime?: string;
  acceptance_end_datetime?: string;
  project_end_deadline?: string;
};

type SubsidyDetail = SubsidySummary & {
  subsidy_catch_phrase?: string;
  detail?: string;
  use_purpose?: string;
  industry?: string;
  target_area_detail?: string;
  subsidy_rate?: string;
  request_reception_presence?: string;
  is_enable_multiple_request?: boolean;
  front_subsidy_detail_page_url?: string;
  granttype?: string;
  application_guidelines?: ResultFile[];
  outline_of_grant?: ResultFile[];
  application_form?: ResultFile[];
  workflow?: Workflow[];
};

type ApiResponse<T> = {
  metadata?: {
    type?: string;
    resultset?: { count?: number };
  };
  result?: T[];
  message?: string;
  title?: string;
  errorCode?: string;
};

type SearchState = {
  keyword: string;
  acceptance: "0" | "1";
  sort: SearchRequest["sort"];
  order: SearchRequest["order"];
  use_purpose: string;
  industry: string;
  target_number_of_employees: string;
  target_area_search: string;
  institution_name: string;
};

type ChatRole = "assistant" | "user";

type ChatMessage = {
  id: string;
  role: ChatRole;
  text: string;
  recommendations?: ChatRecommendation[];
};

type ChatRecommendation = {
  id: string;
  title: string;
  institution?: string;
  deadline?: string;
  amount?: number;
  area?: string;
  reason?: string;
  url?: string;
};

type ChatResponse = {
  answer: string;
  recommendations?: ChatRecommendation[];
};

const initialSearch: SearchState = {
  keyword: "IT",
  acceptance: "1",
  sort: "acceptance_end_datetime",
  order: "ASC",
  use_purpose: "",
  industry: "",
  target_number_of_employees: "",
  target_area_search: "全国",
  institution_name: "",
};

const dateFormatter = new Intl.DateTimeFormat("ja-JP", {
  timeZone: "Asia/Tokyo",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

const yenFormatter = new Intl.NumberFormat("ja-JP", {
  style: "currency",
  currency: "JPY",
  maximumFractionDigits: 0,
});

function cleanPayload(state: SearchState): SearchRequest {
  const payload: SearchRequest = {
    keyword: state.keyword.trim(),
    acceptance: state.acceptance,
    sort: state.sort,
    order: state.order,
  };

  for (const key of [
    "use_purpose",
    "industry",
    "target_number_of_employees",
    "target_area_search",
    "institution_name",
  ] as const) {
    const value = state[key].trim();
    if (value) {
      payload[key] = value;
    }
  }

  return payload;
}

function formatDate(value?: string) {
  if (!value) return "未設定";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return dateFormatter.format(date);
}

function formatAmount(value?: number) {
  if (value === undefined || value === null || Number.isNaN(Number(value))) {
    return "未設定";
  }
  return yenFormatter.format(Number(value));
}

function splitTokens(value?: string) {
  return value?.split(" / ").filter(Boolean) ?? [];
}

function stripHtml(value?: string) {
  if (!value) return "";
  const doc = new DOMParser().parseFromString(value, "text/html");
  return doc.body.textContent?.replace(/\s+/g, " ").trim() || value;
}

function sanitizeDetailHtml(value: string) {
  const doc = new DOMParser().parseFromString(value, "text/html");
  const allowedTags = new Set([
    "A",
    "B",
    "BR",
    "DIV",
    "EM",
    "LI",
    "OL",
    "P",
    "SPAN",
    "STRONG",
    "TABLE",
    "TBODY",
    "TD",
    "TH",
    "THEAD",
    "TR",
    "U",
    "UL",
  ]);

  doc.body.querySelectorAll("*").forEach((element) => {
    if (!allowedTags.has(element.tagName)) {
      element.replaceWith(...Array.from(element.childNodes));
      return;
    }

    Array.from(element.attributes).forEach((attribute) => {
      const name = attribute.name.toLowerCase();
      const value = attribute.value;
      if (name.startsWith("on") || name === "style" || name === "class") {
        element.removeAttribute(attribute.name);
      }
      if (element.tagName === "A" && name === "href" && !/^https?:\/\//i.test(value)) {
        element.removeAttribute(attribute.name);
      }
      if (element.tagName !== "A" && name !== "colspan" && name !== "rowspan") {
        element.removeAttribute(attribute.name);
      }
    });

    if (element.tagName === "A") {
      element.setAttribute("target", "_blank");
      element.setAttribute("rel", "noreferrer");
    }
  });

  return doc.body.innerHTML;
}

function isDeadlineSoon(value?: string) {
  if (!value) return false;
  const end = new Date(value).getTime();
  const now = Date.now();
  return end >= now && end - now <= 1000 * 60 * 60 * 24 * 30;
}

async function readJson<T>(response: Response): Promise<ApiResponse<T>> {
  const contentType = response.headers.get("content-type") || "";
  const text = await response.text();
  if (!text) return {};
  if (contentType.includes("text/html") || /^\s*<!doctype html/i.test(text)) {
    throw new Error(
      "API proxy is returning the React app HTML. Configure the production host to rewrite /api/* to the JGrants API.",
    );
  }
  try {
    return JSON.parse(text) as ApiResponse<T>;
  } catch {
    throw new Error(text.slice(0, 300));
  }
}

async function apiGet<T>(path: string, params?: URLSearchParams) {
  const url = new URL(`${API_BASE_URL}${path}`, window.location.origin);
  if (params) {
    params.forEach((value, key) => url.searchParams.set(key, value));
  }
  const response = await fetch(url.toString(), {
    headers: { Accept: "application/json" },
  });
  const data = await readJson<T>(response);
  if (!response.ok) {
    const message = data.message || data.title || data.errorCode || response.statusText;
    throw new Error(`${response.status}: ${message}`);
  }
  return data;
}

async function searchSubsidies(payload: SearchRequest) {
  const params = new URLSearchParams();
  Object.entries(payload).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      params.set(key, value);
    }
  });
  return apiGet<SubsidySummary>("/v1/public/subsidies", params);
}

async function loadSubsidyDetail(id: string) {
  return apiGet<SubsidyDetail>(`/v2/public/subsidies/id/${encodeURIComponent(id)}`);
}

async function sendChatMessage(message: string, history: ChatMessage[]) {
  const response = await fetch(`${AI_API_BASE_URL}/chat`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      message,
      history: history.slice(-8).map(({ role, text }) => ({ role, content: text })),
    }),
  });
  const data = (await response.json().catch(() => ({}))) as Partial<ChatResponse> & { message?: string };
  if (!response.ok) {
    throw new Error(data.message || `Chat API error: ${response.status}`);
  }
  return data as ChatResponse;
}

function downloadFile(file: ResultFile) {
  if (!file.data) return;
  const byteCharacters = atob(file.data);
  const byteNumbers = Array.from(byteCharacters, (character) => character.charCodeAt(0));
  const blob = new Blob([new Uint8Array(byteNumbers)], { type: "application/pdf" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = file.name || "jgrants-document.pdf";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function normalizeFiles(files?: ResultFile[] | ResultFile) {
  if (!files) return [];
  return Array.isArray(files) ? files : [files];
}

function StatusPill({ item }: { item: SubsidySummary }) {
  const end = item.acceptance_end_datetime ? new Date(item.acceptance_end_datetime).getTime() : 0;
  const expired = end > 0 && end < Date.now();
  const soon = isDeadlineSoon(item.acceptance_end_datetime);
  const label = expired ? "終了" : soon ? "締切間近" : "受付中";
  return <span className={`status status-${expired ? "closed" : soon ? "soon" : "open"}`}>{label}</span>;
}

function Field({ label, value }: { label: string; value?: React.ReactNode }) {
  return (
    <div className="field">
      <dt>{label}</dt>
      <dd>{value || "未設定"}</dd>
    </div>
  );
}

function DocumentList({ title, files }: { title: string; files?: ResultFile[] }) {
  if (!files?.length) return null;
  return (
    <section className="detail-section">
      <h3>{title}</h3>
      <div className="document-list">
        {files.map((file, index) => (
          <button
            className="document-button"
            key={`${file.name}-${index}`}
            type="button"
            onClick={() => downloadFile(file)}
            disabled={!file.data}
            title={`${file.name || "資料"}をダウンロード`}
          >
            <FileText size={16} />
            <span>{file.name || `資料 ${index + 1}`}</span>
            <Download size={15} />
          </button>
        ))}
      </div>
    </section>
  );
}

function DetailPanel({
  detail,
  loading,
  onClose,
}: {
  detail?: SubsidyDetail;
  loading: boolean;
  onClose: () => void;
}) {
  return (
    <aside className={`detail-panel ${detail || loading ? "is-open" : ""}`} aria-live="polite">
      <div className="detail-header">
        <div>
          <p className="eyebrow">補助金詳細</p>
          <h2>{detail?.title || "読み込み中"}</h2>
        </div>
        <button className="icon-button" type="button" onClick={onClose} title="詳細を閉じる">
          <X size={20} />
        </button>
      </div>

      {loading ? (
        <div className="loading-block">
          <Loader2 className="spin" size={28} />
          <span>詳細を取得しています</span>
        </div>
      ) : detail ? (
        <div className="detail-scroll">
          <div className="detail-intro">
            <span className="subsidy-code">{detail.name}</span>
            {detail.granttype && <span className="grant-type">{detail.granttype}</span>}
            <p>{detail.subsidy_catch_phrase || stripHtml(detail.detail) || "概要情報はありません。"}</p>
          </div>

          <dl className="field-grid">
            <Field label="制度名" value={detail.institution_name} />
            <Field label="上限額" value={formatAmount(detail.subsidy_max_limit)} />
            <Field label="補助率" value={detail.subsidy_rate} />
            <Field label="受付" value={detail.request_reception_presence} />
            <Field label="複数回申請" value={detail.is_enable_multiple_request ? "可" : "不可"} />
            <Field label="従業員数" value={detail.target_number_of_employees} />
            <Field label="募集開始" value={formatDate(detail.acceptance_start_datetime)} />
            <Field label="募集終了" value={formatDate(detail.acceptance_end_datetime)} />
          </dl>

          {detail.detail && (
            <section className="detail-section">
              <h3>概要</h3>
              <div className="rich-copy" dangerouslySetInnerHTML={{ __html: sanitizeDetailHtml(detail.detail) }} />
            </section>
          )}

          <section className="detail-section">
            <h3>対象条件</h3>
            <div className="tag-group">
              {[
                ...splitTokens(detail.target_area_search),
                ...splitTokens(detail.use_purpose),
                ...splitTokens(detail.industry),
              ].map((token) => (
                <span className="tag" key={token}>
                  {token}
                </span>
              ))}
            </div>
          </section>

          {!!detail.workflow?.length && (
            <section className="detail-section">
              <h3>募集回</h3>
              <div className="workflow-list">
                {detail.workflow.map((workflow) => (
                  <div className="workflow-item" key={workflow.id || workflow.fiscal_year_round}>
                    <strong>{workflow.fiscal_year_round || "募集回"}</strong>
                    <span>{workflow.target_area_search || workflow.target_area_detail || "地域未設定"}</span>
                    <span>
                      {formatDate(workflow.acceptance_start_datetime)} - {formatDate(workflow.acceptance_end_datetime)}
                    </span>
                  </div>
                ))}
              </div>
            </section>
          )}

          <DocumentList title="公募要領" files={normalizeFiles(detail.application_guidelines)} />
          <DocumentList title="交付要綱" files={normalizeFiles(detail.outline_of_grant)} />
          <DocumentList title="申請様式" files={normalizeFiles(detail.application_form)} />

          {detail.front_subsidy_detail_page_url && (
            <a className="external-link" href={detail.front_subsidy_detail_page_url} target="_blank" rel="noreferrer">
              <ExternalLink size={16} />
              JGrants の詳細ページを開く
            </a>
          )}
        </div>
      ) : (
        <div className="empty-detail">結果を選択すると詳細を表示します。</div>
      )}
    </aside>
  );
}

const promptSuggestions = [
  "東京都でIT導入に使える補助金を教えて",
  "製造業で設備投資に使える受付中の制度は？",
  "小規模事業者向けで締切が近いものを探して",
];

function ChatRecommendationCard({ item }: { item: ChatRecommendation }) {
  return (
    <article className="chat-recommendation">
      <div className="chat-recommendation-main">
        <span className="subsidy-code">{item.id}</span>
        <h3>{item.title}</h3>
        <p>{item.reason || item.institution || "条件に合いそうな補助金です。"}</p>
      </div>
      <div className="chat-recommendation-meta">
        <span>{formatAmount(item.amount)}</span>
        <span>{item.area || "地域未設定"}</span>
        <span>締切 {formatDate(item.deadline)}</span>
      </div>
      {item.url && (
        <a className="external-link compact" href={item.url} target="_blank" rel="noreferrer">
          <ExternalLink size={15} />
          詳細
        </a>
      )}
    </article>
  );
}

function ChatApp() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      text:
        "補助金候補を探すために、いくつか確認します。まず、事業内容、対象地域、業種、従業員数、補助金の使い道を分かる範囲で教えてください。",
    },
  ]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string>();

  async function submitChat(event?: FormEvent, suggestedPrompt?: string) {
    event?.preventDefault();
    const text = (suggestedPrompt || input).trim();
    if (!text || isSending) return;

    const userMessage: ChatMessage = { id: crypto.randomUUID(), role: "user", text };
    const nextMessages = [...messages, userMessage];
    setMessages(nextMessages);
    setInput("");
    setIsSending(true);
    setError(undefined);

    try {
      const data = await sendChatMessage(text, messages);
      setMessages([
        ...nextMessages,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          text: data.answer,
          recommendations: data.recommendations ?? [],
        },
      ]);
    } catch (chatError) {
      setError(chatError instanceof Error ? chatError.message : "チャット応答に失敗しました。");
      setMessages(nextMessages);
    } finally {
      setIsSending(false);
    }
  }

  return (
    <main className="ai-shell">
      <header className="ai-topbar">
        <div>
          <p className="eyebrow">AI subsidy assistant</p>
          <h1>補助金チャット</h1>
        </div>
        <nav className="top-actions" aria-label="アプリ切り替え">
          <a className="ghost-button" href="/" title="検索画面へ戻る">
            <Search size={17} />
            <span>検索</span>
          </a>
          <div className="api-chip">/sam/chat</div>
        </nav>
      </header>

      <section className="chat-layout">
        <aside className="chat-context">
          <div className="context-block">
            <Sparkles size={22} />
            <h2>相談のコツ</h2>
            <p>地域、業種、資金の使い道、従業員数、締切の希望を入れると候補を絞りやすくなります。</p>
          </div>
          <div className="suggestion-list">
            {promptSuggestions.map((prompt) => (
              <button
                className="suggestion-button"
                key={prompt}
                type="button"
                onClick={() => submitChat(undefined, prompt)}
                disabled={isSending}
              >
                <MessageCircle size={16} />
                <span>{prompt}</span>
              </button>
            ))}
          </div>
        </aside>

        <section className="chat-panel" aria-live="polite">
          <div className="message-list">
            {messages.map((message) => (
              <article className={`message message-${message.role}`} key={message.id}>
                <div className="message-avatar">{message.role === "assistant" ? <Bot size={18} /> : <User size={18} />}</div>
                <div className="message-body">
                  <p>{message.text}</p>
                  {!!message.recommendations?.length && (
                    <div className="chat-recommendations">
                      {message.recommendations.map((item) => (
                        <ChatRecommendationCard item={item} key={`${item.id}-${item.title}`} />
                      ))}
                    </div>
                  )}
                </div>
              </article>
            ))}
            {isSending && (
              <article className="message message-assistant">
                <div className="message-avatar">
                  <Bot size={18} />
                </div>
                <div className="message-body typing">
                  <Loader2 className="spin" size={18} />
                  <span>JGrantsから候補を確認しています</span>
                </div>
              </article>
            )}
          </div>

          {error && <div className="error-banner">{error}</div>}

          <form className="chat-composer" onSubmit={submitChat}>
            <input
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="例: 大阪の飲食店で省エネ設備に使える補助金は？"
              disabled={isSending}
            />
            <button className="primary-button" type="submit" disabled={!input.trim() || isSending} title="送信">
              {isSending ? <Loader2 className="spin" size={18} /> : <Send size={18} />}
              <span>送信</span>
            </button>
          </form>
        </section>
      </section>
    </main>
  );
}

function SearchApp() {
  const [search, setSearch] = useState<SearchState>(initialSearch);
  const [items, setItems] = useState<SubsidySummary[]>([]);
  const [count, setCount] = useState(0);
  const [selectedId, setSelectedId] = useState<string>();
  const [detail, setDetail] = useState<SubsidyDetail>();
  const [isSearching, setIsSearching] = useState(false);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [error, setError] = useState<string>();

  const payload = useMemo(() => cleanPayload(search), [search]);
  const keywordError =
    payload.keyword.length < 2 || /\s/.test(payload.keyword) ? "キーワードは2文字以上、スペースなしで入力してください。" : "";

  async function runSearch(nextPayload = payload) {
    if (nextPayload.keyword.length < 2 || /\s/.test(nextPayload.keyword)) {
      setError("キーワードは2文字以上、スペースなしで入力してください。");
      return;
    }
    setIsSearching(true);
    setError(undefined);
    try {
      const data = await searchSubsidies(nextPayload);
      setItems(data.result ?? []);
      setCount(data.metadata?.resultset?.count ?? data.result?.length ?? 0);
      setSelectedId(undefined);
      setDetail(undefined);
    } catch (searchError) {
      setItems([]);
      setCount(0);
      setError(searchError instanceof Error ? searchError.message : "検索に失敗しました。");
    } finally {
      setIsSearching(false);
    }
  }

  async function selectItem(item: SubsidySummary) {
    setSelectedId(item.id);
    setDetail(undefined);
    setIsLoadingDetail(true);
    setError(undefined);
    try {
      const data = await loadSubsidyDetail(item.id);
      setDetail(data.result?.[0] ?? item);
    } catch (detailError) {
      setDetail(item);
      setError(detailError instanceof Error ? detailError.message : "詳細の取得に失敗しました。");
    } finally {
      setIsLoadingDetail(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    runSearch();
  }

  useEffect(() => {
    runSearch(cleanPayload(initialSearch));
  }, []);

  return (
    <main className="app-shell">
      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">jGrants public API</p>
            <h1>補助金検索</h1>
          </div>
          <nav className="top-actions" aria-label="アプリ切り替え">
            <a className="ghost-button" href="/ai" title="AIチャットを開く">
              <Bot size={17} />
              <span>AI相談</span>
            </a>
            <div className="api-chip">/v1/public/subsidies</div>
          </nav>
        </header>

        <form className="filters" onSubmit={submit}>
          <div className="search-row">
            <label className="keyword-field">
              <span>検索キーワード</span>
              <div className="input-with-icon">
                <Search size={18} />
                <input
                  value={search.keyword}
                  onChange={(event) => setSearch((current) => ({ ...current, keyword: event.target.value }))}
                  placeholder="例: IT"
                  maxLength={255}
                />
              </div>
            </label>
            <button className="primary-button" type="submit" disabled={isSearching || !!keywordError} title="検索する">
              {isSearching ? <Loader2 className="spin" size={18} /> : <Search size={18} />}
              <span>検索</span>
            </button>
            <button
              className="ghost-button"
              type="button"
              onClick={() => {
                setSearch(initialSearch);
                runSearch(cleanPayload(initialSearch));
              }}
              title="条件を初期化"
            >
              <RefreshCw size={17} />
              <span>初期化</span>
            </button>
          </div>

          {keywordError && <p className="validation">{keywordError}</p>}

          <div className="filter-grid">
            <label>
              <span>募集期間</span>
              <select
                value={search.acceptance}
                onChange={(event) => setSearch((current) => ({ ...current, acceptance: event.target.value as "0" | "1" }))}
              >
                <option value="1">受付中のみ</option>
                <option value="0">すべて</option>
              </select>
            </label>
            <label>
              <span>地域</span>
              <select
                value={search.target_area_search}
                onChange={(event) => setSearch((current) => ({ ...current, target_area_search: event.target.value }))}
              >
                <option value="">指定なし</option>
                {targetAreaOptions.map((option) => (
                  <option key={option}>{option}</option>
                ))}
              </select>
            </label>
            <label>
              <span>従業員数</span>
              <select
                value={search.target_number_of_employees}
                onChange={(event) =>
                  setSearch((current) => ({ ...current, target_number_of_employees: event.target.value }))
                }
              >
                <option value="">指定なし</option>
                {employeeOptions.map((option) => (
                  <option key={option}>{option}</option>
                ))}
              </select>
            </label>
            <label>
              <span>利用目的</span>
              <select
                value={search.use_purpose}
                onChange={(event) => setSearch((current) => ({ ...current, use_purpose: event.target.value }))}
              >
                <option value="">指定なし</option>
                {purposeOptions.map((option) => (
                  <option key={option}>{option}</option>
                ))}
              </select>
            </label>
            <label>
              <span>業種</span>
              <select
                value={search.industry}
                onChange={(event) => setSearch((current) => ({ ...current, industry: event.target.value }))}
              >
                <option value="">指定なし</option>
                {industryOptions.map((option) => (
                  <option key={option}>{option}</option>
                ))}
              </select>
            </label>
            <label>
              <span>制度名</span>
              <input
                value={search.institution_name}
                onChange={(event) => setSearch((current) => ({ ...current, institution_name: event.target.value }))}
                placeholder="制度名で絞り込み"
              />
            </label>
          </div>

          <div className="sort-row">
            <Filter size={17} />
            <label>
              <span>並び替え</span>
              <select
                value={search.sort}
                onChange={(event) => setSearch((current) => ({ ...current, sort: event.target.value as SearchRequest["sort"] }))}
              >
                <option value="acceptance_end_datetime">募集終了日時</option>
                <option value="acceptance_start_datetime">募集開始日時</option>
                <option value="created_date">作成日時</option>
              </select>
            </label>
            <label>
              <span>順序</span>
              <select
                value={search.order}
                onChange={(event) => setSearch((current) => ({ ...current, order: event.target.value as SearchRequest["order"] }))}
              >
                <option value="ASC">昇順</option>
                <option value="DESC">降順</option>
              </select>
            </label>
            <ArrowDownUp size={17} />
          </div>
        </form>

        {error && <div className="error-banner">{error}</div>}

        <section className="results-header">
          <div>
            <p className="eyebrow">検索結果</p>
            <h2>{isSearching ? "検索中" : `${count.toLocaleString("ja-JP")}件`}</h2>
          </div>
          <div className="request-preview">
            <span>query</span>
            <code>{new URLSearchParams(payload).toString()}</code>
          </div>
        </section>

        <section className="result-list">
          {isSearching ? (
            <div className="loading-block">
              <Loader2 className="spin" size={28} />
              <span>補助金を検索しています</span>
            </div>
          ) : items.length ? (
            items.map((item) => (
              <article
                className={`result-item ${selectedId === item.id ? "is-selected" : ""}`}
                key={item.id}
                onClick={() => selectItem(item)}
              >
                <div className="result-main">
                  <div className="result-title-row">
                    <StatusPill item={item} />
                    <span className="subsidy-code">{item.name}</span>
                  </div>
                  <h3>{item.title || item.name}</h3>
                  <p>{item.institution_name || "制度名未設定"}</p>
                </div>
                <div className="result-meta">
                  <span>{formatAmount(item.subsidy_max_limit)}</span>
                  <span>{item.target_area_search || "地域未設定"}</span>
                  <span>締切 {formatDate(item.acceptance_end_datetime)}</span>
                </div>
              </article>
            ))
          ) : (
            <div className="empty-state">条件に一致する補助金が見つかりませんでした。</div>
          )}
        </section>
      </section>

      <DetailPanel detail={detail} loading={isLoadingDetail} onClose={() => {
        setSelectedId(undefined);
        setDetail(undefined);
      }} />
    </main>
  );
}

function App() {
  return window.location.pathname === "/ai" ? <ChatApp /> : <SearchApp />;
}

createRoot(document.getElementById("root")!).render(<App />);
