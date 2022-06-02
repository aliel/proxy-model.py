import sys
import json
import os
import subprocess
from logged_groups import logged_group, LogMng
from solana.publickey import PublicKey
from solana.account import Account as SolanaAccount
from typing import Optional, List

from .common_neon.environment_data import SOLANA_URL, EVM_LOADER_ID, neon_cli_timeout, LOG_NEON_CLI_DEBUG


class CliBase:
    def run_cli(self, cmd: List[str], **kwargs) -> bytes:
        self.debug("Calling: " + " ".join(cmd))
        proc_result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
        if proc_result.stderr is not None:
            print(proc_result.stderr, file=sys.stderr)
        output = proc_result.stdout
        if not output:
            proc_result.check_returncode()
        return output


@logged_group("neon.Proxy")
class solana_cli(CliBase):
    def call(self, *args):
        try:
            cmd = ["solana",
                   "--url", SOLANA_URL,
                   ] + list(args)
            self.debug("Calling: " + " ".join(cmd))
            return self.run_cli(cmd, universal_newlines=True)
        except subprocess.CalledProcessError as err:
            self.error("ERR: solana error {}".format(err))
            raise


@logged_group("neon.Proxy")
def get_solana_accounts(*, logger) -> [SolanaAccount]:
    def read_sol_account(name) -> Optional[SolanaAccount]:
        if not os.path.isfile(name):
            return None

        with open(name.strip(), mode='r') as d:
            pkey = (d.read())
            num_list = [int(v) for v in pkey.strip("[] \n").split(',')]
            value_list = bytes(num_list[0:32])
            return SolanaAccount(value_list)

    res = solana_cli().call('config', 'get')
    substr = "Keypair Path: "
    path = ""
    for line in res.splitlines():
        if line.startswith(substr):
            path = line[len(substr):].strip()
    if path == "":
        raise Exception("cannot get keypair path")

    path = path.strip()

    signer_list = []
    (file_name, file_ext) = os.path.splitext(path)
    i = 0
    while True:
        i += 1
        full_path = file_name + (str(i) if i > 1 else '') + file_ext
        signer = read_sol_account(full_path)
        if not signer:
            break
        signer_list.append(signer)
        logger.debug(f'Add signer: {signer.public_key()}')

    if not len(signer_list):
        raise Exception("No keypairs")

    return signer_list


@logged_group("neon.Proxy")
class neon_cli(CliBase):
    def call(self, *args):
        try:
            ctx = json.dumps(LogMng.get_logging_context())
            cmd = ["neon-cli",
                   "--commitment=recent",
                   "--url", SOLANA_URL,
                   f"--evm_loader={EVM_LOADER_ID}",
                   f"--logging_ctx={ctx}"
                   ]\
                  + (["-vvv"] if LOG_NEON_CLI_DEBUG else [])\
                  + list(args)
            return self.run_cli(cmd, timeout=neon_cli_timeout, universal_newlines=True)
        except subprocess.CalledProcessError as err:
            self.error("ERR: neon-cli error {}".format(err))
            raise

    def version(self):
        try:
            cmd = ["neon-cli", "--version"]
            return self.run_cli(cmd, timeout=neon_cli_timeout, universal_newlines=True).split()[1]
        except subprocess.CalledProcessError as err:
            self.error("ERR: neon-cli error {}".format(err))
            raise


@logged_group("neon.Proxy")
def read_elf_params(out_dict, *, logger):
    logger.debug("Read ELF params")
    for param in neon_cli().call("neon-elf-params").splitlines():
        if param.startswith('NEON_') and '=' in param:
            v = param.split('=')
            out_dict[v[0]] = v[1]
            logger.debug(f"ELF param: {v[0]}: {v[1]}")


ELF_PARAMS = {}
read_elf_params(ELF_PARAMS)
COLLATERAL_POOL_BASE = ELF_PARAMS.get("NEON_POOL_BASE")
NEON_TOKEN_MINT: PublicKey = PublicKey(ELF_PARAMS.get("NEON_TOKEN_MINT"))
HOLDER_MSG_SIZE = int(ELF_PARAMS.get("NEON_HOLDER_MSG_SIZE"))
CHAIN_ID = int(ELF_PARAMS.get('NEON_CHAIN_ID', None))
NEON_EVM_VERSION = ELF_PARAMS.get("NEON_PKG_VERSION")
NEON_EVM_REVISION = ELF_PARAMS.get('NEON_REVISION')
NEON_COMPUTE_UNITS = int(ELF_PARAMS.get('NEON_COMPUTE_UNITS'))
NEON_HEAP_FRAME = int(ELF_PARAMS.get('NEON_HEAP_FRAME'))
NEON_ADDITIONAL_FEE = int(ELF_PARAMS.get('NEON_ADDITIONAL_FEE'))
NEON_GAS_LIMIT_MULTIPLIER_NO_CHAINID = int(ELF_PARAMS.get('NEON_GAS_LIMIT_MULTIPLIER_NO_CHAINID'))
