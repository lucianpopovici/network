# PyPKI — Private PKI Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![RFC 4210](https://img.shields.io/badge/RFC-4210%20CMPv2-informational)](https://www.rfc-editor.org/rfc/rfc4210)
[![RFC 8555](https://img.shields.io/badge/RFC-8555%20ACME-informational)](https://www.rfc-editor.org/rfc/rfc8555)

A self-contained, production-grade private Certificate Authority with support for two industry-standard certificate management protocols — **CMPv2** (RFC 4210) for embedded/IoT devices and **ACME** (RFC 8555) for servers and workstations — plus an Ansible role for distributing the CA certificate to client machines.

---

## Contents

| File / Directory | Description |
|---|---|
| [`pki_cmpv2_server.py`](#pki-server) | CA + CMPv2 server + ACME integration |
| [`acme_server.py`](#acme-server) | ACME server module (RFC 8555) |
| [`ca_import/`](#ansible-ca-import-role) | Ansible role to push the CA cert to client machines |
| [`LICENSE`](LICENSE) | MIT License |

---

## Features

### Certificate Authority
- Self-signed RSA-4096 root CA, auto-generated on first run
- SQLite-backed certificate store with full issuance history
- Certificate revocation with reason codes
- CRL (Certificate Revocation List) generation
- Live-reloadable configuration (`PATCH /config` or `ca/config.json`)

### CMPv2 Protocol (RFC 4210 / RFC 6712)
| Operation | Type | Description |
|---|---|---|
| Initialization Request | `ir` / `ip` | First-time certificate enrollment |
| Certification Request | `cr` / `cp` | General certificate request |
| Key Update Request | `kur` / `kup` | Certificate renewal with key rollover |
| Revocation Request | `rr` / `rp` | Certificate revocation |
| Certificate Confirmation | `certConf` / `pkiConf` | Two-phase commit |
| General Message | `genm` / `genp` | CA info query |
| PKCS#10 Request | `p10cr` / `cp` | Standard CSR submission |

### ACME Protocol (RFC 8555)
| Challenge type | Description |
|---|---|
| `http-01` | Token served at `/.well-known/acme-challenge/<token>` |
| `dns-01` | TXT record at `_acme-challenge.<domain>` |
| `tls-alpn-01` | RFC 8737 — challenge cert served on port 443 via ALPN |

Full key rollover support (RFC 8555 §7.3.5) — compatible with **acme.sh**, **certbot**, and any standard ACME client.

### TLS
- One-way TLS (`--tls`) and mutual TLS (`--mtls`)
- ALPN negotiation (RFC 7301): `http/1.1`, `h2`, `cmpc` (RFC 9483), `acme-tls/1` (RFC 8737)
- Hardened cipher suites (ECDHE+AESGCM, CHACHA20; no RC4/DES/MD5)
- TLS 1.2 minimum
- Bring-your-own certificate (`--tls-cert` / `--tls-key`)

### Ansible CA Import Role
- Installs CA into OS trust store (Debian, Ubuntu, RHEL, Fedora, macOS)
- Optional: Java cacerts (`keytool`), Python certifi, curl bundle, Mozilla NSS
- Post-install verification script deployed and run on each target
- Supports fetch-from-server, local file, or inline PEM (Vault-friendly)

---

## Requirements

```bash
pip install cryptography pyasn1 pyasn1-modules
```

Python 3.9 or later. No other runtime dependencies.

---

## Quick Start

### 1. Plain HTTP (development)

```bash
python pki_cmpv2_server.py
```

```
CMPv2 endpoint : POST http://0.0.0.0:8080/
CA certificate : GET  http://0.0.0.0:8080/ca/cert.pem
ACME directory : disabled
```

### 2. TLS + ACME (staging/production)

```bash
python pki_cmpv2_server.py \
  --tls --port 8443 \
  --tls-hostname pki.internal \
  --acme-port 8888 \
  --alpn-h2 --alpn-cmp --alpn-acme
```

### 3. Mutual TLS + bootstrap

```bash
# Start server
python pki_cmpv2_server.py \
  --mtls --port 8443 \
  --bootstrap-port 8080 \
  --acme-port 8888

# Issue a client cert via the bootstrap endpoint
curl http://localhost:8080/bootstrap?cn=myclient -o bundle.pem

# Split the bundle
openssl x509 -in bundle.pem -out client.crt
openssl pkey -in bundle.pem -out client.key

# Use it
curl --cert client.crt --key client.key \
     --cacert ./ca/ca.crt \
     https://localhost:8443/health
```

---

## PKI Server

### All CLI flags

```
positional / connection:
  --host HOST               Bind address (default: 0.0.0.0)
  --port PORT               CMPv2/HTTPS port (default: 8080)
  --ca-dir DIR              CA data directory (default: ./ca)
  --log-level LEVEL         DEBUG | INFO | WARNING | ERROR

TLS options:
  --tls                     One-way TLS (server cert only)
  --mtls                    Mutual TLS (client cert required)
  --tls-hostname HOSTNAME   SAN for auto-issued server cert (default: localhost)
  --tls-cert PATH           Path to existing PEM server certificate
  --tls-key PATH            Path to matching private key

ALPN options (RFC 7301):
  --alpn-h2                 Advertise h2 (HTTP/2)
  --alpn-cmp                Advertise cmpc (CMP over TLS, RFC 9483)
  --alpn-acme               Advertise acme-tls/1 (RFC 8737)
  --no-alpn-http            Suppress http/1.1

Bootstrap:
  --bootstrap-port PORT     Plain HTTP port for initial client cert issuance

ACME options:
  --acme-port PORT          Run ACME server on this port
  --acme-base-url URL       Public base URL for ACME links
  --acme-auto-approve-dns   Skip DNS lookup for dns-01 (testing only)

Validity periods (also changeable live via PATCH /config):
  --end-entity-days DAYS    End-entity cert lifetime (default: 365)
  --client-cert-days DAYS   mTLS client cert lifetime (default: 365)
  --tls-server-days DAYS    TLS server cert lifetime (default: 365)
  --ca-days DAYS            CA cert lifetime on first creation (default: 3650)
```

### API endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/` | CMPv2 endpoint (`application/pkixcmp`) |
| `GET` | `/ca/cert.pem` | CA certificate (PEM) |
| `GET` | `/ca/cert.der` | CA certificate (DER) |
| `GET` | `/ca/crl` | Certificate Revocation List |
| `GET` | `/api/certs` | All issued certificates (JSON) |
| `GET` | `/api/whoami` | Authenticated mTLS client identity |
| `GET` | `/config` | Current server configuration |
| `PATCH` | `/config` | Live-update configuration |
| `GET` | `/bootstrap?cn=<name>` | Issue client cert bundle (bootstrap port) |
| `GET` | `/health` | Health check |

### Live configuration

Validity periods can be changed without restarting:

```bash
# Via HTTP API
curl -X PATCH http://localhost:8080/config \
  -H "Content-Type: application/json" \
  -d '{"validity": {"end_entity_days": 90, "client_cert_days": 30}}'

# Via config file (hot-reloaded on next request)
cat ca/config.json
{
  "validity": {
    "end_entity_days": 90,
    "client_cert_days": 30,
    "tls_server_days": 365,
    "ca_days": 3650
  }
}
```

---

## ACME Server

Runs as a module integrated with the PKI server, or standalone:

```bash
# Standalone
python acme_server.py --port 8888 --ca-dir ./ca

# With dns-01 auto-approval (internal/testing only)
python acme_server.py --port 8888 --auto-approve-dns
```

### ACME endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/acme/directory` | Service discovery |
| `HEAD/GET` | `/acme/new-nonce` | Fresh replay nonce |
| `POST` | `/acme/new-account` | Create or find account |
| `POST` | `/acme/new-order` | Request certificate for identifiers |
| `POST` | `/acme/authz/<id>` | Get authorization details |
| `POST` | `/acme/challenge/<authz>/<id>` | Trigger challenge validation |
| `POST` | `/acme/order/<id>/finalize` | Submit CSR |
| `POST` | `/acme/cert/<id>` | Download certificate chain |
| `POST` | `/acme/revoke-cert` | Revoke certificate |
| `POST` | `/acme/key-change` | Account key rollover (RFC 8555 §7.3.5) |

### Using with acme.sh

```bash
# Issue via http-01 (standalone mode)
acme.sh --issue \
  --server http://pki.internal:8888/acme/directory \
  -d mydevice.internal \
  --standalone \
  --insecure          # needed until the CA is in your system trust store

# After running the Ansible role, drop --insecure:
acme.sh --issue \
  --server http://pki.internal:8888/acme/directory \
  -d mydevice.internal \
  --standalone

# Account key rollover
acme.sh --update-account \
  --server http://pki.internal:8888/acme/directory
```

### Using with certbot

```bash
certbot certonly \
  --server http://pki.internal:8888/acme/directory \
  --standalone \
  -d mydevice.internal \
  --no-verify-ssl     # until CA is trusted
```

---

## Ansible CA Import Role

Distributes the CA certificate to client machines across all major trust stores.

### Quick start

```bash
cd ca_import

# Edit inventory
vim inventory/hosts.yml

# Install system trust store only
ansible-playbook ca_import.yml \
  -e ca_import_fetch_url=http://pki.internal:8080/ca/cert.pem

# Full workstation setup (all stores)
ansible-playbook ca_import.yml \
  -e ca_import_fetch_url=http://pki.internal:8080/ca/cert.pem \
  -e ca_import_java=true \
  -e ca_import_python=true \
  -e ca_import_curl=true \
  -e ca_import_nss=true

# Remove CA from all stores
ansible-playbook ca_import.yml \
  -e ca_import_fetch_url=http://pki.internal:8080/ca/cert.pem \
  -e ca_import_remove=true

# Only verify existing trust (no changes)
ansible-playbook ca_import.yml --tags verify
```

### Supported trust stores

| Store | Platform | Flag |
|---|---|---|
| System (OS) | Debian, Ubuntu, RHEL, Fedora, macOS | `ca_import_system: true` (default) |
| Java cacerts | Any (requires `keytool`) | `ca_import_java: true` |
| Python certifi | Any (requires `pip install certifi`) | `ca_import_python: true` |
| curl / libcurl | Any | `ca_import_curl: true` |
| Mozilla NSS | Any (Firefox, Chromium) | `ca_import_nss: true` |

### Key role variables

```yaml
ca_import_fetch_url:   "http://pki.internal:8080/ca/cert.pem"
ca_import_name:        "pypki-ca"
ca_import_label:       "PyPKI Internal CA"
ca_import_system:      true
ca_import_java:        false
ca_import_python:      false
ca_import_curl:        false
ca_import_nss:         false
ca_import_remove:      false
```

Supply the CA cert three ways — fetch from server, copy a local file, or inline PEM (suitable for HashiCorp Vault integration):

```yaml
# Vault example
ca_import_pem_content: "{{ lookup('hashi_vault', 'secret/pypki/ca_pem') }}"
```

---

## CA directory layout

After first run, the `./ca` directory contains:

```
ca/
├── ca.key              Private key for the root CA (keep secret)
├── ca.crt              Root CA certificate (distribute to clients)
├── ca.crl              Certificate Revocation List
├── certificates.db     SQLite store of all issued certificates
├── acme.db             SQLite store of ACME accounts, orders, challenges
├── config.json         Live server configuration (hot-reloaded)
├── server.crt          Auto-issued TLS server certificate
└── server.key          TLS server private key
```

> **Security note:** `ca.key` and `server.key` are stored unencrypted. In production, replace with an HSM or KMS-backed key store and restrict filesystem permissions accordingly.

---

## Protocol compliance

| Standard | Description | Status |
|---|---|---|
| RFC 4210 | Certificate Management Protocol v2 | ✅ Full |
| RFC 4211 | CRMF — Certificate Request Message Format | ✅ Full |
| RFC 6712 | CMP over HTTP | ✅ Full |
| RFC 9483 | CMP Updates (ALPN `cmpc`) | ✅ ALPN only |
| RFC 8555 | ACME — Automatic Certificate Management | ✅ Full |
| RFC 8737 | ACME `tls-alpn-01` challenge | ✅ Full |
| RFC 7301 | TLS ALPN Extension | ✅ Full |
| RFC 7638 | JWK Thumbprint | ✅ Full |
| RFC 5280 | X.509 Certificates and CRL profile | ✅ Full |

---

## License

MIT — see [LICENSE](LICENSE).
