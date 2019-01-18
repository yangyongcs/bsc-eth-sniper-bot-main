import requests
from web3 import Web3
import os
import json
import time
from functools import wraps


class Token:
    # bnb
    ETH_ADDRESS = Web3.toChecksumAddress('0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c')

    MAX_AMOUNT = int('0x' + 'f' * 64, 16)

    def __init__(self, address, provider=None, provider_wss="wss://bsc-ws-node.nariox.org:443", trini_address='0x3f7494957a403c4a484b66c1c6d0807de2660d2f'):
        self.address = Web3.toChecksumAddress(address)
        self.trini_address = Web3.toChecksumAddress(trini_address)
        self.provider = os.environ['PROVIDER'] if not provider else provider
        self.provider_wss = provider_wss
        adapter = requests.adapters.HTTPAdapter(pool_connections=1000, pool_maxsize=1000)
        session = requests.Session()
        session.mount('http://', adapter)
        session.mount('https://', adapter)

        self.web3 = Web3(Web3.HTTPProvider(self.provider, session=session))
        self.web3_wss = Web3(Web3.WebsocketProvider(self.provider_wss))
        self.wallet_address = None

        # bnb
        self.router = self.web3.eth.contract(
            address=Web3.toChecksumAddress('0x10ed43c718714eb63d5aa57b78b54704e256024e'),
            abi=json.load(open("pyuniswap/abi_files_bnb/" + "router.abi")))
        self.erc20_abi = json.load(
            open("pyuniswap/abi_files_bnb/" + "erc20.abi"))
        self.presale_abi = json.load(
            open("pyuniswap/abi_files_bnb/" + "dxsale.abi"))
        self.gas_limit = 500000
        # self.gas_limit = 297255
        # self.gas_limit = 500000
    def get_presale_owner(self, presale_address="0xbaCEbAd5993a19c7188Db1cC8D0F748C9Af1689A", presale_id=2033):
        presale_contract = self.web3.eth.contract(address=Web3.toChecksumAddress(presale_address), abi=self.presale_abi)
        return presale_contract.functions.presaleOwners(presale_id).call()

    def get_symbol(self, address=None):
        address = self.wallet_address if not address else Web3.toChecksumAddress(address)
        if not address:
            raise RuntimeError('Please provide the wallet address!')
        erc20_contract = self.web3.eth.contract(address=self.address, abi=self.erc20_abi)
        return erc20_contract.functions.symbol().call()

    def decimals(self, address=None):
        address = self.wallet_address if not address else Web3.toChecksumAddress(address)
        if not address:
            raise RuntimeError('Please provide the wallet address!')
        erc20_contract = self.web3.eth.contract(address=self.address, abi=self.erc20_abi)
        return erc20_contract.functions.decimals().call()

    def set_gas_limit(self, gas_limit):
        self.gas_limit = int(gas_limit)

    def connect_wallet(self, wallet_address='', private_key=''):
        self.wallet_address = Web3.toChecksumAddress(wallet_address)
        self.private_key = private_key
        if not self.is_approved(self.ETH_ADDRESS):
            self.approve(self.ETH_ADDRESS, gas_price=self.web3.eth.gas_price, timeout=2100)

    def is_connected(self):
        return False if not self.wallet_address else True

    def require_connected(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if not self.is_connected():
                raise RuntimeError('Please connect the wallet first!')
            return func(self, *args, **kwargs)

        return wrapper

    def create_transaction_params(self, value=0, gas_price=None, gas_limit=None, nonce=0):
        if not self.is_connected():
            raise RuntimeError('Please connect the wallet first!')
        if not gas_price:
            gas_price = self.web3.eth.gasPrice
        if not gas_limit:
            gas_limit = self.gas_limit
        return {
            "from": self.wallet_address,
            "value": value,
            'gasPrice': gas_price,
            "gas": gas_limit,
            "nonce": self.web3.eth.getTransactionCount(self.wallet_address) + nonce
        }

    def send_transaction(self, func, params):
        tx = func.buildTransaction(params)
        signed_tx = self.web3.eth.account.sign_transaction(tx, private_key=self.private_key)
        # tx = tx_hash.hex()
        # self.web3.eth.waitForTransactionReceipt(tx)
        return self.web3.eth.sendRawTransaction(signed_tx.rawTransaction)

    def send_buy_transaction(self, signed_tx):
        return self.web3.eth.sendRawTransaction(signed_tx.rawTransaction)

    @require_connected
    def is_approved(self, token_address=None, amount=MAX_AMOUNT):
        token_address = Web3.toChecksumAddress(token_address) if token_address else self.address
        erc20_contract = self.web3.eth.contract(address=token_address, abi=self.erc20_abi)
        approved_amount = erc20_contract.functions.allowance(self.wallet_address, self.router.address).call()
        return approved_amount >= amount

    @require_connected
    def approve(self, token_address, amount=MAX_AMOUNT, gas_price=None, timeout=900):
        if not gas_price:
            gas_price = self.web3.eth.gasPrice
        token_address = Web3.toChecksumAddress(token_address)
        erc20_contract = self.web3.eth.contract(address=token_address, abi=self.erc20_abi)
        func = erc20_contract.functions.approve(self.router.address, amount)
        params = self.create_transaction_params(gas_price=gas_price)
        tx = self.send_transaction(func, params)
        self.web3.eth.waitForTransactionReceipt(tx, timeout=timeout)

    def price(self, amount=int(1e18), swap_token_address=ETH_ADDRESS):
        swap_token_address = Web3.toChecksumAddress(swap_token_address)
        return self.router.functions.getAmountsOut(amount, [self.address, swap_token_address]).call()[-1]

    def received_amount_by_swap(self, input_token_amount=int(1e18), input_token_address=ETH_ADDRESS):
        input_token_address = Web3.toChecksumAddress(input_token_address)
        return self.router.functions.getAmountsOut(input_token_amount, [input_token_address, self.address]).call()[-1]

    def balance(self, address=None):
        address = self.wallet_address if not address else Web3.toChecksumAddress(address)
        if not address:
            raise RuntimeError('Please provide the wallet address!')
        erc20_contract = self.web3.eth.contract(address=self.address, abi=self.erc20_abi)
        return erc20_contract.functions.balanceOf(self.wallet_address).call()

    def trini_balance(self, address=None):
        address = self.wallet_address if not address else Web3.toChecksumAddress(address)
        if not address:
            raise RuntimeError('Please provide the wallet address!')
        erc20_contract = self.web3.eth.contract(address=self.trini_address, abi=self.erc20_abi)
        return erc20_contract.functions.balanceOf(self.wallet_address).call()

    @require_connected
    def buy(self, consumed_token_amount, consumed_token_address=ETH_ADDRESS, slippage=0.01, timeout=900, gas_price=1, speed=1, nonce=0):
        gas_price = int(self.web3.eth.gasPrice*speed)
        min_out = 0
        func = self.router.functions.swapExactETHForTokens(min_out, [consumed_token_address, self.address],
                                                           self.wallet_address, int(time.time() + timeout))
        params = self.create_transaction_params(value=consumed_token_amount, gas_price=gas_price, nonce=nonce)

        tx = func.buildTransaction(params)
        return self.web3.eth.account.sign_transaction(tx, private_key=self.private_key)
        # return self.send_transaction(signed_tx)

    @require_connected
    def buybywbnb(self, consumed_token_amount, consumed_token_address=ETH_ADDRESS, slippage=0.01, timeout=900, speed=1):
        gas_price = int(5 * 10 ** 9 * speed)
        min_out = 0
        func = self.router.functions.swapExactTokensForTokensSupportingFeeOnTransferTokens(consumed_token_amount, min_out,
                                                              [consumed_token_address, self.address],
                                                              self.wallet_address, int(time.time() + timeout))
        params = self.create_transaction_params(gas_price=gas_price)
        tx = func.buildTransaction(params)
        return self.web3.eth.account.sign_transaction(tx, private_key=self.private_key)

    @require_connected
    def sell(self, amount, received_token_address=ETH_ADDRESS, slippage=0.01, timeout=900, gas_price=1, speed=1, nonce=0):
        gas_price = int(self.web3.eth.gasPrice * speed)
        min_out = 0
        if not self.is_approved(self.address, amount):
            self.approve(self.address, timeout=timeout)
        if received_token_address == self.ETH_ADDRESS:
            func = self.router.functions.swapExactTokensForETHSupportingFeeOnTransferTokens(amount, min_out, [self.address, received_token_address],
                                                               self.wallet_address, int(time.time() + timeout))
        else:
            func = self.router.functions.swapExactTokensForETHSupportingFeeOnTransferTokens(amount, min_out,
                                                                  [self.address, received_token_address],
                                                                  self.wallet_address, int(time.time() + timeout))
        params = self.create_transaction_params(gas_price=gas_price, nonce=nonce)
        return self.send_transaction(func, params)

    def contribute(self, presale='', amount=0, speed=1):
        gas_price = int(self.web3.eth.gasPrice * speed)
        tx = {
            'nonce': self.web3.eth.getTransactionCount(self.wallet_address),
            'to': Web3.toChecksumAddress(presale),
            'value': amount,
            'gas': self.gas_limit,
            'gasPrice': gas_price
        }
        signed_tx = self.web3.eth.account.sign_transaction(tx, self.private_key)

        tx_hash = self.web3.eth.sendRawTransaction(signed_tx.rawTransaction)
        return tx_hash

    @require_connected
    def sellbywbnb(self, amount, received_token_address=ETH_ADDRESS, slippage=0.01, timeout=900, speed=1):
        gas_price = int(self.web3.eth.gasPrice * speed)
        received_token_address = Web3.toChecksumAddress(received_token_address)
        received_amount = self.price(amount, received_token_address)
        min_out = int(received_amount * (1 - slippage))
        # min_out = 0
        if not self.is_approved(self.address, amount):
            self.approve(self.address, gas_price=gas_price, timeout=timeout)
        if received_token_address == self.ETH_ADDRESS:
            func = self.router.functions.swapExactTokensForTokens(amount, min_out,
                                                                  [self.address, received_token_address],
                                                                  self.wallet_address, int(time.time() + timeout))
        else:
            func = self.router.functions.swapExactTokensForTokens(amount, min_out,
                                                                  [self.address, received_token_address],
                                                                  self.wallet_address, int(time.time() + timeout))
        params = self.create_transaction_params(gas_price=gas_price)
        return self.send_transaction(func, params)