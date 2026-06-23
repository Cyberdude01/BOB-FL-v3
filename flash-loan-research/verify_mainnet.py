#!/usr/bin/env python3
"""
Verify mainnet execution and wallet balance
"""

from web3 import Web3
import os
from dotenv import load_dotenv

def verify_mainnet():
    # Load environment
    load_dotenv('.env.local')
    
    print('=== ARBITRUM MAINNET VERIFICATION ===')
    
    # Check Arbitrum mainnet connection
    arbitrum_rpc = os.getenv('ARBITRUM_RPC')
    w3 = Web3(Web3.HTTPProvider(arbitrum_rpc))
    
    print(f'RPC Endpoint: {arbitrum_rpc}')
    print(f'Connected: {w3.is_connected()}')
    print(f'Chain ID: {w3.eth.chain_id}')
    print(f'Block Number: {w3.eth.block_number}')
    
    # Check if it's the correct Arbitrum mainnet
    if w3.eth.chain_id == 42161:
        print('✅ CONFIRMED: Arbitrum One Mainnet')
    else:
        print(f'❌ ERROR: Expected chain ID 42161, got {w3.eth.chain_id}')
    
    # Check wallet
    wallet_address = os.getenv('WALLET_ADDRESS')
    balance = w3.eth.get_balance(wallet_address)
    eth_balance = w3.from_wei(balance, 'ether')
    
    print(f'\n=== WALLET VERIFICATION ===')
    print(f'Wallet Address: {wallet_address}')
    print(f'Wallet Balance: {eth_balance} ETH')
    
    # Check recent transactions
    try:
        latest_transactions = w3.eth.get_transactions(wallet_address)
        print(f'Recent Transactions: {len(latest_transactions)}')
        
        if latest_transactions:
            latest_tx = latest_transactions[0]
            print(f'Latest Tx Hash: {latest_tx.hex()}')
            print(f'Latest Tx Block: {latest_tx.blockNumber}')
            print(f'Latest Tx Value: {w3.from_wei(latest_tx.value, "ether")} ETH')
        else:
            print('No recent transactions found')
            
    except Exception as e:
        print(f'Transaction check error: {e}')
    
    return w3.is_connected(), eth_balance

if __name__ == "__main__":
    connected, balance = verify_mainnet()
    print(f'\n=== FINAL VERIFICATION ===')
    print(f'Mainnet Connected: {connected}')
    print(f'Wallet Balance: {balance} ETH')
    print(f'Real Trading Enabled: {os.getenv(\"REAL_TRANSACTIONS_ENABLED\") == "true"}')