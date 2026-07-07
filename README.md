# JGrants Subsidy UI

React UI for searching and reviewing subsidies from the JGrants public API defined in `jgrants-api.yaml`.

## Run locally

```bash
npm install
npm run dev -- --port 5173
```

Open `http://127.0.0.1:5173/`.

The local Vite server proxies `/api` to `https://api.jgrants-portal.go.jp/exp` so browser requests avoid CORS issues during development.
The AI chatbot screen is available at `http://127.0.0.1:5173/ai`. By default it uses the deployed Tokyo API Gateway backend.

## Run the chatbot backend locally

```bash
cd backend
sam build
sam local start-api --profile netbot --region ap-northeast-1
```

In another terminal:

```bash
VITE_AI_API_BASE_URL=/sam \
npm run dev -- --port 5173
```

## Build

```bash
npm run build
```

## Deploy SAM backend

The backend SAM config is set to AWS profile `netbot` and region `ap-northeast-1` (Tokyo).
The Lambda uses Amazon Bedrock for intake conversation, then searches JGrants after it has enough information.
The default model is `anthropic.claude-3-haiku-20240307-v1:0`; change `BEDROCK_MODEL_ID` in `backend/template.yaml` if you want a different Bedrock model.

```bash
cd backend
sam build
sam deploy
```

Current deployed backend:

```bash
https://etox6lj346.execute-api.ap-northeast-1.amazonaws.com
```

## Deployment

The app uses `/api` as its browser-facing API base. In local development, Vite proxies that path. In AWS Amplify Hosting, add a rewrite before the SPA fallback:

| Source address | Target address | Type |
| --- | --- | --- |
| `/api/<*>` | `https://api.jgrants-portal.go.jp/exp/<*>` | `200 (Rewrite)` |

If you prefer same-origin chatbot calls in Amplify, set `VITE_AI_API_BASE_URL=/sam` and add another rewrite:

| Source address | Target address | Type |
| --- | --- | --- |
| `/sam/<*>` | `https://YOUR_API_ID.execute-api.ap-northeast-1.amazonaws.com/<*>` | `200 (Rewrite)` |

Keep the normal SPA fallback after it:

| Source address | Target address | Type |
| --- | --- | --- |
| `</^[^.]+$|\.(?!(css|gif|ico|jpg|jpeg|js|png|txt|svg|woff|woff2|ttf|map|json)$)([^.]+$)/>` | `/index.html` | `200 (Rewrite)` |

If you use your own backend proxy instead, set `VITE_API_BASE_URL` to that same-origin path or URL.

```bash
VITE_API_BASE_URL=/api npm run build
```

Dates are formatted for Japan time (`Asia/Tokyo`) and amounts are formatted as Japanese yen.
