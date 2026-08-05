import requests
import json
import logging
import os
import urllib.parse
from web3 import Web3

SOLC_VERSION = "0.8.6"

# contracts/FederatedLearning.json is a precompiled artifact (abi +
# bytecode), not compiled from source at trainer-pod startup - see
# backend/app/blockchain.py's identical change for the full reasoning
# (solcx only ships amd64 solc binaries, which don't run under Rosetta on
# an Apple Silicon host even inside an amd64-emulated container - a real
# blocker found by actually trying to run CASE=9 against a local Ethereum
# devnet, not by inspection). FederatedLearning.sol's constructor takes no
# arguments, so unlike the ERC20 token there's no per-deployment
# parameterization to preserve - compiling it once ahead of time loses
# nothing.
_ARTIFACT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "contracts", "FederatedLearning.json")


def _load_artifact() -> dict:
    with open(_ARTIFACT_PATH) as f:
        return json.load(f)


def create_federated_learning_smart_contract(
    eth_web3_connection: Web3,
    eth_wallet_address,
    eth_wallet_key,
    eth_blockscout_url,
):
    """Creates the federated learning smart contract

    Args:
        eth_web3_connection (Web3): Web3 connection
        eth_wallet_address (str): Ethereum wallet address
        eth_wallet_key (str): Ethereum wallet key
        eth_blockscout_url (str): Ethereum blockscout URL
    return:
        str: Smart contract address
        str: Smart contract ABI
    """

    artifact = _load_artifact()
    abi = artifact["abi"]
    bytecode = artifact["bytecode"]

    # Connect to the blockchain
    contract = eth_web3_connection.eth.contract(abi=abi, bytecode=bytecode)

    nonce = eth_web3_connection.eth.get_transaction_count(eth_wallet_address)

    # build transaction
    transaction = contract.constructor().build_transaction(
        {
            "gasPrice": eth_web3_connection.eth.gas_price,
            "from": eth_web3_connection.to_checksum_address(eth_wallet_address),
            "nonce": nonce,
        }
    )

    # Sign the transaction
    sign_transaction = eth_web3_connection.eth.account.sign_transaction(
        transaction, private_key=eth_wallet_key
    )
    logging.info("Deploying Contract!")

    # Send the transaction
    transaction_hash = eth_web3_connection.eth.send_raw_transaction(
        sign_transaction.raw_transaction
    )

    # Wait for the transaction to be mined, and get the transaction receipt
    logging.info("Waiting for transaction to finish...")
    transaction_receipt = eth_web3_connection.eth.wait_for_transaction_receipt(
        transaction_hash
    )
    logging.info(f"Done! Contract deployed to {transaction_receipt.contractAddress}")

    if eth_blockscout_url:
        logging.info("Trying to verify contract on blockscout...")
        try:
            federated_learning_file = open(
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "contracts", "FederatedLearning.sol")
            ).read()
            contract_verify_json = {
                "addressHash": transaction_receipt.contractAddress,
                "compilerVersion": SOLC_VERSION,
                "name": "FederatedLearning",
                "optimization": False,
                "contractSourceCode": federated_learning_file,
            }

            eth_blockscout_url = urllib.parse.urljoin(eth_blockscout_url, "/api?module=contract&action=verify")

            response = requests.post(eth_blockscout_url,json=contract_verify_json, timeout=30)

            # TODO: Check pq no se valida (la response da 500 cuando va muy rapido, pero si voy poco a poco va bien??)

            if response.status_code == 200 and response.json()["message"] == "OK":
                logging.info(f"Contract verified on provided Blockscout: {response.json()}")

        except Exception as e:
            logging.error(f"Failed to verify contract on provided Blockscout: {e}")

    return transaction_receipt.contractAddress, abi
