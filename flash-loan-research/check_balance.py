#!/usr/bin/env python3
"""
Check wallet balance on both networks
"""

import os
from dotenv import load_dotenv
from web3 import Web3

# Load environment variables
load_dotenv('.env.local')

def check_balance():
    """Check wallet balance"""
    wallet_address = os.getenv('WALLET_ADDRESS')
    arbitrum_rpc = os.getenv('ARBITRUM_RPC')
    base_rpc = os.getenv('BASE_RPC')
    
    print(f'🔍 Checking wallet balance for: {wallet_address}')
    print('=' * 60)
    
    # Check Arbitrum balance
    print('📊 Arbitrum Balance:')
    try:
        w3_arbitrum = Web3(Web3.HTTPProvider(arbitrum_rpc))
        balance_arbitrum = w3_arbitrum.eth.get_balance(wallet_address)
        balance_eth_arbitrum = w3_arbitrum.from_wei(balance_arbitrum, 'ether')
        balance_usd_arbitrum = balance_eth_arbitrum * 3000  # Assume $3000/ETH
        print(f'   ETH: {balance_eth_arbitrum:.6f}')
        print(f'   USD: ${balance_usd_arbitrum:.2f}')
    except Exception as e:
        print(f'   ❌ Error: {e}')
    
    print()
    
    # Check Base balance  
    print('📊 Base Balance:')
    try:
        w3_base = Web3(Web3.HTTPProvider(base_rpc))
        balance_base = w3_base.eth.get_balance(wallet_address)
        balance_eth_base = w3_base.from_wei(balance_base, 'ether')
        balance_usd_base = balance_eth_base * 3000  # Assume $3000/ETH
        print(f'   ETH: {balance_eth_base:.6f}')
        print(f'   USD: ${balance_usd_base:.2f}')
    except Exception as e:
        print(f'   ❌ Error: {e}')
    
    print()
    
    # Total balance
    total_eth = balance_eth_arbitrum + balance_eth_base
    total_usd = total_eth * 3000
    print(f'💰 Total Balance:')
    print(f'   ETH: {total_eth:.6f}')
    print(f'   USD: ${total_usd:.2f}')

if __name__ == '__main__':
    check_balance()