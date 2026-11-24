use anchor_lang::prelude::*;

declare_id!("A1JYKRSENgPY1Zqa9GjT41m4LuyqMv9dgqeNQ6bSh6HF");

pub const REGISTRY_SEED: &[u8] = b"registry";
pub const ISSUER_SEED: &[u8] = b"issuer";
pub const BATCH_SEED: &[u8] = b"batch";

pub const STATUS_PENDING: u8 = 0;
pub const STATUS_VERIFIED: u8 = 1;
pub const STATUS_SUSPENDED: u8 = 2;

pub const BATCH_ACTIVE: u8 = 0;
pub const BATCH_RECALLED: u8 = 1;

#[program]
pub mod sigil {
    use super::*;

    /// One-time setup. The caller becomes the registry admin.
    pub fn initialize_registry(ctx: Context<InitializeRegistry>) -> Result<()> {
        let registry = &mut ctx.accounts.registry;
        registry.admin = ctx.accounts.admin.key();
        registry.issuer_count = 0;
        registry.bump = ctx.bumps.registry;
        Ok(())
    }

    /// A producer wallet creates its own issuer record, starting as Pending.
    pub fn register_issuer(ctx: Context<RegisterIssuer>, name_hash: [u8; 32]) -> Result<()> {
        let issuer = &mut ctx.accounts.issuer;
        issuer.authority = ctx.accounts.authority.key();
        issuer.name_hash = name_hash;
        issuer.status = STATUS_PENDING;
        issuer.created_at = Clock::get()?.unix_timestamp;
        issuer.verified_at = 0;
        issuer.bump = ctx.bumps.issuer;

        let registry = &mut ctx.accounts.registry;
        registry.issuer_count = registry
            .issuer_count
            .checked_add(1)
            .ok_or(ErrorCode::MathOverflow)?;

        emit!(IssuerRegistered {
            issuer: issuer.key(),
            authority: issuer.authority,
            name_hash,
        });
        Ok(())
    }

    /// Admin only. Pending -> Verified, Verified -> Suspended, Suspended -> Verified.
    pub fn set_issuer_status(ctx: Context<SetIssuerStatus>, new_status: u8) -> Result<()> {
        let issuer = &mut ctx.accounts.issuer;
        let old_status = issuer.status;
        let allowed = matches!(
            (old_status, new_status),
            (STATUS_PENDING, STATUS_VERIFIED)
                | (STATUS_VERIFIED, STATUS_SUSPENDED)
                | (STATUS_SUSPENDED, STATUS_VERIFIED)
        );
        require!(allowed, ErrorCode::InvalidStatusTransition);

        issuer.status = new_status;
        if new_status == STATUS_VERIFIED {
            issuer.verified_at = Clock::get()?.unix_timestamp;
        }

        emit!(IssuerStatusChanged {
            issuer: issuer.key(),
            old_status,
            new_status,
        });
        Ok(())
    }

    /// Current admin hands the registry to another wallet. The program upgrade
    /// authority is unchanged; this only moves the operational admin role.
    pub fn set_registry_admin(ctx: Context<SetRegistryAdmin>, new_admin: Pubkey) -> Result<()> {
        let registry = &mut ctx.accounts.registry;
        let old_admin = registry.admin;
        registry.admin = new_admin;

        emit!(RegistryAdminChanged {
            registry: registry.key(),
            old_admin,
            new_admin,
        });
        Ok(())
    }

    /// The producer commits a batch. Only immutable fields are written here.
    pub fn create_batch(
        ctx: Context<CreateBatch>,
        nonce: u64,
        industry: u8,
        merkle_root: [u8; 32],
        details_hash: [u8; 32],
        units: u32,
        manufactured_at: i64,
        expires_at: i64,
    ) -> Result<()> {
        require!(
            ctx.accounts.issuer.status == STATUS_VERIFIED,
            ErrorCode::IssuerNotVerified
        );
        require!(units > 0, ErrorCode::InvalidUnits);

        let now = Clock::get()?.unix_timestamp;
        if expires_at != 0 {
            require!(
                expires_at > manufactured_at && expires_at > now,
                ErrorCode::InvalidExpiry
            );
        }

        let batch = &mut ctx.accounts.batch;
        batch.issuer = ctx.accounts.issuer.key();
        batch.nonce = nonce;
        batch.industry = industry;
        batch.merkle_root = merkle_root;
        batch.details_hash = details_hash;
        batch.units = units;
        batch.manufactured_at = manufactured_at;
        batch.expires_at = expires_at;
        batch.status = BATCH_ACTIVE;
        batch.recalled_at = 0;
        batch.recall_reason = 0;
        batch.created_at = now;
        batch.bump = ctx.bumps.batch;

        emit!(BatchCreated {
            batch: batch.key(),
            issuer: batch.issuer,
            nonce,
            industry,
            merkle_root,
            units,
            expires_at,
        });
        Ok(())
    }

