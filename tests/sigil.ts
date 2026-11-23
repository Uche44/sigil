import * as anchor from "@coral-xyz/anchor";
import { Program } from "@coral-xyz/anchor";
import { Sigil } from "../target/types/sigil";
import { Keypair, PublicKey, SystemProgram } from "@solana/web3.js";
import { assert } from "chai";
import BN from "bn.js";

const STATUS_PENDING = 0;
const STATUS_VERIFIED = 1;
const STATUS_SUSPENDED = 2;

const REGISTRY_SEED = Buffer.from("registry");
const ISSUER_SEED = Buffer.from("issuer");
const BATCH_SEED = Buffer.from("batch");

function u64le(value: number): Buffer {
  const buf = Buffer.alloc(8);
  buf.writeBigUInt64LE(BigInt(value));
  return buf;
}

describe("sigil", () => {
  const provider = anchor.AnchorProvider.env();
  anchor.setProvider(provider);
  const program = anchor.workspace.Sigil as Program<Sigil>;
  const admin = (provider.wallet as anchor.Wallet).payer;

  const registryPda = PublicKey.findProgramAddressSync(
    [REGISTRY_SEED],
    program.programId
  )[0];

  function issuerPda(authority: PublicKey): PublicKey {
    return PublicKey.findProgramAddressSync(
      [ISSUER_SEED, authority.toBuffer()],
      program.programId
    )[0];
  }

  function batchPda(issuer: PublicKey, nonce: number): PublicKey {
    return PublicKey.findProgramAddressSync(
      [BATCH_SEED, issuer.toBuffer(), u64le(nonce)],
      program.programId
    )[0];
  }

  async function airdrop(key: PublicKey): Promise<void> {
    const sig = await provider.connection.requestAirdrop(
      key,
      2 * anchor.web3.LAMPORTS_PER_SOL
    );
    await provider.connection.confirmTransaction(sig, "confirmed");
  }

  async function registerIssuer(authority: Keypair): Promise<PublicKey> {
    const issuer = issuerPda(authority.publicKey);
    await program.methods
      .registerIssuer(Array.from(Buffer.alloc(32, 7)))
      .accounts({
        registry: registryPda,
        authority: authority.publicKey,
        issuer,
        systemProgram: SystemProgram.programId,
      })
      .signers([authority])
      .rpc();
    return issuer;
  }

  async function setStatus(
    issuer: PublicKey,
    status: number,
    signer: Keypair
  ): Promise<void> {
    await program.methods
      .setIssuerStatus(status)
      .accounts({ registry: registryPda, admin: signer.publicKey, issuer })
      .signers([signer])
      .rpc();
  }

  async function createBatch(
    authority: Keypair,
    issuer: PublicKey,
    nonce: number,
    opts: Partial<{
      units: number;
      manufacturedAt: number;
      expiresAt: number;
    }> = {}
  ): Promise<PublicKey> {
    const batch = batchPda(issuer, nonce);
    const now = Math.floor(Date.now() / 1000);
    await program.methods
      .createBatch(
        new BN(nonce),
        1,
        Array.from(Buffer.alloc(32, 3)),
        Array.from(Buffer.alloc(32, 4)),
        opts.units ?? 10,
        new BN(opts.manufacturedAt ?? now - 3600),
        new BN(opts.expiresAt ?? now + 86400)
      )
      .accounts({
        issuer,
        authority: authority.publicKey,
        batch,
        systemProgram: SystemProgram.programId,
      })
      .signers([authority])
      .rpc();
    return batch;
  }

  async function expectFailure(
    promise: Promise<unknown>,
    code: string
  ): Promise<void> {
    try {
      await promise;
      assert.fail(`expected failure with ${code}`);
    } catch (error) {
      const err = error as any;
      const actual =
        err?.error?.errorCode?.code ?? err?.message ?? String(error);
      assert.include(String(actual), code);
    }
  }

  it("creates the registry once", async () => {
    await program.methods
      .initializeRegistry()
      .accounts({
        registry: registryPda,
        admin: admin.publicKey,
        systemProgram: SystemProgram.programId,
      })
      .signers([admin])
      .rpc();

    const registry = await program.account.registry.fetch(registryPda);
    assert.ok(registry.admin.equals(admin.publicKey));
    assert.equal(registry.issuerCount, 0);
  });

  it("register_issuer creates a pending issuer", async () => {
    const issuer = await registerIssuer(admin);
    const account = await program.account.issuer.fetch(issuer);
    assert.equal(account.status, STATUS_PENDING);
    assert.ok(account.authority.equals(admin.publicKey));
    assert.equal(account.verifiedAt.toNumber(), 0);
  });

  it("only the admin can verify an issuer", async () => {
    const outsider = Keypair.generate();
    await airdrop(outsider.publicKey);
    const issuer = issuerPda(admin.publicKey);

    await expectFailure(
      setStatus(issuer, STATUS_VERIFIED, outsider),
      "ConstraintHasOne"
    );

    await setStatus(issuer, STATUS_VERIFIED, admin);
    const account = await program.account.issuer.fetch(issuer);
    assert.equal(account.status, STATUS_VERIFIED);
    assert.isAbove(account.verifiedAt.toNumber(), 0);
  });

  it("rejects invalid status transitions", async () => {
    const issuer = issuerPda(admin.publicKey);
    await expectFailure(
      setStatus(issuer, STATUS_PENDING, admin),
      "InvalidStatusTransition"
    );
    await expectFailure(
      setStatus(issuer, STATUS_VERIFIED, admin),
      "InvalidStatusTransition"
    );
  });

  it("an unverified issuer cannot create a batch", async () => {
    const producer = Keypair.generate();
    await airdrop(producer.publicKey);
    const issuer = await registerIssuer(producer);

    await expectFailure(
      createBatch(producer, issuer, 1),
      "IssuerNotVerified"
    );
  });

  it("a verified issuer creates a batch and every committed field is stored", async () => {
    const issuer = issuerPda(admin.publicKey);
    const batch = await createBatch(admin, issuer, 10);
    const account = await program.account.batch.fetch(batch);

    assert.ok(account.issuer.equals(issuer));
    assert.equal(account.units, 10);
    assert.equal(account.industry, 1);
    assert.equal(account.status, 0);
    assert.deepEqual(Buffer.from(account.merkleRoot), Buffer.alloc(32, 3));
    assert.deepEqual(Buffer.from(account.detailsHash), Buffer.alloc(32, 4));
    assert.equal(account.recalledAt.toNumber(), 0);
  });

  it("rejects zero units and bad expiry", async () => {
    const issuer = issuerPda(admin.publicKey);
    const now = Math.floor(Date.now() / 1000);

    await expectFailure(createBatch(admin, issuer, 20, { units: 0 }), "InvalidUnits");
    await expectFailure(
      createBatch(admin, issuer, 21, { expiresAt: now - 10 }),
      "InvalidExpiry"
    );
    await expectFailure(
      createBatch(admin, issuer, 22, {
        manufacturedAt: now - 10,
        expiresAt: now - 20,
      }),
      "InvalidExpiry"
    );
  });

  it("recall is one-way and changes nothing else", async () => {
    const issuer = issuerPda(admin.publicKey);
    const batch = await createBatch(admin, issuer, 30);
    const before = await program.account.batch.fetch(batch);

    await program.methods
      .recallBatch(1)
      .accounts({
        issuer,
        authority: admin.publicKey,
        batch,
      })
      .signers([admin])
      .rpc();

    const after = await program.account.batch.fetch(batch);
    assert.equal(after.status, 1);
    assert.isAbove(after.recalledAt.toNumber(), 0);
    assert.equal(after.recallReason, 1);

    assert.ok(after.issuer.equals(before.issuer));
    assert.equal(after.nonce.toNumber(), before.nonce.toNumber());
    assert.equal(after.industry, before.industry);
    assert.deepEqual(
      Buffer.from(after.merkleRoot),
      Buffer.from(before.merkleRoot)
    );
    assert.deepEqual(
      Buffer.from(after.detailsHash),
      Buffer.from(before.detailsHash)
    );
    assert.equal(after.units, before.units);
    assert.equal(
      after.manufacturedAt.toNumber(),
      before.manufacturedAt.toNumber()
    );
    assert.equal(after.expiresAt.toNumber(), before.expiresAt.toNumber());
    assert.equal(after.createdAt.toNumber(), before.createdAt.toNumber());
  });

  it("cannot recall twice or recall someone else's batch", async () => {
    const issuer = issuerPda(admin.publicKey);
    const batch = await createBatch(admin, issuer, 40);

    await program.methods
      .recallBatch(1)
      .accounts({ issuer, authority: admin.publicKey, batch })
      .signers([admin])
      .rpc();

    await expectFailure(
      program.methods
        .recallBatch(1)
        .accounts({ issuer, authority: admin.publicKey, batch })
        .signers([admin])
        .rpc(),
      "BatchAlreadyRecalled"
    );

    const outsider = Keypair.generate();
    await airdrop(outsider.publicKey);
    const otherBatch = await createBatch(admin, issuer, 41);

    await expectFailure(
      program.methods
        .recallBatch(1)
        .accounts({ issuer, authority: outsider.publicKey, batch: otherBatch })
        .signers([outsider])
        .rpc(),
      "ConstraintHasOne"
    );
  });
});
