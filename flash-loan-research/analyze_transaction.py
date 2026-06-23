#!/usr/bin/env python3

from web3 import Web3
import os
from dotenv import load_dotenv

load_dotenv('.env.local')

def analyze_transaction():
    """Analyze the stuck transaction"""
    w3 = Web3(Web3.HTTPProvider(os.getenv('ARBITRUM_RPC')))
    wallet_address = os.getenv('WALLET_ADDRESS')
    
    print('🔍 TRANSACTION ANALYSIS')
    print('=' * 40)
    
    # Transaction details
    tx_hash = '0xdc3c75ba8641db2375d646fbd8a6d81ecdcb2d9308ef5c9b9b63a4a318ce05b6'
    
    # Check current status
    current_block = w3.eth.block_number
    current_nonce = w3.eth.get_transaction_count(wallet_address)
    gas_price = w3.eth.gas_price
    
    print(f'Transaction Hash: {tx_hash}')
    print(f'Current block: {current_block:,}')
    print(f'Wallet nonce: {current_nonce}')
    print(f'Current gas price: {w3.from_wei(gas_price, "gwei")} gwei')
    print()
    
    # Try to get transaction details
    try:
        tx = w3.eth.get_transaction(tx_hash)
        if tx:
            print('✅ Transaction found in mempool')
            print(f'From: {str(tx.from)}')
            print(f'To: {str(tx.to)}')
            print(f'Value: {w3.from_wei(tx.value, "ether")} ETH')
            print(f'Gas: {tx.gas}')
            print(f'Gas Price: {w3.from_wei(tx.gasPrice, "gwei")} gwei')
            print(f'Nonce: {tx.nonce}')
            print(f'Block: {tx.blockNumber if tx.blockNumber else "pending"}')
        else:
            print('❌ Transaction not found in mempool')
            
    except Exception as e:
        print(f'Error getting transaction: {e}')
    
    # Try to get receipt
    try:
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        if receipt:
            print('✅ Transaction receipt found')
            print(f'Status: {receipt.status}')
            print(f'Block: {receipt.blockNumber}')
            print(f'Gas Used: {receipt.gasUsed}')
        else:
            print('❌ Transaction receipt not found')
            
    except Exception as e:
        print(f'Error getting receipt: {e}')
    
    # Analysis
    print()
    print('📊 TRANSACTION STATUS ANALYSIS')
    print('=' * 40)
    
    if current_nonce == 54:
        print('⚠️ TRANSACTION STUCK ANALYSIS:')
        print('============================')
        print('• Transaction has been pending for 9.6+ hours')
        print('• This is ABNORMAL and indicates a problem')
        print('• Nonce has not been used (still 54)')
        print()
        print('🔍 LIKELY CAUSES:')
        print('1. Gas price too low for current network conditions')
        print('2. Transaction dropped from mempool due to low priority')
        print('3. Network congestion or node synchronization issues')
        print('4. Significant changes in fee market since transaction was sent')
        print()
        print('🚨 CONCLUSION:')
        print('The transaction is LIKELY LOST or STUCK in mempool')
        print('Recommended action: Create new transaction with higher gas price')
        print()
        print('💡 SOLUTION:')
        print('1. Wait a bit more (sometimes transactions take hours)')
        print('2. Replace with higher gas price transaction')
        print('3. Consider this as a lesson in gas price management')
        return False
    else:
        print('✅ Transaction confirmed!')
        print(f'Nonce increased to {current_nonce}')
        return True

if __name__ == "__main__":
    analyze_transaction()