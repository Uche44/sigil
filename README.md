# Sigil

Sigil is an open-source, industry-agnostic product-record layer on Solana. A
verified producer registers a batch and commits a tamper-evident commitment to
it on-chain. Every unit gets a QR code. A shopper scans it with an ordinary
phone camera — no app, wallet or account — and sees what the code is registered
as, whether the batch is expired or recalled, and whether the code is being
scanned in unusual ways.

Sigil never claims a pack is "genuine". It says what the code is registered to
and asks the shopper to compare that with the pack in their hand.

## Verdicts

In this order of precedence:

1. `UNKNOWN` (red) — malformed link, unknown batch, or a serial that is not in
   the batch's Merkle tree.
2. `ISSUER_SUSPENDED` (red) — the producer's verification was withdrawn.
3. `RECALLED` (red) — the batch was recalled.
4. `EXPIRED` (red) — past the on-chain expiry.
5. `UNUSUAL_ACTIVITY` (amber) — registered and in date, but scan patterns look
   odd. This can be normal; the copy never says "fake".
6. `REGISTERED` (green) — registered and in date.

Every result also shows a `Verified producer` or `Unverified producer` label.

## Architecture

| Layer | Technology | Responsibility |
|---|---|---|
| Program | Rust + Anchor | Issuers, batches, expiry, recall, authority checks |
| API | Python + FastAPI | Serials, Merkle trees, details, scan events, verify |
| Web | Next.js + Tailwind | Shopper page, producer dashboard, admin page |
| Industry packs | JSON in `/packs` | Per-industry fields and shopper checklist |

Only small commitments go on-chain: a Merkle root, a details hash, expiry and
unit count. Product details, serials and scan events live off-chain.

The Merkle root is committed on-chain, so the server cannot invent valid serials
after signing. There is no instruction that can change a batch's root, details
hash, units or expiry — not even for the admin.

Anyone can check a code without trusting the server:

```
leaf = SHA-256("sigil:leaf:v1" || batch_pda_bytes || serial_bytes)
node = SHA-256("sigil:node:v1" || left || right)
```

The verify response can include the serial's leaf, the proof path and the batch
PDA. Folding the leaf up the path must equal the Merkle root stored in the batch
account. Odd levels duplicate the last node. The product details are canonical
JSON (sorted keys, no whitespace, UTF-8); their SHA-256 must equal the batch's
`details_hash`.

Shoppers never sign or send a transaction. All writes come from a producer
wallet (`register_issuer`, `create_batch`, `recall_batch`) or the admin wallet
(`set_issuer_status`).

## Repository layout

```
programs/sigil/      Anchor program
api/                 FastAPI service, Merkle library, tests
packs/               Industry pack JSON
apps/web/            Next.js app
scripts/             Admin CLI and scan simulator
```

## Local setup

### API

```bash
cd api
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e . pytest pytest-asyncio
cp ../.env.example ../.env        # edit it
set -a; . ../.env; set +a
.venv/bin/uvicorn sigil.server:app --reload --port 8000
```

`SIGIL_ADMIN_PUBKEYS` must contain the admin wallet (comma separated). The same
wallet should be the registry admin created by `initialize_registry`.

### Web

```bash
cd apps/web
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 \
NEXT_PUBLIC_SOLANA_RPC=https://api.devnet.solana.com \
npm run dev
```

Open http://localhost:3000.

To scan from a phone on the same network, set `SIGIL_WEB_BASE_URL` and
`SIGIL_PUBLIC_BASE_URL` to the machine's LAN address (for example
`http://192.168.1.20:3000` and `http://192.168.1.20:8000`), start Next with
`npm run dev -- -H 0.0.0.0`, and use that LAN address in `NEXT_PUBLIC_API_URL`.
The QR labels are generated from `SIGIL_WEB_BASE_URL`.

## Deploying the program (devnet)

The program is Anchor 0.31.1, built for Solana CLI 2.1.x.

Either use the official `solanafoundation/anchor:v0.31.1` image so the host does
not need Rust, Solana or Anchor installed:

```bash
# 1. create a deployer keypair once (inside the image, mounted into the repo)
docker run --rm -v "$PWD":/work -w /work \
  solanafoundation/anchor:v0.31.1 \
  solana-keygen new --no-bip39-passphrase -o /work/.deployer.json -f

# 2. create the program keypair, then put its pubkey in programs/sigil/src/lib.rs,
#    Anchor.toml and apps/web/idl/sigil.json
docker run --rm -v "$PWD":/work -w /work \
  solanafoundation/anchor:v0.31.1 \
  solana-keygen new --no-bip39-passphrase -o /work/target/deploy/sigil-keypair.json -f
docker run --rm -v "$PWD":/work -w /work \
  solanafoundation/anchor:v0.31.1 \
  solana-keygen pubkey /work/target/deploy/sigil-keypair.json

# 3. build and deploy
docker run --rm -v "$PWD":/work -w /work \
  solanafoundation/anchor:v0.31.1 \
  sh -c "solana config set -u devnet && solana airdrop 2 -k /work/.deployer.json && \
         anchor build && anchor deploy --provider.cluster devnet \
         --provider.wallet /work/.deployer.json"

# 4. initialize the singleton registry (the deployer becomes admin)
SIGIL_PROGRAM_ID=<deployed id> \
  api/.venv/bin/python scripts/solana_admin.py --keypair .deployer.json init-registry
```

