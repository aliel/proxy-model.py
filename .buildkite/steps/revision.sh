set ${NEON_EVM_COMMIT:=v0.11.0}
set ${FAUCET_COMMIT:=latest}
set ${PROXY_LOG_CFG:=log_cfg.json}
set ${UNISWAP_V2_CORE_COMMIT:=stable}

# this is usefull for local builds
set ${SKIP_DOCKER_PULL:=NO}

export REVISION=${BUILDKITE_COMMIT}
export NEON_EVM_COMMIT
export FAUCET_COMMIT
export PROXY_LOG_CFG
export UNISWAP_V2_CORE_COMMIT
export SKIP_DOCKER_PULL

echo "REVISION=${REVISION}"
echo "NEON_EVM_COMMIT=${NEON_EVM_COMMIT}"
echo "FAUCET_COMMIT=${FAUCET_COMMIT}"
echo "PROXY_LOG_CFG=${PROXY_LOG_CFG}"
echo "UNISWAP_V2_CORE_COMMIT=${UNISWAP_V2_CORE_COMMIT}"
echo "SKIP_DOCKER_PULL=${SKIP_DOCKER_PULL}"
