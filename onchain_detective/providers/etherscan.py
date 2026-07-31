import requests
from datetime import datetime
from typing import Optional

from .base import BaseProvider, Transaction, TokenTransfer, WalletInfo
from ..utils.rate_limiter import etherscan_limiter
from ..utils.cache import cached
from ..config import settings


class EtherscanProvider(BaseProvider):
    """Провайдер данных через Etherscan API V2."""

    def __init__(self, api_key: str, base_url: str = None):
        super().__init__(api_key)
        self.base_url = base_url or settings.etherscan_base_url

    def _request(self, params: dict) -> dict:
        """Базовый запрос к API V2."""
        params["apikey"] = self.api_key

        @etherscan_limiter
        def _call():
            response = requests.get(self.base_url, params=params, timeout=30)
            data = response.json()

            if data.get("status") == "0":
                error_msg = str(data.get("result", ""))
                if "No transactions found" in error_msg or "No records found" in error_msg:
                    return {"status": "1", "result": []}
                raise Exception(f"Etherscan API error: {error_msg}")

            return data

        return _call()

    @cached(ttl=300)
    def get_transactions(self, address: str, start_block: int = 0,
                         end_block: int = 99999999) -> list[Transaction]:
        params = {
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": start_block,
            "endblock": end_block,
            "sort": "asc",
            "chainid": 1,
        }
        data = self._request(params)

        transactions = []
        for tx in data.get("result", []):
            transactions.append(Transaction(
                hash=tx["hash"],
                block_number=int(tx["blockNumber"]),
                timestamp=datetime.fromtimestamp(int(tx["timeStamp"])),
                from_address=tx["from"],
                to_address=tx.get("to", ""),
                value=float(tx["value"]) / 1e18,
                gas_used=int(tx.get("gasUsed", 0)),
                gas_price=float(tx.get("gasPrice", 0)) / 1e18 if tx.get("gasPrice") else None,
                is_error=tx.get("isError", "0") == "1",
                input_data=tx.get("input", ""),
                raw=tx,
            ))
        return transactions

    @cached(ttl=300)
    def get_token_transfers(self, address: str, token_address: str = None,
                            start_block: int = 0, end_block: int = 99999999) -> list[TokenTransfer]:
        params = {
            "module": "account",
            "action": "tokentx",
            "address": address,
            "startblock": start_block,
            "endblock": end_block,
            "sort": "asc",
            "chainid": 1,
        }
        if token_address:
            params["contractaddress"] = token_address

        data = self._request(params)

        transfers = []
        for tx in data.get("result", []):
            decimals = int(tx.get("tokenDecimal", 18))
            transfers.append(TokenTransfer(
                token_address=tx["contractAddress"],
                token_name=tx.get("tokenName"),
                token_symbol=tx.get("tokenSymbol"),
                from_address=tx["from"],
                to_address=tx.get("to", ""),
                value=float(tx["value"]) / (10 ** decimals),
                transaction_hash=tx["hash"],
                block_number=int(tx["blockNumber"]),
                timestamp=datetime.fromtimestamp(int(tx["timeStamp"])),
            ))
        return transfers

    @cached(ttl=600)
    def get_wallet_info(self, address: str) -> WalletInfo:
        balance_params = {
            "module": "account",
            "action": "balance",
            "address": address,
            "tag": "latest",
            "chainid": 1,
        }
        balance_data = self._request(balance_params)
        balance_wei = int(balance_data.get("result", 0))
        balance_native = balance_wei / 1e18

        tx_params = {
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": 0,
            "endblock": 99999999,
            "page": 1,
            "offset": 1,
            "sort": "asc",
            "chainid": 1,
        }
        first_tx_data = self._request(tx_params)
        first_tx = first_tx_data.get("result", [])
        first_tx_date = None
        if first_tx:
            first_tx_date = datetime.fromtimestamp(int(first_tx[0]["timeStamp"]))

        tx_params["sort"] = "desc"
        last_tx_data = self._request(tx_params)
        last_tx = last_tx_data.get("result", [])
        last_tx_date = None
        if last_tx:
            last_tx_date = datetime.fromtimestamp(int(last_tx[0]["timeStamp"]))

        code_params = {
            "module": "proxy",
            "action": "eth_getCode",
            "address": address,
            "tag": "latest",
            "chainid": 1,
        }
        code_data = self._request(code_params)
        is_contract = code_data.get("result", "0x") != "0x"

        return WalletInfo(
            address=address,
            balance_native=balance_native,
            first_tx_date=first_tx_date,
            last_tx_date=last_tx_date,
            total_tx_count=0,
            is_contract=is_contract,
        )

    def get_contract_creator(self, contract_address: str) -> Optional[str]:
        params = {
            "module": "contract",
            "action": "getcontractcreation",
            "contractaddresses": contract_address,
            "chainid": 1,
        }
        data = self._request(params)
        result = data.get("result", [])
        if result:
            return result[0].get("contractCreator")
        return None