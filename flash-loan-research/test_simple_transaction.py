#!/usr/bin/env python3
"""
Simple Transaction Test Script
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# Load environment variables first
load_dotenv('.env.local')

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from web3 import Web3

async def test_simple_transaction():
    """Test a simple transaction to verify connectivity"""
    try:
        # Connect to Arbitrum
        w3 = Web3(Web3.HTTPProvider(os.getenv('ARBITRUM_RPC')))
        wallet_address = os.getenv('WALLET_ADDRESS')
        private_key = os.getenv('PRIVATE_KEY')
        
        print(f"🔍 Testing simple transaction")
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
        
        # Sign transaction
        signed_tx = w3.eth.account.sign_transaction(transaction, private_key)
        
        # Send transaction
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        print(f"Transaction Hash: {tx_hash.hex()}")
        
        # Wait for confirmation
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        print(f"Receipt Status: {receipt.status}")
        print(f"Transaction confirmed: {receipt.status == 1}")
        
        return receipt.status == 1
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_simple_transaction())
    sys.exit(0 if result else 1)