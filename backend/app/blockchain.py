from web3 import Web3
import json
import os

# Token.sol/Token.json is a precompiled artifact (abi + bytecode), not
# compiled from source at request time - see contracts/token/ERC20/Token.sol
# for the contract and its own comment for why. The original design
# baked token_name/token_symbol into the Solidity *source* per deployment
# and ran solcx's install_solc()/compile_standard() on every backend
# startup - which (a) needs network access to download a solc binary on
# first use, and (b) only ships amd64 Linux binaries (confirmed: no
# arm64 build exists for any solc release solcx's index lists), so it
# never runs on an Apple Silicon host even under Docker Desktop's x86
# emulation (the downloaded amd64 solc binary itself fails under Rosetta
# with "failed to open elf at /lib64/ld-linux-x86-64.so.2" - a second,
# unrelated layer of emulation solc's own binary doesn't survive).
# ERC20's own constructor already takes name/symbol as real arguments, so
# there's no need to regenerate source per deployment at all - compile
# once (see FUTURE.md or the repo's build notes for the `forge build`
# command used), commit the artifact, and just vary the constructor
# *arguments* at deploy time like any normal contract deployment tool
# (Truffle/Hardhat/Foundry) would.
_TOKEN_ARTIFACT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "contracts", "Token.json")


def _load_token_artifact() -> dict:
    with open(_TOKEN_ARTIFACT_PATH) as f:
        return json.load(f)


def create_transaction(w3: Web3, chain_id: int, token_name: str, token_symbol: str, wallet_address: str):
    artifact = _load_token_artifact()

    # create a transaction
    checksum_address = w3.to_checksum_address(wallet_address)
    contract = w3.eth.contract(abi=artifact["abi"], bytecode=artifact["bytecode"])
    nonce = w3.eth.get_transaction_count(checksum_address)
    tx = contract.constructor(token_name, token_symbol).build_transaction(
        {
        "gasPrice": w3.eth.gas_price,
        "from": checksum_address,
        "nonce": nonce,
        "chainId": chain_id,
        }
    )

    return tx, artifact["abi"]

def sign_and_send_transaction(w3: Web3, tx: dict, wallet_key: str):
    # Sign the transaction
    sign_transaction = w3.eth.account.sign_transaction(tx, private_key=wallet_key)
    print("Deploying Contract!")
    # Send the transaction
    transaction_hash = w3.eth.send_raw_transaction(sign_transaction.raw_transaction)

    # Wait for the transaction to be mined, and get the transaction receipt
    print("Waiting for transaction to finish...")
    transaction_receipt = w3.eth.wait_for_transaction_receipt(transaction_hash)
    print(f"Done! Contract deployed to {transaction_receipt.contractAddress}")

    return transaction_receipt.contractAddress


def create_token(token_name: str, token_symbol: str, rpc_url: str, chain_id: int, wallet_address: str, wallet_key: str):
    w3 = Web3(Web3.HTTPProvider(rpc_url))

    tx, abi = create_transaction(w3, chain_id, token_name, token_symbol, wallet_address)

    token_address = sign_and_send_transaction(w3, tx, wallet_key)

    return token_address, abi
