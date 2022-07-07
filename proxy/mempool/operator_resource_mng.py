from __future__ import annotations

from typing import Optional, List

from solana.account import Account as SolanaAccount
from solana.publickey import PublicKey

from logged_groups import logged_group

from ..common_neon.address import EthereumAddress
from ..common_neon.environment_utils import get_solana_accounts


class OperatorResourceInfo:
    def __init__(self, signer: SolanaAccount, rid: int, idx: int):
        self.signer = signer
        self.rid = rid
        self.idx = idx
        self.ether: Optional[EthereumAddress] = None
        self.storage: Optional[PublicKey] = None
        self.holder: Optional[PublicKey] = None

    def public_key(self) -> PublicKey:
        return self.signer.public_key()

    def secret_key(self) -> bytes:
        return self.signer.secret_key()


@logged_group("neon.MemPool")
class OperatorResourceMng:

    def __init__(self):
        self._signer_list: List[SolanaAccount] = get_solana_accounts()

    def init_operator_resource_info(self):
        for rid in range(PERM_ACCOUNT_LIMIT):
            for signer in signer_list:
                info = OperatorResourceInfo(signer=signer, rid=rid, idx=idx)
                self._resource_list.append(info)
                idx += 1
