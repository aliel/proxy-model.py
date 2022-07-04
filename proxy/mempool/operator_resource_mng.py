from __future__ import annotations

from typing import Optional

from solana.account import Account as SolanaAccount
from solana.publickey import PublicKey

from logged_groups import logged_group

from ..common_neon.address import EthereumAddress


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
        pass

