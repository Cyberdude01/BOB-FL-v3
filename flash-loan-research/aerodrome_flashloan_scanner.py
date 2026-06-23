#!/usr/bin/env python3
"""Aerodrome/Base quote scanner + generic flash-loan dry-call simulator."""

import argparse, json, os, time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv
from web3 import Web3

ETH_PRICE_USD=1566.32
AAVE_PREMIUM_BPS=5
MIN_NET_PROFIT_USD=0.25
SLIPPAGE_BPS=5

AERO_ROUTER="0xcF77a3Ba9A5CA399B7c97c74d54e5b1Beb874E43"
AERO_FACTORY="0x420DD381b31aEf6683db6B902084cB0FFECe40Da"

AERO_ABI=[
 {"name":"getAmountsOut","type":"function","stateMutability":"view","inputs":[{"name":"amountIn","type":"uint256"},{"name":"routes","type":"tuple[]","components":[{"name":"from","type":"address"},{"name":"to","type":"address"},{"name":"stable","type":"bool"},{"name":"factory","type":"address"}]}],"outputs":[{"name":"amounts","type":"uint256[]"}]},
 {"name":"swapExactTokensForTokens","type":"function","stateMutability":"nonpayable","inputs":[{"name":"amountIn","type":"uint256"},{"name":"amountOutMin","type":"uint256"},{"name":"routes","type":"tuple[]","components":[{"name":"from","type":"address"},{"name":"to","type":"address"},{"name":"stable","type":"bool"},{"name":"factory","type":"address"}]},{"name":"to","type":"address"},{"name":"deadline","type":"uint256"}],"outputs":[{"name":"amounts","type":"uint256[]"}]}
]
FLASH_ABI=[{"name":"executeArb","type":"function","stateMutability":"nonpayable","inputs":[{"name":"p","type":"tuple","components":[{"name":"routerA","type":"address"},{"name":"routerB","type":"address"},{"name":"tokenBorrow","type":"address"},{"name":"tokenMid","type":"address"},{"name":"minProfit","type":"uint256"},{"name":"callDataA","type":"bytes"},{"name":"callDataB","type":"bytes"}]},{"name":"amount","type":"uint256"}],"outputs":[]}]

@dataclass
class Token:
    symbol:str; address:str; decimals:int

TOKENS={
 "USDC":Token("USDC","0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",6),
 "USDT":Token("USDT","0xfde4C96c8593536E31F229EA8f37b2ADa2699bb2",6),
 "DAI":Token("DAI","0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb",18),
}

