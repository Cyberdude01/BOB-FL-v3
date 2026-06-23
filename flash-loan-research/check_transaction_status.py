#!/usr/bin/env python3

from web3 import Web3
import os
from dotenv import load_dotenv

load_dotenv('.env.local')

def check_transaction_status():
    """Check the status of the stuck transaction"""
    w3 = Web3(Web3.HTTPProvider(os.getenv('ARBITRUM_RPC')))
    wallet_address = os.getenv('WALLET_ADDRESS')
    
    print('🔍 TRANSACTION STATUS CHECK')
    print('=' * 40)
    
    # Transaction details
    tx_hash = '0xdc3c75ba8641db2375d646fbd8a6d81ecdcb2d9308ef5c9b9b63a4a318ce05b6'
    
    # Check current status
    current_block = w3.eth.block_number
    current_nonce = w3.eth.get_transaction_count(wallet_address)
    gas_price = w3.eth.gas_price
    
    print('Transaction Hash:', tx_hash)
    print('Current block:', current_block)
    print('Wallet nonce:', current_nonce)
    print('Current gas price:', w3.from_wei(gas_price, 'gwei'), 'gwei')
    print()
    
    # Try to get transaction details
    try:
        tx = w3.eth.get_transaction(tx_hash)
        if tx:
            print('✅ Transaction found in mempool')
            print('From:', tx.from)
            print('To:', tx.to)
            print('Value:', w3.from_wei(tx.value, 'ether'), 'ETH')
            print('Gas:', tx.gas)
            print('Gas Price:', w3.from_wei(tx.gasPrice, 'gwei'), 'gwei')
            print('Nonce:', tx.nonce)
            print('Block:', tx.blockNumber if tx.blockNumber else 'pending')
        else:
            print('❌ Transaction not found in mempool')
            
    except Exception as e:
        print('Error getting transaction:', e)
    
    # Try to get receipt
    try:
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        if receipt:
            print('✅ Transaction receipt found')
            print('Status:', receipt.status)
            print('Block:', receipt.blockNumber)
            print('Gas Used:', receipt.gasUsed)
        else:
            print('❌ Transaction receipt not found')
            
    except Exception as e:
        print('Error getting receipt:', e)
    
    print()
    print('📊 ANALYSIS')
    print('=' * 40)
    
    if current_nonce == 54:
        print('⚠️ TRANSACTION STUCK FOR 9.6+ HOURS')
        print('====================================')
        print('This is ABNORMAL behavior')
        print('Transaction is likely LOST or STUCK in mempool')
        print()
        print('POSSIBLE CAUSES:')
        print('1. Gas price too low for current network conditions')
        print('2. Transaction dropped from mempool due to low priority')
        print('3. Network congestion or node issues')
        print('4. Fee market changed significantly since transaction was sent')
        print()
        print('RECOMMENDATION:')
        print('Create a new transaction with higher gas price')
        print('This transaction should be considered lost')
        return False
    else:
        print('✅ Transaction confirmed!')
        print('Nonce has increased to', current_nonce)
        return True

if __name__ == "__main__":
    check_transaction_status()