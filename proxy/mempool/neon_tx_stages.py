from __future__ import annotations

import abc
import base58
import sha3

from typing import Optional, Dict, Any
from logged_groups import logged_group
from solana.publickey import PublicKey
from solana.transaction import TransactionInstruction

from ..common_neon.address import accountWithSeed
from ..common_neon.compute_budget import TransactionWithComputeBudget
from ..common_neon.layouts import ACCOUNT_INFO_LAYOUT
from ..common_neon.neon_instruction import NeonIxBuilder


@logged_group("neon.Proxy")
class NeonTxStage(abc.ABC):
    NAME = 'UNKNOWN'

    def __init__(self, builder: NeonIxBuilder):
        self._builder = builder
        self._size = 0
        self._balance = 0
        self.tx = TransactionWithComputeBudget()

    def _is_empty(self) -> bool:
        return not len(self.tx.signatures)

    @abc.abstractmethod
    def build(self) -> None:
        pass

    @property
    def size(self) -> int:
        assert self._size > 0
        return self._size

    def set_balance(self, value: int) -> None:
        assert value > 0
        self._balance = value

    def has_balance(self) -> bool:
        return self._balance > 0

    @property
    def balance(self):
        assert self.has_balance()
        return self._balance


class NeonCreateAccountWithSeedStage(NeonTxStage, abc.ABC):
    def __init__(self, builder: NeonIxBuilder):
        super().__init__(builder)
        self._seed = bytes()
        self._seed_base = bytes()
        self._sol_account: Optional[PublicKey] = None

    def _init_sol_account(self) -> None:
        assert len(self._seed_base) > 0

        self._seed = base58.b58encode(self._seed_base)
        self._sol_account = accountWithSeed(bytes(self._builder.operator_account), self._seed)

    @property
    def sol_account(self) -> PublicKey:
        assert self._sol_account is not None
        return self._sol_account

    def _create_account_with_seed(self) -> TransactionInstruction:
        assert len(self._seed) > 0

        return self._builder.create_account_with_seed_instruction(self.sol_account, self._seed, self.balance, self.size)


class NeonCreateAccountTxStage(NeonTxStage):
    NAME = 'createNeonAccount'

    def __init__(self, builder: NeonIxBuilder, account_desc: Dict[str, Any]):
        super().__init__(builder)
        self._address = account_desc['address']
        self._size = ACCOUNT_INFO_LAYOUT.sizeof()

    def _create_account(self) -> TransactionInstruction:
        assert self.has_balance()
        return self._builder.make_create_eth_account_instruction(self._address)

    def build(self) -> None:
        assert self._is_empty()
        self.debug(f'Create user account {self._address}')
        self.tx.add(self._create_account())


class NeonCreateERC20TxStage(NeonTxStage):
    NAME = 'createERC20Account'

    def __init__(self, builder: NeonIxBuilder, token_account_desc: Dict[str, Any]):
        super().__init__(builder)
        self._token_account_desc = token_account_desc
        self._size = 124

    def _create_erc20_account(self) -> TransactionInstruction:
        assert self.has_balance()
        return self._builder.make_erc20token_account_instruction(self._token_account_desc)

    def build(self) -> None:
        assert self._is_empty()

        self.debug(
            f'Create ERC20 token account: ' +
            f'key {self._token_account_desc["key"]}, ' +
            f'owner: {self._token_account_desc["owner"]}, ' +
            f'contact: {self._token_account_desc["contract"]}, ' +
            f'mint: {self._token_account_desc["mint"]}'
        )

        self.tx.add(self._create_erc20_account())


class NeonCreatePermAccountStage(NeonCreateAccountWithSeedStage):
    NAME = 'createPermAccount'

    def __init__(self, builder: NeonIxBuilder, seed_base: bytes, size: int):
        super().__init__(builder)
        self._seed_base = seed_base
        self._size = size
        self._init_sol_account()

    def _init_sol_account(self):
        assert len(self._seed_base) > 0
        seed = sha3.keccak_256(self._seed_base).hexdigest()[:32]
        self._seed = bytes(seed, 'utf8')
        self._sol_account = accountWithSeed(bytes(self._builder.operator_account), self._seed)

    def get_seed(self):
        return self._seed_base

    def build(self):
        assert self._is_empty()

        self.debug(f'Create perm account {self.sol_account}')
        self.tx.add(self._create_account_with_seed())


@logged_group("neon.Proxy")
class NeonDeletePermAccountStage(NeonCreatePermAccountStage):
    NAME = 'refundPermAccount'

    def __init__(self, builder: NeonIxBuilder, seed_base: bytes):
        NeonCreatePermAccountStage.__init__(self, builder, seed_base, 0)

    def _delete_account(self):
        return self._builder.create_refund_instruction(self.sol_account, self._seed)

    def build(self):
        assert self._is_empty()

        self.debug(f'Refund perm account {self.sol_account}')
        self.tx.add(self._delete_account())