class AeroScanner:
    def __init__(self, execute=False):
        load_dotenv('.env.local')
        self.execute=execute
        self.w3=Web3(Web3.HTTPProvider(os.environ['BASE_RPC']))
        self.wallet=Web3.to_checksum_address(os.environ['WALLET_ADDRESS'])
        self.pk=os.environ['PRIVATE_KEY']
        with open('live-flashloan/deployments.json') as f:
            dep=json.load(f)['contracts']['base']
        self.contract_addr=Web3.to_checksum_address(dep['flashLoanArbGeneric'])
        self.flash=self.w3.eth.contract(address=self.contract_addr, abi=FLASH_ABI)
        self.aero=self.w3.eth.contract(address=Web3.to_checksum_address(AERO_ROUTER), abi=AERO_ABI)

    def units(self, amt, t): return int(amt*(10**t.decimals))
    def human(self, amt, t): return amt/(10**t.decimals)
    def route(self, a, b, stable=True): return [(Web3.to_checksum_address(a),Web3.to_checksum_address(b),stable,Web3.to_checksum_address(AERO_FACTORY))]
    def quote(self, amt, token_in, token_out, stable=True):
        try: return self.aero.functions.getAmountsOut(amt,self.route(token_in,token_out,stable)).call()
        except Exception: return None
    def gas_usd(self, gas=900000): return gas*self.w3.eth.gas_price/1e18*ETH_PRICE_USD

    def scan(self):
        cands=[]
        amounts=[10,25,50,100,250,500,1000,2500,5000,10000]
        for borrow_sym,borrow in TOKENS.items():
            for mid_sym,mid in TOKENS.items():
                if mid_sym==borrow_sym: continue
                for stable_a in [True,False]:
                    for stable_b in [True,False]:
                        for amt_h in amounts:
                            amt=self.units(amt_h,borrow)
                            q1=self.quote(amt,borrow.address,mid.address,stable_a)
                            if not q1: continue
                            mid_out=q1[-1]
                            q2=self.quote(mid_out,mid.address,borrow.address,stable_b)
                            if not q2: continue
                            final=q2[-1]
                            premium=amt*AAVE_PREMIUM_BPS//10000
                            gross=final-amt-premium
                            net=self.human(gross,borrow)-self.gas_usd()
                            if net>MIN_NET_PROFIT_USD:
                                cands.append(dict(network='base',borrow=borrow_sym,mid=mid_sym,amount=amt,amount_human=amt_h,stableA=stable_a,stableB=stable_b,mid_out=mid_out,final_out=final,premium=premium,net_profit_usd=net))
        return sorted(cands,key=lambda x:x['net_profit_usd'], reverse=True)

    def params(self,c):
        borrow=TOKENS[c['borrow']]; mid=TOKENS[c['mid']]
        min_mid=c['mid_out']*(10000-SLIPPAGE_BPS)//10000
        min_final=c['final_out']*(10000-SLIPPAGE_BPS)//10000
        min_profit=max(1,int((c['net_profit_usd']/2)*(10**borrow.decimals)))
        deadline=int(time.time())+120
        call_a=self.aero.functions.swapExactTokensForTokens(c['amount'],min_mid,self.route(borrow.address,mid.address,c['stableA']),self.contract_addr,deadline)._encode_transaction_data()
        call_b=self.aero.functions.swapExactTokensForTokens(c['mid_out'],min_final,self.route(mid.address,borrow.address,c['stableB']),self.contract_addr,deadline)._encode_transaction_data()
        return (Web3.to_checksum_address(AERO_ROUTER),Web3.to_checksum_address(AERO_ROUTER),Web3.to_checksum_address(borrow.address),Web3.to_checksum_address(mid.address),min_profit,bytes.fromhex(call_a[2:]),bytes.fromhex(call_b[2:]))

    def simulate(self,c):
        try:
            self.flash.functions.executeArb(self.params(c),c['amount']).call({'from':self.wallet})
            return True,'eth_call simulation passed'
        except Exception as e: return False,str(e)[:500]

    def execute_live(self,c):
        tx=self.flash.functions.executeArb(self.params(c),c['amount']).build_transaction({'from':self.wallet,'nonce':self.w3.eth.get_transaction_count(self.wallet),'chainId':8453,'gas':950000,'maxFeePerGas':int(self.w3.eth.gas_price*2),'maxPriorityFeePerGas':max(1,int(self.w3.eth.gas_price*0.3))})
        signed=self.w3.eth.account.sign_transaction(tx,self.pk)
        h=self.w3.eth.send_raw_transaction(signed.raw_transaction)
        r=self.w3.eth.wait_for_transaction_receipt(h,timeout=180)
        if r.status!=1: raise RuntimeError('tx reverted '+h.hex())
        return h.hex()

    def run(self):
        cands=self.scan(); results=[]
        for c in cands[:10]:
            ok,msg=self.simulate(c); c['simulation_ok']=ok; c['simulation_message']=msg
            if ok and self.execute: c['tx_hash']=self.execute_live(c)
            results.append(c)
        out={'timestamp':datetime.now().isoformat(),'network':'base','contract':self.contract_addr,'candidates_found':len(cands),'results':results}
        with open('AERODROME_FLASHLOAN_SCAN_BASE.json','w') as f: json.dump(out,f,indent=2)
        return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--execute',action='store_true'); args=ap.parse_args()
    out=AeroScanner(args.execute).run()
    print(json.dumps({k:v for k,v in out.items() if k!='results'},indent=2))
    for r in out['results'][:5]: print(json.dumps({k:r[k] for k in ['borrow','mid','amount_human','stableA','stableB','net_profit_usd','simulation_ok','simulation_message']},indent=2))
if __name__=='__main__': main()
