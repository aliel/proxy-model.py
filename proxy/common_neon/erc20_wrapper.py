from solcx import install_solc
from web3 import Web3
from spl.token.client import Token
from spl.token.constants import TOKEN_PROGRAM_ID
from eth_account.signers.local import LocalAccount as NeonAccount
from solana.rpc.api import Account as SolanaAccount
from solana.publickey import PublicKey
from solana.transaction import AccountMeta, TransactionInstruction
from solana.system_program import SYS_PROGRAM_ID
from solana.sysvar import SYSVAR_RENT_PUBKEY
from solana.rpc.types import TxOpts, RPCResponse, Commitment
import spl.token.instructions as spl_token
from typing import Union, Dict
import struct
from logged_groups import logged_group
from .compute_budget import TransactionWithComputeBudget

install_solc(version='0.7.6')
from solcx import compile_source

# Standard interface of ERC20 contract to generate ABI for wrapper
ERC20_INTERFACE_SOURCE = '''
pragma solidity >= 0.7.0;
pragma abicoder v2;

interface SPLToken {

    enum AccountState {
        Uninitialized,
        Initialized,
        Frozen
    }

    struct Account {
        bytes32 mint;
        bytes32 owner;
        uint64 amount;
        bytes32 delegate;
        uint64 delegated_amount;
        bytes32 close_authority;
        AccountState state;
    }

    struct Mint {
        uint64 supply;
        uint8 decimals;
        bool isInitialized;
        bytes32 freezeAuthority;
        bytes32 mintAuthority;
    }

    function findAccount(bytes32 salt) external pure returns(bytes32);

    function exists(bytes32 account) external view returns(bool);
    function getAccount(bytes32 account) external view returns(Account memory);
    function getMint(bytes32 account) external view returns(Mint memory);

    function initializeMint(bytes32 salt, uint8 decimals) external returns(bytes32);
    function initializeMint(bytes32 salt, uint8 decimals, bytes32 mint_authority, bytes32 freeze_authority) external returns(bytes32);

    function initializeAccount(bytes32 salt, bytes32 mint) external returns(bytes32);
    function initializeAccount(bytes32 salt, bytes32 mint, bytes32 owner) external returns(bytes32);

    function closeAccount(bytes32 account) external;

    function mintTo(bytes32 account, uint64 amount) external;
    function burn(bytes32 account, uint64 amount) external;

    function approve(bytes32 source, bytes32 target, uint64 amount) external;
    function revoke(bytes32 source) external;

    function transfer(bytes32 source, bytes32 target, uint64 amount) external;

    function freeze(bytes32 account) external;
    function thaw(bytes32 account) external;
}
'''

