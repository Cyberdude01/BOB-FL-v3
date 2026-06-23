#!/usr/bin/env python3
"""
Simple Transaction Send Test Script (no wait for confirmation)
"""

import os
import sys
from dotenv import load_dotenv
from web3 import Web3

# Load environment variables first
load_dotenv('.env.local')

def test_send_transaction():
    """Test sending a transaction without waiting for confirmation"""
    try:
        # Connect to Arbitrum
        w3 = Web3(Web3.HTTPProvider(os.getenv('ARBITRUM_RPC')))
        wallet_address = os.getenv('WALLET_ADDRESS')
        private_key = os.getenv('PRIVATE_KEY')
        
        print(f"🔍 Testing transaction send")
        print(f"Wallet: {wallet_address}")
        
        # Check balance
        balance = w3.eth.get_balance(wallet_address)
        eth_balance = w3.from_wei(balance, 'ether')
        print(f"Balance: {eth_balance} ETH")
        
        # Get current gas price
        gas_price = w3.eth.gas_price
        print(f"Gas Price: {w3.from_wei(gas_price, 'gwei')} gwei")
        
        # Create a simple transaction (send 0 ETH to ourselves)
        nonce = w3.eth.get_transaction_count(wallet_address)
        
        transaction = {
            'to': wallet_address,
            'value': 0,  # Send 0 ETH
            'gas': 50000,  # Higher gas limit for Arbitrum
            'gasPrice': gas_price,
            'nonce': nonce,
            'chainId': 42161  # Arbitrum chain ID
        }
        
        print(f"Creating transaction...")
        print(f"Nonce: {nonce}")
        print(f"Gas Limit: {transaction['gas']}")
        print(f"Gas Price: {w3.from_wei(transaction['gasPrice'], 'gwei')} gwei")
        
        # Sign transaction
        signed_tx = w3.eth.account.sign_transaction(transaction, private_key)
        
        # Send transaction (don't wait for confirmation)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        print(f"Transaction Hash: {tx_hash.hex()}")
        print("✅ Transaction sent successfully!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = test_send_transaction()
    sys.exit(0 if result else 1)