#!/bin/bash
#
# CMPv2 Server Testing Script
# This script tests various CMPv2 (Certificate Management Protocol v2) operations
# against a CMPv2 server using OpenSSL 3.0+ CMP functionality.
#
# Requirements:
#   - OpenSSL 3.0 or later (with CMP support)
#   - curl (for HTTP connectivity checks)
#   - jq (optional, for JSON parsing)
#
# Usage: ./test_cmpv2_server.sh [options]
#
# Author: CodeGuruX
# License: MIT
#

set -euo pipefail

# =============================================================================
# Configuration - Modify these values for your CMPv2 server
# =============================================================================

# CMPv2 Server Configuration
CMP_SERVER="${CMP_SERVER:-cmp.example.com}"
CMP_PORT="${CMP_PORT:-8080}"
CMP_PATH="${CMP_PATH:-/cmp}"
CMP_URL="http://${CMP_SERVER}:${CMP_PORT}${CMP_PATH}"

# TLS Configuration (if using HTTPS)
USE_TLS="${USE_TLS:-false}"
TLS_CERT="${TLS_CERT:-}"
TLS_KEY="${TLS_KEY:-}"
TLS_CACERT="${TLS_CACERT:-}"

# CMP Authentication
CMP_REFERENCE="${CMP_REFERENCE:-}"
CMP_SECRET="${CMP_SECRET:-}"
CMP_CERT="${CMP_CERT:-}"
CMP_KEY="${CMP_KEY:-}"

# Certificate Subject
CERT_SUBJECT="${CERT_SUBJECT:-/CN=test-client/O=Test Organization/C=US}"

# CA Certificate (for verification)
CA_CERT="${CA_CERT:-ca-cert.pem}"

# Output directory
OUTPUT_DIR="${OUTPUT_DIR:-./cmpv2_test_output}"

# Logging
LOG_FILE="${LOG_FILE:-${OUTPUT_DIR}/cmpv2_test.log}"
VERBOSE="${VERBOSE:-false}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# =============================================================================
# Helper Functions
# =============================================================================

log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    case "$level" in
        INFO)  echo -e "${BLUE}[INFO]${NC} ${message}" ;;
        OK)    echo -e "${GREEN}[OK]${NC} ${message}" ;;
        WARN)  echo -e "${YELLOW}[WARN]${NC} ${message}" ;;
        ERROR) echo -e "${RED}[ERROR]${NC} ${message}" ;;
        DEBUG) [[ "$VERBOSE" == "true" ]] && echo -e "[DEBUG] ${message}" ;;
    esac
    
    echo "[${timestamp}] [${level}] ${message}" >> "${LOG_FILE}"
}

check_prerequisites() {
    log INFO "Checking prerequisites..."
    
    # Check OpenSSL version
    if ! command -v openssl &> /dev/null; then
        log ERROR "OpenSSL is not installed"
        exit 1
    fi
    
    local openssl_version
    openssl_version=$(openssl version | awk '{print $2}')
    local major_version
    major_version=$(echo "$openssl_version" | cut -d. -f1)
    
    if [[ "$major_version" -lt 3 ]]; then
        log ERROR "OpenSSL 3.0+ is required for CMP support (found: $openssl_version)"
        log INFO "Please upgrade OpenSSL or use a container with OpenSSL 3.0+"
        exit 1
    fi
    
    log OK "OpenSSL version: $openssl_version"
    
    # Check if CMP is supported
    if ! openssl cmp -help &> /dev/null; then
        log ERROR "OpenSSL CMP module is not available"
        exit 1
    fi
    
    log OK "OpenSSL CMP module is available"
    
    # Check curl
    if ! command -v curl &> /dev/null; then
        log WARN "curl is not installed - some connectivity checks will be skipped"
    fi
}

setup_output_dir() {
    log INFO "Setting up output directory: ${OUTPUT_DIR}"
    mkdir -p "${OUTPUT_DIR}"
    mkdir -p "${OUTPUT_DIR}/certs"
    mkdir -p "${OUTPUT_DIR}/keys"
    mkdir -p "${OUTPUT_DIR}/requests"
}

generate_key_pair() {
    local key_file="$1"
    local key_type="${2:-RSA}"
    local key_size="${3:-2048}"
    
    log INFO "Generating ${key_type} key pair (${key_size} bits)..."
    
    case "$key_type" in
        RSA)
            openssl genrsa -out "${key_file}" "${key_size}" 2>/dev/null
            ;;
        EC|ECDSA)
            openssl ecparam -name prime256v1 -genkey -noout -out "${key_file}" 2>/dev/null
            ;;
        *)
            log ERROR "Unsupported key type: ${key_type}"
            return 1
            ;;
    esac
    
    if [[ -f "${key_file}" ]]; then
        log OK "Key pair generated: ${key_file}"
        return 0
    else
        log ERROR "Failed to generate key pair"
        return 1
    fi
}

test_connectivity() {
    log INFO "Testing connectivity to CMPv2 server: ${CMP_SERVER}:${CMP_PORT}"
    
    # Test basic TCP connectivity
    if command -v nc &> /dev/null; then
        if nc -z -w5 "${CMP_SERVER}" "${CMP_PORT}" 2>/dev/null; then
            log OK "TCP connection to ${CMP_SERVER}:${CMP_PORT} successful"
        else
            log ERROR "Cannot connect to ${CMP_SERVER}:${CMP_PORT}"
            return 1
        fi
    elif command -v curl &> /dev/null; then
        if curl -s --connect-timeout 5 "${CMP_URL}" -o /dev/null 2>/dev/null; then
            log OK "HTTP connection to ${CMP_URL} successful"
        else
            log WARN "HTTP connection test failed (server may still be reachable)"
        fi
    else
        log WARN "Neither nc nor curl available - skipping connectivity test"
    fi
}

# =============================================================================
# CMPv2 Test Functions
# =============================================================================

# Build common OpenSSL CMP options
build_cmp_options() {
    local opts=""
    
    opts+="-server ${CMP_SERVER}:${CMP_PORT}${CMP_PATH} "
    
    if [[ "$USE_TLS" == "true" ]]; then
        opts+="-tls_used "
        [[ -n "$TLS_CERT" ]] && opts+="-tls_cert ${TLS_CERT} "
        [[ -n "$TLS_KEY" ]] && opts+="-tls_key ${TLS_KEY} "
        [[ -n "$TLS_CACERT" ]] && opts+="-tls_trusted ${TLS_CACERT} "
    fi
    
    # Authentication options
    if [[ -n "$CMP_REFERENCE" && -n "$CMP_SECRET" ]]; then
        opts+="-ref ${CMP_REFERENCE} -secret ${CMP_SECRET} "
    elif [[ -n "$CMP_CERT" && -n "$CMP_KEY" ]]; then
        opts+="-cert ${CMP_CERT} -key ${CMP_KEY} "
    fi
    
    # CA certificate for verification
    [[ -f "$CA_CERT" ]] && opts+="-trusted ${CA_CERT} "
    
    echo
