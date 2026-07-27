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

- React 19 + TypeScript 6 + Vite 8
- [Mantine v9](https://mantine.dev/) UI primitives
- [TanStack Query v5](https://tanstack.com/query) for data fetching
- [TanStack Table v8](https://tanstack.com/table) for the devices and entities tables
- [Vitest v4](https://vitest.dev/) + Testing Library
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
├── api/            # typed fetch client, SSE helper, base-path resolution
├── components/     # shared UI (Layout, SeverityBadge, LiveIndicator)
├── hooks/          # TanStack Query hooks per endpoint + useLiveEvents
├── pages/
│   ├── Devices/    # DevicesPage + Table + FilterBar + ActionRow + EditDeviceDrawer + modals
│   ├── Entities/   # the same, for entities
│   └── Settings/   # Device / Entity settings, Global Policies, Exceptions
├── theme.ts        # Mantine theme
├── main.tsx        # entry
└── App.tsx         # provider stack + router
```

## Notes

- `src/api/generated.ts` is gitignored — regenerate with `task gen-api` (or `npm run gen:api`) whenever the backend's schema changes.
- Tests stub `globalThis.fetch` directly (not MSW) because MSW v2 has interop issues with Vitest + jsdom.
- `package.json` declares `engines: node >=20`; CI builds on Node 24.
- Every URL the app emits resolves against `api/basePath.ts`, not the origin —
  see [ingress](../../home-curator/README.md#ingress) for why.
