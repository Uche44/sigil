# Going live

The Solana program is already deployed on **devnet**, so going live means
hosting the web app and API, pointing a domain at them, and regenerating labels
so the QRs use that domain.

## Recommended target

| Piece | Where | Why |
|---|---|---|
| Web (Next.js) | Vercel | Native Next hosting, free tier, HTTPS, CDN |
| API (FastAPI) | Render, Docker | Long-running process with a persistent disk |
| Database | SQLite on the Render disk | No code change; single instance is fine for a demo |
| Uploads | Same Render disk (`/data/uploads`) | Photos survive deploys |
| RPC | Helius / QuickNode free tier | Public devnet RPC times out under load |
| Domain | e.g. `sigil.example` + `api.sigil.example` | Short, printable, trustworthy |

Vercel cannot host the API: it needs a persistent disk and a long-running
process, and the database is SQLite today. Render's disk solves both without a
database migration.

This is a hackathon deployment, not a scale-out design. SQLite and local uploads
mean one API instance. If Sigil grows, move to Postgres and object storage.

## Prerequisites

- The repo on GitHub. A remote exists, but this machine is not authenticated:
  ```bash
  gh auth login          # or push with your own credentials
  git push origin main
  ```
- A Vercel account and a Render account, both connected to that GitHub repo.
- A domain. Without one you can use the free `*.vercel.app` and
  `*.onrender.com` URLs, but labels will be longer and less convincing.
- A devnet RPC endpoint from Helius or QuickNode (free tier is enough).

## 1. Deploy the API on Render

`render.yaml` is a blueprint for this repo. In Render: **New → Blueprint**, pick
the repo, and apply. It creates:

- a Docker web service from `api/Dockerfile`
- a 1 GB disk mounted at `/data`
- generated token/device secrets
- the program ID and admin wallet

Set these environment variables in the dashboard when prompted:

```
SIGIL_RPC_URL=https://devnet.helius-rpc.com/?api-key=...
SIGIL_WEB_BASE_URL=https://<web-domain>
SIGIL_PUBLIC_BASE_URL=https://<api-domain>
SIGIL_CORS_ORIGINS=https://<web-domain>
```

`SIGIL_WEB_BASE_URL` is what QR codes encode. `SIGIL_PUBLIC_BASE_URL` is what
uploaded photo URLs use.

Use a paid RPC for `SIGIL_RPC_URL` (server-side reads). Do **not** put that key
in the web app: `NEXT_PUBLIC_*` values are shipped to every browser. Keep the
browser on `https://api.devnet.solana.com`, or use a domain-restricted key.

The blueprint defaults `SIGIL_RPC_URL` to the public devnet endpoint so the
first deploy works without another account. Replace it with Helius or QuickNode
before relying on it; the public endpoint occasionally times out.

Wait for the health check on `/api/v1/health`, then open
`https://<api-domain>/api/v1/config` and confirm the program ID and RPC.

## 2. Deploy the web app on Vercel

Import the repo and set:

- **Root Directory:** `apps/web`
- **Framework:** Next.js
- **Environment variables:**
  ```
  NEXT_PUBLIC_API_URL=https://<api-domain>
  NEXT_PUBLIC_SOLANA_RPC=https://devnet.helius-rpc.com/?api-key=...
  ```

Both are public values compiled into the browser bundle. The Solana RPC must be
the same cluster as the API (devnet).

## 3. Add domains

- `sigil.example` → Vercel → the web project.
- `api.sigil.example` → Render → the API service.

Update the Render env vars and redeploy. Update Vercel's
`NEXT_PUBLIC_API_URL` if the API domain changed.

CORS is not a wildcard: the exact web origin must be in `SIGIL_CORS_ORIGINS`.

## 4. Regenerate every label

QR codes are generated from `SIGIL_WEB_BASE_URL` at download time. Any label
printed with `localhost`, a LAN IP, or an old domain is permanent and cannot be
fixed. After the domain is live:

1. Open the producer dashboard.
2. Download the label sheet again for each active batch.
3. Print those.

Scan one with a phone on mobile data, not just the office Wi-Fi.

## 5. Production checklist

- [ ] `/api/v1/health` returns 200 over HTTPS.
- [ ] `/api/v1/config` shows the devnet program and the production RPC.
- [ ] Producer sign-in works with Phantom on devnet.
- [ ] Admin `/admin` shows the `6H47…` wallet as the on-chain registry admin.
- [ ] A new batch can be created, confirmed and its labels downloaded.
- [ ] Scanning a new label returns `REGISTERED` with the production domain.
- [ ] Recall changes the same label to `RECALLED` after at most 20 seconds.
- [ ] The old `localhost` labels are not in circulation.
- [ ] `SIGIL_TOKEN_SECRET` and `SIGIL_DEVICE_SECRET` are not the dev defaults.
- [ ] The deployer keypair and program keypair are backed up offline.

## Devnet vs mainnet

Keep the hackathon build on **devnet**. Judges expect it, and it costs nothing.

A mainnet launch is a separate decision:

- deploy the same program with the same program keypair to mainnet;
- initialise a fresh registry and make `6H47…` admin there;
- point `SIGIL_RPC_URL` and `NEXT_PUBLIC_SOLANA_RPC` at mainnet;
- pay real SOL for program rent and transaction fees;
- expect real issuers and real consequences for verification decisions.

The program ID can stay the same across clusters; the registry and all issuer
accounts are separate per cluster.

## If you only need a demo today

A Cloudflare quick tunnel exposes this laptop on a public HTTPS URL without
accounts:

```bash
cloudflared tunnel --url http://localhost:3000
```

But the tunnel dies with the laptop, and labels would point at a random
`trycloudflare.com` address. Use it to show the flow, not as the live product.