    /// One-way. Nothing else on a batch can ever change.
    pub fn recall_batch(ctx: Context<RecallBatch>, reason: u8) -> Result<()> {
        let batch = &mut ctx.accounts.batch;
        require!(batch.status == BATCH_ACTIVE, ErrorCode::BatchAlreadyRecalled);

        batch.status = BATCH_RECALLED;
        batch.recalled_at = Clock::get()?.unix_timestamp;
        batch.recall_reason = reason;

        emit!(BatchRecalled {
            batch: batch.key(),
            issuer: batch.issuer,
            reason,
            recalled_at: batch.recalled_at,
        });
        Ok(())
    }
}

#[account]
pub struct Registry {
    pub admin: Pubkey,
    pub issuer_count: u32,
    pub bump: u8,
}

impl Registry {
    pub const LEN: usize = 32 + 4 + 1;
}

#[account]
pub struct Issuer {
    pub authority: Pubkey,
    pub name_hash: [u8; 32],
    pub status: u8,
    pub created_at: i64,
    pub verified_at: i64,
    pub bump: u8,
}

impl Issuer {
    pub const LEN: usize = 32 + 32 + 1 + 8 + 8 + 1;
}

#[account]
pub struct Batch {
    pub issuer: Pubkey,
    pub nonce: u64,
    pub industry: u8,
    pub merkle_root: [u8; 32],
    pub details_hash: [u8; 32],
    pub units: u32,
    pub manufactured_at: i64,
    pub expires_at: i64,
    pub status: u8,
    pub recalled_at: i64,
    pub recall_reason: u8,
    pub created_at: i64,
    pub bump: u8,
}

impl Batch {
    pub const LEN: usize = 32 + 8 + 1 + 32 + 32 + 4 + 8 + 8 + 1 + 8 + 1 + 8 + 1;
}

#[derive(Accounts)]
pub struct InitializeRegistry<'info> {
    #[account(
        init,
        payer = admin,
        space = 8 + Registry::LEN,
        seeds = [REGISTRY_SEED],
        bump
    )]
    pub registry: Account<'info, Registry>,
    #[account(mut)]
    pub admin: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct RegisterIssuer<'info> {
    #[account(mut, seeds = [REGISTRY_SEED], bump = registry.bump)]
    pub registry: Account<'info, Registry>,
    #[account(mut)]
    pub authority: Signer<'info>,
    #[account(
        init,
        payer = authority,
        space = 8 + Issuer::LEN,
        seeds = [ISSUER_SEED, authority.key().as_ref()],
        bump
    )]
    pub issuer: Account<'info, Issuer>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct SetIssuerStatus<'info> {
    #[account(has_one = admin)]
    pub registry: Account<'info, Registry>,
    pub admin: Signer<'info>,
    #[account(mut)]
    pub issuer: Account<'info, Issuer>,
}

#[derive(Accounts)]
pub struct SetRegistryAdmin<'info> {
    #[account(mut, has_one = admin)]
    pub registry: Account<'info, Registry>,
    pub admin: Signer<'info>,
}

#[derive(Accounts)]
#[instruction(nonce: u64)]
pub struct CreateBatch<'info> {
    #[account(has_one = authority)]
    pub issuer: Account<'info, Issuer>,
    #[account(mut)]
    pub authority: Signer<'info>,
    #[account(
        init,
        payer = authority,
        space = 8 + Batch::LEN,
        seeds = [BATCH_SEED, issuer.key().as_ref(), &nonce.to_le_bytes()],
        bump
    )]
    pub batch: Account<'info, Batch>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct RecallBatch<'info> {
    #[account(has_one = authority)]
    pub issuer: Account<'info, Issuer>,
    pub authority: Signer<'info>,
    #[account(mut, has_one = issuer)]
    pub batch: Account<'info, Batch>,
}

#[event]
pub struct IssuerRegistered {
    pub issuer: Pubkey,
    pub authority: Pubkey,
    pub name_hash: [u8; 32],
}

#[event]
pub struct IssuerStatusChanged {
    pub issuer: Pubkey,
    pub old_status: u8,
    pub new_status: u8,
}

#[event]
pub struct RegistryAdminChanged {
    pub registry: Pubkey,
    pub old_admin: Pubkey,
    pub new_admin: Pubkey,
}

#[event]
pub struct BatchCreated {
    pub batch: Pubkey,
    pub issuer: Pubkey,
    pub nonce: u64,
    pub industry: u8,
    pub merkle_root: [u8; 32],
    pub units: u32,
    pub expires_at: i64,
}

#[event]
pub struct BatchRecalled {
    pub batch: Pubkey,
    pub issuer: Pubkey,
    pub reason: u8,
    pub recalled_at: i64,
}

#[error_code]
pub enum ErrorCode {
    #[msg("You are not allowed to do this")]
    Unauthorized,
    #[msg("The issuer is not verified")]
    IssuerNotVerified,
    #[msg("A batch must have at least one unit")]
    InvalidUnits,
    #[msg("The expiry date must be after manufacture and in the future")]
    InvalidExpiry,
    #[msg("This batch was already recalled")]
    BatchAlreadyRecalled,
    #[msg("That status change is not allowed")]
    InvalidStatusTransition,
    #[msg("Arithmetic overflow")]
    MathOverflow,
}