Or install the matching toolchain on the host:

```bash
rustup default stable
cargo install anchor-cli --version 0.31.1 --locked
sh -c "$(curl -sSfL https://release.anza.xyz/v2.1.21/install)"
solana config set --url devnet --keypair .deployer.json
anchor build
anchor deploy --provider.cluster devnet --provider.wallet .deployer.json
api/.venv/bin/python scripts/solana_admin.py --keypair .deployer.json init-registry
```

Then set `SIGIL_PROGRAM_ID` and `SIGIL_ADMIN_PUBKEYS` to the deployed program and
deployer wallet. The admin page also offers a one-click registry initialisation
if the registry does not exist yet.

If the devnet faucet is rate limited, run the same flow against a local
validator:

```bash
solana-test-validator --reset --mint "$(solana-keygen pubkey .deployer.json)" &
solana airdrop 100 --url localhost --keypair .deployer.json
anchor build
anchor deploy --provider.cluster localnet --provider.wallet .deployer.json
api/.venv/bin/python scripts/solana_admin.py --rpc http://127.0.0.1:8899 \
  --keypair .deployer.json init-registry
```

Then start the API with `SIGIL_RPC_URL=http://127.0.0.1:8899` and run
`api/.venv/bin/python scripts/e2e_demo.py --api http://localhost:8000 --rpc http://127.0.0.1:8899`.

## Demo walkthrough

1. Connect the admin wallet on `/admin` and sign in.
2. On `/producer`, connect a different wallet, submit a company profile and
   sign `register_issuer`.
3. Back on `/admin`, verify the pending producer (one wallet transaction).
4. On `/producer`, create a batch through the wizard, sign it, download the PDF
   label sheet.
5. Scan a label with a phone. You get `REGISTERED` with the product details and
   the "compare with your pack" checklist.
6. Recall the batch from the producer dashboard. The same QR now shows
   `RECALLED` after at most 20 seconds (chain read cache).
7. Run `api/.venv/bin/python scripts/simulate_scans.py --batch-code <code> --serial <serial>`
   to see `UNUSUAL_ACTIVITY` appear from the scan hints.

`EXPIRED` is covered by the API tests rather than the live walkthrough: the
program refuses to create a batch that is already past its expiry, which is
deliberate. To see it live, create a batch expiring today and scan it after
midnight UTC.

If the devnet faucet rate-limits the deployer, fund it at
https://faucet.solana.com or use the localnet flow above.

To prove the "new industry, no code change" claim, drop another JSON file in
`/packs` following the existing shape. The API and wizard pick it up on restart.

If you want the whole path exercised without a browser, run the end-to-end
script with the deployer keypair and the API running:

```bash
api/.venv/bin/python scripts/e2e_demo.py --admin-keypair .deployer.json --recall
```

It creates a producer wallet, registers and verifies it, creates a batch, checks
a serial, and optionally recalls the batch. Every step is a real devnet
transaction.

## Tests

```bash
cd api && .venv/bin/pytest -q
cd ../apps/web && npx tsc --noEmit
```

The API tests cover the leaf/node/tree test vectors, canonical JSON, serial
format, pack validation, the full prepare → confirm → verify path, verdict
precedence, proof verification, tamper detection and the one-way recall rule.

Anchor tests live in `tests/sigil.ts` and run against a local validator with
`anchor test` (requires the Docker image or a local toolchain).

## The honest limits

These are product requirements, not disclaimers to bury:

1. A QR code cannot prove which physical pack it is stuck on. A real code copied
   onto a fake of the same product looks identical.
2. Scan-pattern hints can miss a single copy and can false-alarm on honest
   behaviour.
3. Someone outside the chain decides who counts as a real producer. For now that
   is the admin, later a regulator or trade body.
4. Physical protection such as tamper-evident labels matters and is outside the
   software.
5. Sigil reduces and exposes counterfeiting. It does not end it.

The strongest angle is live status: any shopper can check right now whether a
batch is expired or recalled, and copying a recalled product's code gains a
counterfeiter nothing.

## Security notes

- Scan events store a device hash (HMAC of IP and user agent), a coarse region
  and the verdict. Raw IPs and precise locations are not stored, and events are
  deleted after 90 days.
- The verify endpoint is rate limited per device hash and chain reads are cached
  briefly so recalls appear quickly without hammering the RPC.
- Uploaded images are re-encoded server-side before storage.
- The admin can verify or suspend issuers and can never edit a batch.
- The producer wallet is a single point of compromise. A multisig or the
  program's upgrade authority moving to a multisig is the next step; the current
  deployment keeps the upgrade authority with the deployer for the hackathon.

## Licence

MIT. See `LICENSE`.
