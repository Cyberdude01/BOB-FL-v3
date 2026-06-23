#!/usr/bin/env python3
"""
Execute Simple Real Transaction on Blockchain
Monitor wallet balance before and after
"""

import asyncio
import json
import os
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables first
load_dotenv('.env.local')

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from web3 import Web3

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('simple_real_transaction.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

async def execute_simple_real_transaction():
    """Execute a simple real transaction and monitor results"""
    logger.info("🚀 EXECUTING SIMPLE REAL TRANSACTION")
    logger.info("=" * 60)
    
    try:
        # Connect to Arbitrum
        w3 = Web3(Web3.HTTPProvider(os.getenv('ARBITRUM_RPC')))
        wallet_address = os.getenv('WALLET_ADDRESS')
        private_key = os.getenv('PRIVATE_KEY')
        
        # Step 1: Get initial balance
        logger.info("📊 Step 1: Capture Initial Balance")
        initial_balance = w3.eth.get_balance(wallet_address)
        initial_eth = w3.from_wei(initial_balance, 'ether')
        initial_usd = float(initial_eth) * 3200  # Approximate ETH/USD rate
        
        logger.info(f"💰 Initial Balance: {initial_eth} ETH (${initial_usd:,.2f})")
        
        # Step 2: Create simple transaction
        logger.info("\n🔄 Step 2: Create Simple Transaction")
        
        # Get current nonce
        nonce = w3.eth.get_transaction_count(wallet_address)
        logger.info(f"Current nonce: {nonce}")
        
        # Get gas price
        gas_price = w3.eth.gas_price
        gas_price_gwei = w3.from_wei(gas_price, 'gwei')
        logger.info(f"Gas Price: {gas_price_gwei} gwei")
        
        # Calculate safe gas limit (50% of balance)
        max_spendable = float(initial_eth) * 0.1  # Use only 10% of balance
        max_gas_limit = int(max_spendable * 1e18 / gas_price)
        safe_gas_limit = min(max_gas_limit, 21000)  # Cap at 21k for ETH transfer
        
        logger.info(f"Max spendable: {max_spendable} ETH")
        logger.info(f"Safe gas limit: {safe_gas_limit}")
        
        # Create transaction
        transaction = {
            'to': wallet_address,  # Send to self
            'value': 0,  # Send 0 ETH
            'gas': safe_gas_limit,
            'gasPrice': gas_price,
            'nonce': nonce,
            'chainId': 42161
        }
        
        # Calculate cost
        estimated_cost = transaction['gas'] * transaction['gasPrice']
        eth_cost = w3.from_wei(estimated_cost, 'ether')
        
        logger.info(f"Transaction Cost: {eth_cost} ETH")
        logger.info(f"Can afford: {float(eth_cost) < float(initial_eth)}")
        
        # Step 3: Execute transaction
        logger.info("\n⚡ Step 3: Execute Real Transaction")
        
        # Sign transaction
        signed_tx = w3.eth.account.sign_transaction(transaction, private_key)
        
        # Send transaction
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        logger.info(f"✅ Transaction sent: {tx_hash.hex()}")
        
        # Step 4: Monitor confirmation
        logger.info("\n⏳ Step 4: Monitor Transaction Confirmation")
        
        try:
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
            
            if receipt.status == 1:
                logger.info(f"✅ Transaction confirmed in block {receipt.blockNumber}")
                logger.info(f"Gas used: {receipt.gasUsed}")
                
                # Step 5: Get final balance
                logger.info("\n💰 Step 5: Capture Final Balance")
                final_balance = w3.eth.get_balance(wallet_address)
                final_eth = w3.from_wei(final_balance, 'ether')
                final_usd = float(final_eth) * 3200
                
                logger.info(f"Final Balance: {final_eth} ETH (${final_usd:,.2f})")
                
                # Calculate profit/loss
                profit_eth = final_eth - initial_eth
                profit_usd = final_usd - initial_usd
                
                logger.info(f"\n📊 TRANSACTION RESULTS:")
                logger.info(f"   Initial Balance: {initial_eth} ETH (${initial_usd:,.2f})")
                logger.info(f"   Final Balance: {final_eth} ETH (${final_usd:,.2f})")
                logger.info(f"   Change: {profit_eth} ETH (${profit_usd:,.2f})")
                logger.info(f"   Transaction Hash: {tx_hash.hex()}")
                logger.info(f"   Confirmed: ✅")
                logger.info(f"   Profitable: {'✅ YES' if profit_usd > 0 else '❌ NO'}")
                
                # Commit to markdown
                await commit_transaction_results(
                    initial_balance=initial_eth,
                    final_balance=final_eth,
                    profit_eth=profit_eth,
                    profit_usd=profit_usd,
                    tx_hash=tx_hash.hex(),
                    success=True,
                    gas_used=receipt.gasUsed
                )
                
                return profit_usd >= 0  # Consider success if no loss
                
            else:
                logger.error(f"❌ Transaction failed (status: {receipt.status})")
                
                # Get final balance anyway
                final_balance = w3.eth.get_balance(wallet_address)
                final_eth = w3.from_wei(final_balance, 'ether')
                final_usd = float(final_eth) * 3200
                
                profit_eth = final_eth - initial_eth
                profit_usd = final_usd - initial_usd
                
                await commit_transaction_results(
                    initial_balance=initial_eth,
                    final_balance=final_eth,
                    profit_eth=profit_eth,
                    profit_usd=profit_usd,
                    tx_hash=tx_hash.hex(),
                    success=False,
                    gas_used=receipt.gasUsed,
                    error=f"Transaction failed with status {receipt.status}"
                )
                
                return False
                
        except Exception as e:
            logger.error(f"❌ Transaction confirmation failed: {e}")
            
            # Get final balance anyway
            final_balance = w3.eth.get_balance(wallet_address)
            final_eth = w3.from_wei(final_balance, 'ether')
            final_usd = float(final_eth) * 3200
            
            profit_eth = final_eth - initial_eth
            profit_usd = final_usd - initial_usd
            
            await commit_transaction_results(
                initial_balance=initial_eth,
                final_balance=final_eth,
                profit_eth=profit_eth,
                profit_usd=profit_usd,
                tx_hash=tx_hash.hex(),
                success=False,
                error=f"Confirmation failed: {e}"
            )
            
            return False
            
    except Exception as e:
        logger.error(f"❌ Simple transaction execution failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def commit_transaction_results(initial_balance, final_balance, profit_eth, profit_usd, tx_hash, success, gas_used=None, error=None):
    """Commit transaction results to markdown"""
    logger.info("📝 Committing transaction results to markdown...")
    
    try:
        # Create markdown content
        markdown_content = f"""# Simple Real Transaction Execution Results

## 🎯 EXECUTION SUMMARY

**Timestamp**: {datetime.now().isoformat()}  
**Status**: {'✅ SUCCESS' if success else '❌ FAILED'}  
**Transaction Hash**: `{tx_hash}`  

## 💰 TRANSACTION RESULTS

| Metric | Value |
|--------|-------|
| **Initial Balance** | {initial_balance:.8f} ETH |
| **Final Balance** | {final_balance:.8f} ETH |
| **Change** | {profit_eth:.8f} ETH |
| **Change (USD)** | ${profit_usd:,.2f} |
| **Profitable** | {'✅ YES' if profit_usd > 0 else '❌ NO'} |

## ⚡ TRANSACTION DETAILS

- **Transaction Hash**: `{tx_hash}`
- **Success**: {'✅' if success else '❌'}
- **Gas Used**: {gas_used if gas_used else 'N/A'}
- **Profit/Loss**: {profit_eth:.8f} ETH (${profit_usd:,.2f})

## 🔍 ANALYSIS

"""
        
        if success:
            if profit_usd > 0:
                markdown_content += f"""
**✅ PROFITABLE TRANSACTION EXECUTED SUCCESSFULLY**

- **Actual Profit**: ${profit_usd:,.2f}
- **ETH Equivalent**: {profit_eth:.8f} ETH
- **Success Rate**: 100%

## 🎉 CONCLUSION

The simple real transaction was **SUCCESSFULLY EXECUTED** and **PROFITABLE**!

**Total Profit**: ${profit_usd:,.2f} USD  
**ETH Equivalent**: {profit_eth:.8f} ETH  
**Status**: TRANSACTION SUCCESSFUL  

---
"""
            else:
                markdown_content += f"""
**⚠️ TRANSACTION EXECUTED BUT NOT PROFITABLE**

- **No Profit/Loss**: ${profit_usd:,.2f}
- **Status**: Transaction successful but neutral result

## 🔧 NOTES

This was a simple test transaction (0 ETH sent to self). For profitable flash loans, 
actual arbitrage logic needs to be implemented.

---
"""
        else:
            markdown_content += f"""
**❌ TRANSACTION EXECUTION FAILED**

- **Error**: {error}
- **Status**: Transaction failed to execute

## 🔧 TROUBLESHOOTING

1. **Check wallet balance**
2. **Verify gas limits**
3. **Network connectivity**
4. **Contract addresses**

---
"""
        
        markdown_content += f"*Generated: {datetime.now().isoformat()}*\n"
        
        # Write to file
        filename = f"simple_real_transaction_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(filename, 'w') as f:
            f.write(markdown_content)
        
        logger.info(f"✅ Results committed to: {filename}")
        
    except Exception as e:
        logger.error(f"❌ Failed to commit results: {e}")

async def main():
    """Main function"""
    logger.info("🚀 SIMPLE REAL TRANSACTION EXECUTION")
    logger.info("=" * 60)
    
    # Execute simple real transaction
    success = await execute_simple_real_transaction()
    
    if success:
        logger.info("\n🎉 SIMPLE TRANSACTION EXECUTION SUCCESSFUL!")
        logger.info("✅ Real transaction executed on blockchain")
        logger.info("✅ Balance changes monitored")
        return 0
    else:
        logger.error("\n❌ SIMPLE TRANSACTION EXECUTION FAILED")
        logger.info("🔧 Check logs for details")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)