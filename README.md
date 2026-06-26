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

Set `VITE_API_BASE_URL` if the deployed app should call a different same-origin backend or API proxy.

```bash
VITE_API_BASE_URL=/api npm run build
```

Dates are formatted for Japan time (`Asia/Tokyo`) and amounts are formatted as Japanese yen.
