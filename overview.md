Sigil: Agent Briefing (Full Project Overview)
Working brief for the coding agent. Version 1, 23 November 2026. This is the source of truth for what Sigil is, what is decided, and what is still open.
0. How to use this document
• DECIDED means the owner (Perpetual) decided it. Do not change it without asking.
• RECOMMENDED means it is a proposal that fits the decisions. Follow it unless told otherwise.
• OPEN means ask Perpetual before deciding.
• If this brief conflicts with the shorter "Product Authenticity Layer: Project Scope" document, this brief wins. Known differences are listed in section 15.
1. One-paragraph summary
Sigil is an open-source, industry-agnostic product-record layer built on Solana. A verified producer registers a batch of products. Sigil stores a tamper-evident commitment to that batch on-chain (who made it, what it is, when it expires) and generates one QR code per unit. A shopper scans the QR with an ordinary phone camera, before paying, with no app, wallet or account, and sees what the product is registered as, whether it is expired or recalled, and whether the code is being scanned in unusual ways. Sigil never claims a pack is "genuine". It says what the code is registered to and asks the shopper to compare that with the pack in their hand.
2. Context
Owner and working style. Perpetual is a backend engineer who mainly works in FastAPI and is a final-year student. Assume Solana, Rust and Anchor are newer territory, so prefer simple, well-documented patterns and explain choices briefly. Perpetual communicates casually and directly, and has said plainly that jargon is unwelcome. Explain things in simple words. Do not pile on options.
Event. The Dev3pack hackathon, Solana only. The deadline and judging criteria are not yet known (see section 20).
Problem. Fake medicine and fake cosmetics look real and can hurt people. Honest producers lose trust.
Landscape (so the agent does not reinvent or misposition):
• Nigeria's regulator NAFDAC has run scratch-code SMS authentication since about 2010, through commercial providers. It is single-use and checked after purchase.
• Veritag already combines NFC chips with Solana NFTs (wine, MVP stage). It needs special hardware.
• OriginateNavio (Cardano Foundation) anchors supply-chain events to Cardano for company operators. It is a traceability tool, not a shopper-facing check.
• Sigil's difference: open source, industry-agnostic, shopper-facing, QR-only (no special hardware), and no supply-chain tracking.
3. Decisions (DECIDED)
1.  Name: Sigil.
2.  Solana only. Industry-agnostic, not chain-agnostic. Keep a clean boundary between chain code and everything else, but do not build multi-chain adapters.
3.  Verify before paying, always. A shopper must be able to check a product before buying it, repeatedly, without consuming anything.
4.  QR-based. The QR points to a product record whose commitment is on the blockchain.
5.  No NFC in the MVP.
6.  Authenticity and product status only. No supply-chain or custody tracking.
7.  Product details include expiry. After the expiry date the scan shows Expired.
8.  Producers choose an industry at registration, and each industry has its own required fields (industry packs).
9.  We build the layer (the engine and its API) plus thin demo apps on top of it (producer dashboard, shopper page, admin page). The code is open source on GitHub.
10.  Target uses: medicine, cosmetics, perishable food and drink, precious materials.
4. Rejected or changed ideas (do not reintroduce without asking)
• Burn-on-first-scan scratch codes. Rejected. A browsing shopper would use up the code and the next genuine buyer would see a false "already used".
• Hiding the code behind a destructible seal. Rejected. People need product information without buying.
• Raw scan count as proof of counterfeiting. Rejected. Scans are only soft hints (section 10).
• NFC chips. Rejected for now. Possible later premium tier only.
• Supply-chain tracking. Out of scope.
• Seller bonds and slashing. Deferred. They need custody information we do not collect.
• The proportional-election (Phragmen) idea. A separate saved idea. It is not part of Sigil.
5. What Sigil does
5.1 Producer flow
1.  The producer connects a Solana wallet in the dashboard and submits a company profile (name, regulator numbers, documents). This creates an issuer record with status Pending.
2.  An admin reviews the documents and marks the issuer Verified.
3.  The verified producer creates a batch. They choose an industry, fill in the required fields, set the expiry date and number of units, and upload a photo.
4.  The system generates unique serials, builds a Merkle tree, and shows the producer the batch summary. The producer signs one transaction in their wallet to commit it on-chain.
5.  The producer downloads printable QR labels (one per unit) and prints them on the packaging.
6.  If needed, the producer can later mark the batch Recalled. This is one-way.
5.2 Shopper flow
1.  The shopper scans the QR with the phone's normal camera. A web page opens. No app, wallet or login.
2.  The page shows the verdict, product name, photo, producer, batch number, expiry date, and a "compare with your pack" checklist.
3.  Scanning never uses anything up. Any number of people may scan any number of times.
5.3 Verdicts
Use exactly these, in this order of precedence:
1.  UNKNOWN (red): malformed link, unknown batch, or serial not in the batch's Merkle tree. Copy: "This code is not registered. Do not trust this product."
2.  ISSUER_SUSPENDED (red): the producer's verification was withdrawn.
3.  RECALLED (red): the batch was recalled.
4.  EXPIRED (red): current time is later than the stored expiry.
5.  UNUSUAL_ACTIVITY (amber): the code is registered and in date, but scan patterns look odd. Copy must say this can be normal and must not say "fake".
6.  REGISTERED (green): registered and in date.
Show a Verified producer or Unverified producer label on every result.
Copy rules (important):
• Never use the words "genuine", "authentic", "safe" or "original" as a claim about the physical pack.
• Always show: "This code is registered to [product name], batch [batch number], expiry [date]. Check that this matches the pack in your hand."
• Do not rely on colour alone. Pair every colour with an icon and a text label.
6. Architecture
There are four layers:
1.  Solana program (Rust, Anchor). Holds issuers, batches, expiry and recall status. It enforces who may do what.
2.  API server (Python, FastAPI). Generates serials and Merkle trees, stores product details and scan events, reads on-chain state, and answers shopper checks.
3.  Web app (React). Three areas: shopper page (no wallet code), producer dashboard (wallet connect), admin page (wallet connect).
4.  Industry packs (JSON). Field lists and copy for each industry.
Key data-flow facts:
• The chain holds only small commitments. Product details live off-chain, and the chain stores their hash.
• Scan events are off-chain (database), not on-chain. This avoids fees and hot-account limits.
• Shoppers never sign or send a transaction in the MVP. The server only reads the chain.
• All on-chain writes come from wallets: the producer (create batch, recall) and the admin (verify or suspend issuers).
• The Merkle root is committed on-chain, so the server cannot invent new valid serials for a batch after the fact.
7. On-chain program spec (Anchor)
Accounts
• Registry (singleton PDA, seed registry): admin pubkey, issuer_count u32, bump.
• Issuer (PDA, seeds issuer + authority pubkey): authority pubkey, name_hash [u8;32] (hash of the off-chain company profile), status (Pending=0, Verified=1, Suspended=2), created_at i64, verified_at i64, bump.
• Batch (PDA, seeds batch + issuer PDA + nonce u64 little-endian): issuer pubkey, nonce u64, industry u8, merkle_root [u8;32], details_hash [u8;32], units u32, manufactured_at i64, expires_at i64 (0 means none), status (Active=0, Recalled=1), recalled_at i64, recall_reason u8, created_at i64, bump.
Instructions
• initialize_registry(admin): one time.
• register_issuer(name_hash): signed by the producer wallet; creates an Issuer as Pending.
• set_issuer_status(new_status): signed by registry.admin only. Allowed moves: Pending to Verified, Verified to Suspended, Suspended to Verified.
• create_batch(nonce, industry, merkle_root, details_hash, units, manufactured_at, expires_at): signed by the issuer authority. Requires the issuer to be Verified, units greater than 0, and expires_at either 0 or in the future and after manufactured_at.
• recall_batch(reason): signed by the issuer authority. Only Active to Recalled. Never reversible.
Hard rules
• No instruction may change merkle_root, details_hash, units or expires_at after creation. Nobody, including the admin, can edit a batch.
• Use Clock for timestamps, checked arithmetic everywhere, Anchor has_one and seed constraints for authority checks.
• Emit events: IssuerRegistered, IssuerStatusChanged, BatchCreated, BatchRecalled.
• Custom errors: Unauthorized, IssuerNotVerified, InvalidUnits, InvalidExpiry, BatchAlreadyRecalled, InvalidStatusTransition.
• Deploy to devnet for the hackathon. The upgrade authority stays with the deployer for now. Document the plan to move it to a multisig or make the program immutable.
8. Identifiers and cryptography
• Serial: 10 random bytes (80 bits) from a cryptographically secure source, shown as 16 base32 characters. Serials are public, not secret. The randomness stops anyone from guessing a registered serial.
• Leaf: SHA-256 of the prefix sigil:leaf:v1, then the batch PDA bytes, then the serial bytes.
• Tree: binary Merkle tree over leaves in insertion order, SHA-256, with a distinct prefix for inner nodes (sigil:node:v1) to prevent second-preimage tricks. Duplicate the last node on odd levels.
• Details hash: SHA-256 of canonical JSON (sorted keys, no extra whitespace, UTF-8) of the product details. Anyone can recompute it to check the details were not altered.
• Verification is not done on-chain. The server checks the Merkle proof against the on-chain root. The response may include the proof so a client can verify independently.
• Write unit tests with fixed test vectors for the leaf, node and tree functions.
9. API (FastAPI)
Public
• GET /api/v1/verify/{batch_code}/{serial}: returns verdict, reason, product details, issuer info (with verified label), batch number, expiry, and optionally the Merkle proof. Logs a scan event.
• POST /api/v1/reports (stretch): shopper reports a suspected fake with a note and optional photo.
Producer (login by wallet signature, Sign-In With Solana style, then a short-lived token)
• POST /api/v1/auth/nonce and POST /api/v1/auth/verify.
• POST /api/v1/issuers: submit the company profile.
• POST /api/v1/batches/prepare: validates the details against the industry pack, generates serials, builds the tree, saves everything as a draft, and returns the values the wallet needs to sign create_batch.
• POST /api/v1/batches/{id}/confirm: given the transaction signature, reads the chain, checks the batch account matches the draft, and marks the batch Active.
• GET /api/v1/batches/{id}/labels: printable QR sheet (PDF) and per-unit PNG/SVG, only after confirmation.
• POST /api/v1/batches/{id}/recall/prepare: returns what the wallet signs for recall_batch.
• GET /api/v1/batches/{id}/activity: scan statistics and flagged codes.
Admin
• GET /api/v1/admin/issuers?status=pending, and the wallet signs set_issuer_status in the admin page.
Verify algorithm
1.  Look up the batch by the public batch_code in the database. If missing, return UNKNOWN.
2.  Read the Batch and Issuer accounts from the chain (cache with a short time-to-live of about 15 to 30 seconds, so recalls show up quickly).
3.  Rebuild or fetch the Merkle proof for the serial and check it against merkle_root. If it fails, return UNKNOWN.
4.  Apply the precedence in section 5.3.
5.  Record a scan event and return the result.
Database tables
• issuers, batches (including details_json, details_hash, merkle_root, onchain_pubkey, public_code, status), serials (batch_id, serial, leaf_index), scan_events, reports (stretch).
• MVP batch size cap: 100,000 units. SQLite is fine for local work, Postgres for deployment.
Python and Solana tooling. Use solders and solana-py for reading accounts. For decoding accounts and instructions, AnchorPy may lag behind the Anchor version, so pin versions on day one and test early. If it causes friction, decode the (simple) account layouts manually with Borsh, or isolate chain reads in one small module so it can be swapped.
10. Scan-activity hints
These are soft signals. They are never proof, and they must never say "fake".
Stored per scan: serial, batch, timestamp, coarse region and country, a device hash (an HMAC of IP and user agent using a server secret, truncated), and the verdict returned. Do not store raw IP addresses or precise location.
Rules (all thresholds configurable):
• Impossible travel: two scans of one serial from places more than about 300 km apart within about 1 hour.
• Many places: scans from 3 or more distinct regions within 7 days.
• Batch-level alert: if more than a set share of a batch's scanned serials are flagged, alert the producer. This is the strongest signal because mass copying produces many flags at once.
Why hints and not proof: honest shoppers browse and rescan, and phone location is coarse and spoofable. A single scan or a high scan count alone means nothing.
Amber copy example: "This code has been scanned in several places recently. This can be normal. Check your pack carefully."
Delete scan events after a fixed retention period (default 90 days).
11. Industry packs
Packs are JSON files in /packs. Each has: id, display name, industry_code (u8), expiry_required (bool), a list of fields (key, label, type, required), and short consumer copy for the "compare with your pack" checklist.
Industry codes: 0 = generic, 1 = medicine, 2 = cosmetics, 3 = food and drink, 4 = precious materials, 5 to 15 reserved.
• Medicine: product name, manufacturer, regulator registration number, batch number, manufacture date, expiry date, photo. Expiry required.
• Cosmetics: brand, product name, batch number, expiry or use-by date, photo.
• Food and drink: product name, batch number, production date, expiry date, photo. Expiry required.
• Precious materials: item type, weight, purity, certificate reference, photo. No expiry.
The API validates details against the pack before preparing a batch. The chain stores only the industry code and the details hash. Adding an industry must need only a new JSON file, no code change. This is a core claim of the project and must be demonstrable.
12. Frontend (React)
• RECOMMENDED: Next.js with Tailwind. Wallet code only on producer and admin routes, so the shopper page stays small and fast.
• Shopper page (/v/<batch_code>/<serial>): mobile first, fast on slow networks, no wallet code, large verdict with icon and text, product block, producer and verified label, the compare checklist, a link to report a suspected fake (stretch), and a short privacy note about scan logging.
• Producer dashboard: wallet connect, company profile and status, batch creation wizard, label download, activity view, recall button with a confirmation.
• Admin page: pending issuers with their documents, verify and suspend actions.
• QR and labels: QR error correction level M or Q. Print the short verify domain as plain text next to each QR, so people can notice lookalike sites. Include the short serial under the QR for manual entry.
13. Security and threat model
• Code stuck on the wrong product. The page shows the registered product, so a human can see the mismatch. Residual risk: only works if the shopper looks.
• Made-up code. Returns UNKNOWN.
• Real code copied onto a fake of the same product. Cannot be detected from the code alone. Only the hints in section 10 may help.
• Fake verify website. A fake QR could point to a lookalike site. Mitigate with the printed plain-text domain, a short memorable domain, and HTTPS with HSTS.
• Fraudulent producer. Mitigate with admin verification, an "Unverified producer" label, and suspension.
• Compromised producer wallet. An attacker could create batches or recall them. Mitigate later with multisig. Note this risk in the README.
• Dishonest or compromised server. It could return wrong answers. Mitigate with open source, on-chain commitments, the optional Merkle proof, and the details hash for independent checks.
• Admin abuse. The admin can verify a bad issuer but cannot edit any batch. All status changes emit on-chain events.
• Abuse of the verify endpoint. Rate limit per device hash, and cache chain reads.
• Serial guessing. 80-bit random serials make guessing impractical.
• Privacy. No raw IPs, no precise location, a retention limit, and no shopper accounts.
• General. Validate all inputs, sanitise uploaded images, restrict CORS, and never put secrets in the repository.
14. Honest limits (must appear in the README, the product copy and the pitch)
1.  A QR code cannot prove which physical pack it is stuck on. A real code copied onto a fake of the same product looks identical.
2.  Scan-pattern hints can miss a single copy and can false-alarm on honest behaviour.
3.  Someone outside the chain must decide who counts as a real producer. For now that is the admin, later a regulator or trade body.
4.  Physical protection (tamper-evident labels) matters and is outside the software.
5.  Sigil reduces and exposes counterfeiting. It does not end it.
The strongest honest pitch angle is live status: any shopper can check right now whether a batch is expired or recalled, and a counterfeiter gains nothing by copying a recalled product's code. Authenticity signals are a secondary benefit.
15. Known differences from the scope document
• The scope document says the server pays network fees so shoppers never need a wallet. In this MVP, shoppers send no transactions at all, so there is no relayer. Fee sponsorship only returns if a later feature needs shopper-signed actions.
• The scope document says only approved producers can register products. In code, this is enforced by create_batch requiring a Verified issuer.
• The scope document mentions "unusual activity" without defining it. Section 10 defines it.
16. Repository layout and tooling
• programs/sigil/: Anchor program and tests.
• api/: FastAPI service, database models, Merkle and canonical-JSON library, label generator.
• packs/: industry pack JSON files.
• apps/web/: shopper page, producer dashboard, admin page.
• scripts/: seed demo data, simulate scans.
• docs/ and README.md: setup, integration guide (a few API calls), threat model, honest limits.
• Tests: Anchor tests with LiteSVM or a local validator, pytest for the API and Merkle library, and a scan-simulation script for the hints.
• License: MIT or Apache-2.0. OPEN: confirm with Perpetual.
17. Suggested build order
1.  Packs, canonical JSON, serial generator and Merkle library, with test vectors.
2.  Anchor program and tests.
3.  API read path and the verify endpoint, against devnet.
4.  Batch prepare and confirm flow.
5.  Shopper page.
6.  Producer dashboard and label export.
7.  Admin page and issuer verification.
8.  Scan logging, hints and the simulation script.
9.  Seed data, demo polish, README.
Build a thin vertical slice early (one batch, one scan, one verdict end to end), then widen.
18. Demo script and acceptance criteria
Demo
1.  Approve a producer in the admin page.
2.  Register a medicine batch with a future expiry and print a QR.
3.  Scan it: REGISTERED.
4.  Show the same QR on a different product: the mismatch is obvious on screen.
5.  Register a batch with a past expiry: EXPIRED.
6.  Recall a batch: RECALLED.
7.  Run the simulation: many far-apart scans of one code produce UNUSUAL_ACTIVITY and a producer alert.
8.  Register a cosmetics batch by adding only a pack file: the same engine, no code changes.
Done means
• A shopper can check a product with a plain phone camera and no wallet.
• No instruction can change expiry, root or details after a batch is created, and tests prove it.
• Two or more industries run with zero code changes.
• An unverified issuer cannot create a batch, and tests prove it.
• A scan never consumes or changes a code.
• The README states the honest limits and shows how to integrate in a few API calls.
19. Later features (not MVP)
• "Bought" and "finished" marking. A one-way order: registered, bought, finished. Marking must need a secret only a buyer has (for example a hidden code inside the pack), so strangers cannot mark shelves of products. It exposes refilled-bottle fraud. Messages must say "bought on [date], be careful if buying from a shop", never "fake".
• Community reports with photos and a producer map.
• An optional unclonable-tag tier for high-value goods.
• Regulator co-signing for issuer verification and recalls.
• SMS or USSD checks for people without data.
• Seller bonds, if custody information ever exists.
• More languages, and fee sponsorship if shopper-signed actions appear.
20. Open questions (ask Perpetual)
• What are the hackathon deadline, tracks and judging criteria?
• Should producers sign with their own wallet (RECOMMENDED here) or should the server hold keys for them?
• Which web framework: Next.js (RECOMMENDED) or Vite?
• Where will the shopper page and database be hosted, and which short domain?
• Is there a first real pilot (a pharmacy or cosmetics seller) to talk to?
• Is the name Sigil free to use (domain, GitHub, Solana ecosystem)? Check before launch.
• Which open-source licence?