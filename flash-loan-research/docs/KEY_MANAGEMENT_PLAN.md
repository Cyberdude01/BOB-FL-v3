# Key Management Plan

## Current Phase: Development / Testing

Wallet model: dedicated single hot wallet with tiny funds only.

Public execution wallet:

`0xc18EDe537AE7fD823d7A20942E11DfB067D47694`

## Hard Rules

- Never send seed phrases or private keys in Telegram, chat, GitHub, logs, or docs.
- Never commit `.env`, `.env.local`, keystores, API keys, or RPC URLs with embedded keys.
- Never use the user's main wallet for automated execution.
- Never enable real transactions until explicit human approval.
- Never use unlimited token approvals for production flows.
- Never auto-execute above the configured dev limit.

## Development Storage

For development only:

- public wallet address may be stored in config
- private key should stay outside Git and preferably outside this repo
- if CLI signing is later needed, use `.env.local` or encrypted keystore only for the tiny-funded dev wallet

`.gitignore` already excludes:

- `.env`
- `.env.local`
- `.env.*.local`
- `*.key`
- `*.pem`
- `secrets/`

## Recommended Next Step Before Any Signing

Use an encrypted keystore rather than a raw private key:

- Foundry keystore, Web3.py keystore, or similar password-protected local keystore
- password stored separately from the repo
- no raw private key in shell history

## Backup Procedure

For the dev hot wallet:

1. Record seed phrase/private key offline only.
2. Store backup in a secure offline location.
3. Confirm recovery by deriving/checking the same public address on a separate device.
4. Keep only tiny funds in this wallet.

For production:

1. Use Safe/multisig treasury.
2. Keep automated hot wallet capped and refill manually.
3. Use separate signers/devices for treasury control.
4. Create emergency withdrawal procedure.
5. Rotate execution wallet after any suspected compromise.

## Rotation Cadence

Development:

- rotate immediately after any leak or suspicious transaction
- rotate before moving from dry-run to real pilot if the key was ever exposed to unsafe tooling

Production:

- quarterly review
- immediate rotation after incident
- rotate RPC/API keys after personnel or infra changes

## Approval Policy

Current dev limits:

- max daily loss: `$50`
- max per transaction: `$50`
- max hot wallet balance: `$100`
- manual approval required above: `$10`

Any transaction moving real funds must display before approval:

- network
- contract/function/path
- tokens and amount
- estimated gas
- max loss
- expected profit
- destination addresses
- calldata summary or decoded function where available

## Incident Response

If key compromise is suspected:

1. Stop the bot.
2. Disable `REAL_TRANSACTIONS_ENABLED`.
3. Move remaining funds to a new wallet using a trusted wallet UI.
4. Rotate all related keys.
5. Review Git history/logs for leaks.
6. Re-enable only after root cause is fixed.