# Copy of contract: https://github.com/neonlabsorg/neon-evm/blob/develop/evm_loader/erc20_for_spl.sol
ERC20_CONTRACT_SOURCE = '''
// SPDX-License-Identifier: MIT

contract ERC20ForSpl {
    SPLToken constant _splToken = SPLToken(0xFf00000000000000000000000000000000000004);

    string public name;
    string public symbol;
    bytes32 immutable public tokenMint;

    mapping(address => mapping(address => uint256)) private _allowances;


    event Transfer(address indexed from, address indexed to, uint256 amount);
    event Approval(address indexed owner, address indexed spender, uint256 amount);

    event ApprovalSolana(address indexed owner, bytes32 indexed spender, uint64 amount);
    event TransferSolana(address indexed from, bytes32 indexed to, uint64 amount);

    constructor(string memory _name, string memory _symbol, bytes32 _tokenMint) {
        require(_splToken.getMint(_tokenMint).isInitialized, "ERC20: invalid token mint");

        name = _name;
        symbol = _symbol;
        tokenMint = _tokenMint;
    }

    function decimals() public view returns (uint8) {
        return _splToken.getMint(tokenMint).decimals;
    }

    function totalSupply() public view returns (uint256) {
        return _splToken.getMint(tokenMint).supply;
    }

    function balanceOf(address who) public view returns (uint256) {
        bytes32 account = _solanaAccount(who);
        return _splToken.getAccount(account).amount;
    }

    function allowance(address owner, address spender) public view returns (uint256) {
        return _allowances[owner][spender];
    }

    function approve(address spender, uint256 amount) public returns (bool) {
        address owner = msg.sender;

        _approve(owner, spender, amount);

        return true;
    }

    function transfer(address to, uint256 amount) public returns (bool) {
        address from = msg.sender;

        _transfer(from, to, amount);

        return true;
    }


    function transferFrom(address from, address to, uint256 amount) public returns (bool) {
        address spender = msg.sender;

        _spendAllowance(from, spender, amount);
        _transfer(from, to, amount);

        return true;
    }

    function burn(uint256 amount) public returns (bool) {
        address from = msg.sender;

        _burn(from, amount);

        return true;
    }


    function burnFrom(address from, uint256 amount) public returns (bool) {
        address spender = msg.sender;

        _spendAllowance(from, spender, amount);
        _burn(from, amount);

        return true;
    }

    
    function approveSolana(bytes32 spender, uint64 amount) public returns (bool) {
        address from = msg.sender;
        bytes32 fromSolana = _solanaAccount(from);

        if (amount > 0) {
            _splToken.approve(fromSolana, spender, amount);
        } else {
            _splToken.revoke(fromSolana);
        }

        emit Approval(from, address(0), amount);
        emit ApprovalSolana(from, spender, amount);

        return true;
    }

    function transferSolana(bytes32 to, uint64 amount) public returns (bool) {
        address from = msg.sender;
        bytes32 fromSolana = _solanaAccount(from);

        _splToken.transfer(fromSolana, to, uint64(amount));

        emit Transfer(from, address(0), amount);
        emit TransferSolana(from, to, amount);

        return true;
    }

    function claim(bytes32 from, uint64 amount) external returns (bool) {
        bytes32 toSolana = _solanaAccount(msg.sender);

        if (!_splToken.exists(toSolana)) {
            _splToken.initializeAccount(_salt(msg.sender), tokenMint);
        }

        // spl-token transaction will be signed by tx.origin
        // this is only allowed in top level contract
        (bool status, ) = address(_splToken).delegatecall(
            abi.encodeWithSignature("transfer(bytes32,bytes32,uint64)", from, toSolana, amount)
        );

        require(status, "ERC20: claim failed");

        emit Transfer(address(0), msg.sender, amount);

        return true;
    }

    function _approve(address owner, address spender, uint256 amount) internal {
        require(owner != address(0), "ERC20: approve from the zero address");
        require(spender != address(0), "ERC20: approve to the zero address");

        _allowances[owner][spender] = amount;
        emit Approval(owner, spender, amount);
    }

    function _spendAllowance(address owner, address spender, uint256 amount) internal {
        uint256 currentAllowance = allowance(owner, spender);
        if (currentAllowance != type(uint256).max) {
            require(currentAllowance >= amount, "ERC20: insufficient allowance");
            _approve(owner, spender, currentAllowance - amount);
        }
    }

    function _burn(address from, uint256 amount) internal {
        require(from != address(0), "ERC20: burn from the zero address");
        require(amount <= type(uint64).max, "ERC20: burn amount exceeds uint64 max");

        bytes32 fromSolana = _solanaAccount(from);

        require(_splToken.getAccount(fromSolana).amount >= amount, "ERC20: burn amount exceeds balance");
        _splToken.burn(fromSolana, uint64(amount));

        emit Transfer(from, address(0), amount);
    }

    function _transfer(address from, address to, uint256 amount) internal {
        require(from != address(0), "ERC20: transfer from the zero address");
        require(to != address(0), "ERC20: transfer to the zero address");

        bytes32 fromSolana = _solanaAccount(from);
        bytes32 toSolana = _solanaAccount(to);

        require(amount <= type(uint64).max, "ERC20: transfer amount exceeds uint64 max");
        require(_splToken.getAccount(fromSolana).amount >= amount, "ERC20: transfer amount exceeds balance");

        if (!_splToken.exists(toSolana)) {
            _splToken.initializeAccount(_salt(to), tokenMint);
        }

        _splToken.transfer(fromSolana, toSolana, uint64(amount));

        emit Transfer(from, to, amount);
    }

    function _salt(address account) internal pure returns (bytes32) {
        return bytes32(uint256(uint160(account)));
    }

    function _solanaAccount(address account) internal pure returns (bytes32) {
        return _splToken.findAccount(_salt(account));
    }
}
'''


