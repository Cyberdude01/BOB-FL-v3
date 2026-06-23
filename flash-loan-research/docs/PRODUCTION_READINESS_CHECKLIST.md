# Production Readiness Checklist

BOB-FL must remain in read-only/dry-run mode until this checklist is satisfied.

## Phase 1: Arbitrum + Base Development

- [ ] `.env.local` created from `.env.example`
- [ ] `EXECUTION_ENABLED=false`
- [ ] `REAL_TRANSACTIONS_ENABLED=false`
- [ ] `python scripts/check_dev_setup.py` passes
- [ ] Wallet has tiny ETH gas balance on Arbitrum
- [ ] Wallet has tiny ETH gas balance on Base
- [ ] Public RPC connectivity works on Arbitrum
- [ ] Public RPC connectivity works on Base
- [ ] Protocol addresses verified against official docs and block explorers
- [ ] Aerodrome Base pool factory and any additional Base addresses verified
- [ ] Opportunity detector network list updated to Arbitrum + Base
- [ ] Dashboard starts locally
- [ ] Telegram alert path tested
- [ ] Circuit breaker state/status verified

## Phase 2: Dry Run / Simulation

- [ ] Simulated opportunities can be detected on Arbitrum + Base
- [ ] Simulated execution produces expected bundles/plans
- [ ] Profit calculation includes gas, slippage, flash loan fees, and failure risk
- [ ] Min profit threshold defined per network
- [ ] Gas spike alerts trigger correctly
- [ ] Provider throttling alerts trigger correctly
- [ ] Consecutive failure circuit breaker trips correctly
- [ ] Daily loss threshold gate works
- [ ] Logs contain no secrets

## Phase 3: Tiny Real Pilot

Requires explicit human approval before enabling real transactions.

- [ ] Hot wallet capped to `$50-$100`
- [ ] Real execution enabled only for Arbitrum + Base
- [ ] Max per-transaction exposure set to `$50` or lower
- [ ] Manual approval required above `$10`
- [ ] First transaction is a minimal-value test transaction
- [ ] Transaction success/failure alert confirmed
- [ ] Revert/error handling confirmed
- [ ] Emergency stop tested
- [ ] Post-trade reconciliation working

## Phase 4: Scale Toward Production

- [ ] Paid RPC provider selected
- [ ] Backup RPC provider configured
- [ ] RPC failover tested
- [ ] Flashbots/signed request path implemented and tested where applicable
- [ ] Eden feasibility reviewed before inclusion
- [ ] Safe/multisig treasury created
- [ ] Hot wallet refill policy documented
- [ ] Compliance/tax logging requirements reviewed
- [ ] Independent security review completed
- [ ] Runbook created for downtime/incident response

## Do Not Proceed If

- Any private key or seed phrase has appeared in chat, Git, logs, or screenshots
- Any protocol address is unverified
- Any script can submit real transactions while `REAL_TRANSACTIONS_ENABLED=false`
- Circuit breaker cannot block execution
- Alerts are not working
- Profit math ignores gas or slippage
- Wallet balance exceeds the configured hot-wallet cap
