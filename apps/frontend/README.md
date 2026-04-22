# Home Curator Frontend

React + Vite SPA consuming the Home Curator backend.

## Dev

```
cd apps/frontend
npm install

# In another terminal: run the backend
# cd ../backend && uv run uvicorn home_curator.main:app --port 8099

npm run gen:api          # regenerate typed API client (backend must be running)
npm run dev              # Vite dev server on :5173 with /api proxied to :8099
```

## Build

`npm run build` emits `dist/` which the backend serves at `/` in production.

## Test

```
npm run test             # watch mode
npm run test:run         # one-shot (CI)
npm run typecheck
```