@logged_group("neon.Proxy")
class ERC20Wrapper:
    proxy: Web3
    name: str
    symbol: str
    token: Token
    admin: NeonAccount
    mint_authority: SolanaAccount
    evm_loader_id: PublicKey
    neon_contract_address: str
    solana_contract_address: PublicKey
    interface: Dict
    wrapper: Dict

    def __init__(self, proxy: Web3,
                 name: str, symbol: str,
                 token: Token,
                 admin: NeonAccount,
                 mint_authority: SolanaAccount,
                 evm_loader_id: PublicKey):
        self.proxy = proxy
        self.name = name
        self.symbol = symbol
        self.token = token
        self.admin = admin
        self.mint_authority = mint_authority
        self.evm_loader_id = evm_loader_id

    def get_neon_account_address(self, neon_account_address: str) -> PublicKey:
        neon_account_addressbytes = bytes.fromhex(neon_account_address[2:])
        return PublicKey.find_program_address([b"\1", neon_account_addressbytes], self.evm_loader_id)[0]

    def deploy_wrapper(self):
        compiled_interface = compile_source(ERC20_INTERFACE_SOURCE)
        interface_id, interface = compiled_interface.popitem()
        self.interface = interface

        compiled_wrapper = compile_source(ERC20_CONTRACT_SOURCE)
        wrapper_id, wrapper_interface = compiled_wrapper.popitem()
        self.wrapper = wrapper_interface

        erc20 = self.proxy.eth.contract(abi=self.wrapper['abi'], bytecode=wrapper_interface['bin'])
        nonce = self.proxy.eth.get_transaction_count(self.proxy.eth.default_account)
        tx = {'nonce': nonce}
        tx_constructor = erc20.constructor(self.name, self.symbol, bytes(self.token.pubkey)).buildTransaction(tx)
        tx_deploy = self.proxy.eth.account.sign_transaction(tx_constructor, self.admin.key)
        tx_deploy_hash = self.proxy.eth.send_raw_transaction(tx_deploy.rawTransaction)
        self.debug(f'tx_deploy_hash: {tx_deploy_hash.hex()}')
        tx_deploy_receipt = self.proxy.eth.wait_for_transaction_receipt(tx_deploy_hash)
        self.debug(f'tx_deploy_receipt: {tx_deploy_receipt}')
        self.debug(f'deploy status: {tx_deploy_receipt.status}')
        self.neon_contract_address = tx_deploy_receipt.contractAddress
        self.solana_contract_address = self.get_neon_account_address(self.neon_contract_address)

    def get_neon_erc20_account_address(self, neon_account_address: str):
        neon_contract_address_bytes = bytes.fromhex(self.neon_contract_address[2:])
        neon_account_address_bytes = bytes.fromhex(neon_account_address[2:])
        seeds = [b"\1", b"ERC20Balance",
                 bytes(self.token.pubkey),
                 neon_contract_address_bytes,
                 neon_account_address_bytes]
        return PublicKey.find_program_address(seeds, self.evm_loader_id)[0]

    def create_associated_token_account(self, owner: PublicKey, payer: SolanaAccount):
        # Construct transaction
        # This part of code is based on original implementation of Token.create_associated_token_account
        # except that skip_preflight is set to True
        tx = TransactionWithComputeBudget()
        create_ix = spl_token.create_associated_token_account(
            payer=payer.public_key(), owner=owner, mint=self.token.pubkey
        )
        tx.add(create_ix)
        self.token._conn.send_transaction(tx, payer, opts=TxOpts(skip_preflight = True, skip_confirmation=False))
        return create_ix.keys[1].pubkey

    def create_neon_erc20_account_instruction(self, payer: PublicKey, eth_address: str):
        return TransactionInstruction(
            program_id=self.evm_loader_id,
            data=bytes.fromhex('0F'),
            keys=[
                AccountMeta(pubkey=payer, is_signer=True, is_writable=True),
                AccountMeta(pubkey=self.get_neon_erc20_account_address(eth_address), is_signer=False, is_writable=True),
                AccountMeta(pubkey=self.get_neon_account_address(eth_address), is_signer=False, is_writable=True),
                AccountMeta(pubkey=self.solana_contract_address, is_signer=False, is_writable=True),
                AccountMeta(pubkey=self.token.pubkey, is_signer=False, is_writable=True),
                AccountMeta(pubkey=SYS_PROGRAM_ID, is_signer=False, is_writable=False),
                AccountMeta(pubkey=TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),
                AccountMeta(pubkey=SYSVAR_RENT_PUBKEY, is_signer=False, is_writable=False),
            ]
        )

    def create_input_liquidity_instruction(self, payer: PublicKey, from_address: PublicKey, to_address: str, amount: int):
        return TransactionInstruction(
            program_id=TOKEN_PROGRAM_ID,
            data=b'\3' + struct.pack('<Q', amount),
            keys=[
                AccountMeta(pubkey=from_address, is_signer=False, is_writable=True),
                AccountMeta(pubkey=self.get_neon_erc20_account_address(to_address), is_signer=False, is_writable=True),
                AccountMeta(pubkey=payer, is_signer=True, is_writable=False)
            ]
        )

    def mint_to(self, destination: Union[PublicKey, str], amount: int) -> RPCResponse:
        """
        Method mints given amount of tokens to a given address - either in NEON or Solana format
        NOTE: destination account must be previously created
        """
        if isinstance(destination, str):
            destination = self.get_neon_erc20_account_address(destination)
        return self.token.mint_to(destination, self.mint_authority, amount,
                                  opts=TxOpts(skip_preflight=True, skip_confirmation=False))

    def erc20_interface(self):
        return self.proxy.eth.contract(address=self.neon_contract_address, abi=self.interface['abi'])

    def get_balance(self, address: Union[PublicKey, str]) -> int:
        if isinstance(address, PublicKey):
            return int(self.token.get_balance(address, Commitment('confirmed'))['result']['value']['amount'])

        erc20 = self.proxy.eth.contract(address=self.neon_contract_address, abi=self.interface['abi'])
        return erc20.functions.balanceOf(address).call()
