# SWOS420 Base Mainnet Launch Checklist 🚀

## Pre-Deploy

- [ ] **Audit**: All 4 contracts reviewed (SWOSPlayerNFT, SENSIToken, TransferMarket, LeagueManager)
- [ ] **Testnet Verification**: Full deploy + integration test on Base Sepolia
  ```bash
  forge script script/Deploy.s.sol:DeploySWOS420 \
    --rpc-url base_sepolia --broadcast --verify
  ```
- [ ] **Gas Estimation**: Run deploy simulation with `--estimate-gas`
- [ ] **Treasury Wallet**: Multisig deployed (Safe/Gnosis) on Base mainnet
- [ ] **Oracle Wallet**: Dedicated hot wallet for matchday oracle updates
- [ ] **Private Key Security**: Deployer key in hardware wallet, not in `.env`
- [ ] **Environment Variables**: All `NEXT_PUBLIC_*` addresses prepared

## Deploy

- [ ] **Step 1 — Deploy Contracts**:
  ```bash
  forge script script/Deploy.s.sol:DeploySWOS420 \
    --rpc-url base_mainnet \
    --broadcast \
    --verify \
    --etherscan-api-key $BASESCAN_API_KEY
  ```
- [ ] **Step 2 — Record Addresses**:
  - SWOSPlayerNFT: `0x...`
  - SENSIToken: `0x...`
  - TransferMarket: `0x...`
  - LeagueManager: `0x...`
- [ ] **Step 3 — Verify Permissions**:
  - `SENSIToken.owner()` → LeagueManager ✅
  - `SWOSPlayerNFT.oracle()` → LeagueManager ✅
  - `TransferMarket.treasury()` → Treasury multisig ✅
- [ ] **Step 4 — Verify on Basescan**: All 4 contracts show green checkmark

## Post-Deploy

- [ ] **Mint Initial Roster**: Run batch mint script for Season 1 players
  ```bash
  python scripts/mint_players.py --roster data/season_25-26.json --rpc base_mainnet
  ```
- [ ] **Register Teams**: Execute `registerTeam()` for all league teams
- [ ] **Start Season**: Call `startSeason()` on LeagueManager
- [ ] **Seed Transfer Market**: Create initial listings for star players
- [ ] **Verify Oracle Pipeline**: Run one matchday settlement end-to-end
- [ ] **Test Wage Distribution**: Confirm $SENSI flows to NFT owners after matchday

## Frontend

- [ ] **Update `.env.local`**: Set all `NEXT_PUBLIC_*` addresses to mainnet
- [ ] **WalletConnect**: Get project ID from [cloud.walletconnect.com](https://cloud.walletconnect.com)
- [ ] **Switch Default Chain**: Update `providers.tsx` → `initialChain={base}` (mainnet)
- [ ] **Build & Test**:
  ```bash
  cd frontend && npm run build && npm run start
  ```
- [ ] **Deploy to Vercel**:
  ```bash
  npx vercel --prod
  ```
- [ ] **Custom Domain**: Configure domain DNS → Vercel
- [ ] **OpenGraph Preview**: Test social cards with [opengraph.dev](https://opengraph.dev)

## Marketing

- [ ] **X Thread 1**: "We put the entire transfer market on-chain" — post when market has ≥5 active listings
- [ ] **X Thread 2**: "Your NFT just scored a hat-trick" — post after first matchday with goal events
- [ ] **X Thread 3**: "The $SENSI economy burns" — post after first burn event visible on dashboard
- [ ] **15s Videos**: Record each video concept and attach to thread openers
- [ ] **Discord/Telegram**: Create community channels, post contract addresses
- [ ] **Dexscreener**: Submit $SENSI token for tracking

## Monitoring

- [ ] **Oracle Health**: Set up alerting for failed matchday settlements
- [ ] **Contract Events**: Index events via The Graph or Envio
- [ ] **Dashboard Analytics**: Add Vercel Analytics or Plausible
- [ ] **Error Tracking**: Sentry or similar for frontend errors
- [ ] **Gas Monitoring**: Track oracle gas spend per matchday

## Emergency

- [ ] **Pause Contracts**: Test `pause()` on all pausable contracts
- [ ] **Ownership Transfer**: Document 2-step ownership transfer process
- [ ] **Incident Runbook**: Create playbook for contract pause + community comms
