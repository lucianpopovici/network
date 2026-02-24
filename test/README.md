# CMPv2 Server Testing Script

## Overview

This `test_cmpv2_server.sh` script is a comprehensive tool designed to test various operations of a CMPv2 (Certificate Management Protocol v2) server. It leverages the CMP functionality available in OpenSSL 3.0+ to perform initialization requests, certificate requests, key updates, revocations, and general messages. The script is highly configurable, allowing users to specify server details, authentication methods (MAC-based or signature-based), TLS settings, and the specific CMP operations to test.

CMPv2 is a robust protocol for managing X.509 digital certificates, enabling automated certificate enrollment, renewal, and revocation. This script provides a convenient way to verify the correct functioning of a CMPv2 server implementation.

## Features

*   **Comprehensive CMP Operations:** Supports the following CMP message types:
    *   **IR (Initialization Request):** Initial certificate enrollment for a new key pair.
    *   **CR (Certificate Request):** Certificate enrollment with an existing key pair.
    *   **KUR (Key Update Request):** Renewal of an existing certificate with a new key pair.
    *   **RR (Revocation Request):** Request to revoke an existing certificate.
    *   **GENM (General Message):** Used to retrieve CA certificates and other general information.
    *   **P10CR (PKCS#10 Certificate Request):** Enrollment using a pre-generated PKCS#10 CSR.
    *   **Root CA Certificate Update:** Request for updated Root CA certificates.
*   **Flexible Authentication:** Supports both:
    *   **MAC-based authentication:** Using a shared secret and reference.
    *   **Signature-based authentication:** Using a client certificate and private key.
*   **TLS Support:** Option to communicate with the CMPv2 server over HTTPS, including client certificate and trusted CA certificate configuration.
*   **Key Pair Generation:** Automatically generates RSA or ECDSA key pairs for certificate requests.
*   **Detailed Logging:** Logs all commands and output to a dedicated log file, with verbose output option for debugging.
*   **Connectivity Checks:** Verifies TCP/HTTP connectivity to the CMPv2 server before running tests.
*   **Modular Design:** Each CMP operation is encapsulated in its own test function, allowing for selective execution.
*   **Test Summary:** Provides a clear summary of passed, failed, and skipped tests.

## Requirements

*   **OpenSSL 3.0 or later:** Essential for CMP protocol support.
    *   To check your OpenSSL version: `openssl version`
*   **Bash 4.0 or later:** The script uses advanced bash features.
*   **`curl` (optional but recommended):** Used for HTTP connectivity checks.
*   **`nc` (netcat) (optional but recommended):** Used for TCP connectivity checks.
*   **`jq` (optional):** Not directly used in the provided script, but often useful for parsing JSON responses from CMP servers if you extend the script.

## Installation

1.  **Download the script:**
    ```bash
    wget https://raw.githubusercontent.com/your-repo/test_cmpv2_server.sh # Replace with actual URL
    # OR copy the content from above and save it as test_cmpv2_server.sh
    ```
2.  **Make it executable:**
    ```bash
    chmod +x test_cmpv2_server.sh
    ```
3.  **Ensure OpenSSL 3.0+ is installed and available in your PATH.**

## Usage

```bash
./test_cmpv2_server.sh [OPTIONS] [TEST...]
