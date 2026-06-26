# JGrants Subsidy UI

React UI for searching and reviewing subsidies from the JGrants public API defined in `jgrants-api.yaml`.

## Run locally

```bash
npm install
npm run dev -- --port 5173
```

Open `http://127.0.0.1:5173/`.

The local Vite server proxies `/api` to `https://api.jgrants-portal.go.jp/exp` so browser requests avoid CORS issues during development.

## Build

```bash
npm run build
```

## Deployment

The app uses `/api` as its browser-facing API base. In local development, Vite proxies that path. In AWS Amplify Hosting, add a rewrite before the SPA fallback:

| Source address | Target address | Type |
| --- | --- | --- |
| `/api/<*>` | `https://api.jgrants-portal.go.jp/exp/<*>` | `200 (Rewrite)` |

Keep the normal SPA fallback after it:

| Source address | Target address | Type |
| --- | --- | --- |
| `</^[^.]+$|\.(?!(css|gif|ico|jpg|jpeg|js|png|txt|svg|woff|woff2|ttf|map|json)$)([^.]+$)/>` | `/index.html` | `200 (Rewrite)` |

If you use your own backend proxy instead, set `VITE_API_BASE_URL` to that same-origin path or URL.

```bash
VITE_API_BASE_URL=/api npm run build
```

Dates are formatted for Japan time (`Asia/Tokyo`) and amounts are formatted as Japanese yen.
