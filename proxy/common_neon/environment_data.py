import os

SOLANA_URL = os.environ.get("SOLANA_URL", "http://localhost:8899")
PP_SOLANA_URL = os.environ.get("PP_SOLANA_URL", SOLANA_URL)
EVM_LOADER_ID = os.environ.get("EVM_LOADER")
neon_cli_timeout = float(os.environ.get("NEON_CLI_TIMEOUT", "0.5"))
CONFIRMATION_CHECK_DELAY = float(os.environ.get("NEON_CONFIRMATION_CHECK_DELAY", "0.1"))
CONTINUE_COUNT_FACTOR = int(os.environ.get("CONTINUE_COUNT_FACTOR", "3"))
TIMEOUT_TO_RELOAD_NEON_CONFIG = int(os.environ.get("TIMEOUT_TO_RELOAD_NEON_CONFIG", "3600"))
