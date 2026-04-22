# Home Curator Frontend

React + Vite SPA consuming the Home Curator backend via a typed client generated from `/openapi.json`.

The common workflow is driven by the **root Taskfile** — see `../../README.md`. A typical day:

```bash
task dev              # backend (:8099) + frontend (:5173) together
task gen-api          # after the backend's OpenAPI shape changes
task test:frontend    # run the Vitest suite
task typecheck        # TypeScript strict check
```

## Stack

- React 18 + TypeScript 5 + Vite 5
- [Mantine v7](https://mantine.dev/) UI primitives
- [TanStack Query](https://tanstack.com/query) for data fetching
- [TanStack Table v8](https://tanstack.com/table) for the devices table
- [openapi-fetch](https://github.com/openapi-ts/openapi-typescript) typed client, generated from the backend's OpenAPI spec

## Direct commands

If you'd rather skip the Taskfile:

```bash
cd apps/frontend
npm install
npm run gen:api               # regenerate the typed API client (backend must be running)
npm run dev                   # Vite dev server on :5173 with /api proxied to :8099
npm run build                 # emits dist/ which the backend serves at / in production
npm run test:run              # Vitest one-shot
npm run typecheck             # tsc --noEmit
```

## Layout

```
src/
├── api/            # typed fetch client + SSE helper
├── components/     # shared UI (Layout, SeverityBadge, LiveIndicator)
├── hooks/          # TanStack Query hooks per endpoint + useLiveEvents
├── pages/
│   ├── Devices/    # DevicesPage + Table + FilterBar + ActionRow + IssuePanel + modals
│   └── Settings/   # Naming Conventions editor
├── theme.ts        # Mantine theme
├── main.tsx        # entry
└── App.tsx         # provider stack + router
```

## Notes

- `src/api/generated.ts` is gitignored — regenerate with `task gen-api` (or `npm run gen:api`) whenever the backend's schema changes.
- Tests stub `globalThis.fetch` directly (not MSW) because MSW v2 has interop issues with Vitest + jsdom.
- Node 22+ required.
