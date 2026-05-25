# Frontend

React 18 + TypeScript + Vite. Tailwind v4 via the `@tailwindcss/vite` plugin.

## Development

```bash
npm install
npm run dev
```

Requires the Django backend running at `http://localhost:8000`. The Vite dev server
proxies `/api` requests there automatically.

## Build

```bash
npm run build
```

Output goes to `../backend/static/dist/`. This directory is committed to git so
Railway/Render doesn't need a Node build step at deploy time.

## Demo credentials

Username: `analyst` / Password: `breathe2024`
