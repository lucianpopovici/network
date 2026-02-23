# PyPKI — Private PKI Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![RFC 4210](https://img.shields.io/badge/RFC-4210%20CMPv2-informational)](https://www.rfc-editor.org/rfc/rfc4210)
[![RFC 8555](https://img.shields.io/badge/RFC-8555%20ACME-informational)](https://www.rfc-editor.org/rfc/rfc8555)
[![RFC 8894](https://img.shields.io/badge/RFC-8894%20SCEP-informational)](https://www.rfc-editor.org/rfc/rfc8894)
[![RFC 9480](https://img.shields.io/badge/RFC-9480%20CMPv3-informational)](https://www.rfc-editor.org/rfc/rfc9480)
[![RFC 7030](https://img.shields.io/badge/RFC-7030%20EST-informational)](https://www.rfc-editor.org/rfc/rfc7030)

A self-contained, production-grade private Certificate Authority with support for four industry-standard certificate management protocols — **CMPv2/v3** (RFC 4210 / RFC 9480) for embedded/IoT devices, **ACME** (RFC 8555) for servers and workstations, **SCEP** (RFC 8894) for network devices and MDM-enrolled endpoints, and **EST** (RFC 7030) for TLS-capable devices — plus an Ansible role for distributing the CA certificate to client machines.

---

## Contents

| File / Directory | Description |
|---|---|
| [`pki_cmpv2_server.py`](#pki-server) | CA + CMPv2/v3 server + ACME + SCEP + EST integration |
| [`acme_server.py`](#acme-server) | ACME server module (RFC 8555) |
| [`scep_server.py`](#scep-server) | SCEP server module (RFC 8894) |
| [`est_server.py`](#est-server) | EST server module (RFC 7030) |
| [`ca_import/`](#ansible-ca-import-role) | Ansible role to push the CA cert to client machines |
| [`CHANGELOG.md`](CHANGELOG.md) | Full version history |
| [`LICENSE`](LICENSE) | MIT License |

---

## Features

### Certificate Authority
- Self-signed RSA-4096 root CA, auto-generated on first run
- SQLite-backed certificate store with full issuance history
- Certificate revocation with reason codes
- CRL generation — served by CMPv2, ACME, and SCEP
- Live-reloadable configuration (`PATCH /config` or `ca/config.json`)

### CMPv2 / CMPv3 Protocol (RFC 4210 / RFC 6712 / RFC 9480)
| Operation | Type | Description |
|---|---|---|
| Initialization Request | `ir` / `ip` | First-time certificate enrollment |
| Certification Request | `cr` / `cp` | General certificate request |
| Key Update Request | `kur` / `kup` | Certificate renewal with key rollover |
| Revocation Request | `rr` / `rp` | Certificate revocation |
| Certificate Confirmation | `certConf` / `pkiConf` | Two-phase commit |
| General Message | `genm` / `genp` | CA info query |
| PKCS#10 Request | `p10cr` / `cp` | Standard CSR submission |

**CMPv3 extensions (RFC 9480) — auto-negotiated via `pvno` field:**

| Feature | Description |
|---|---|
| `pvno=3` negotiation | Server mirrors client's pvno; CMPv2 clients unaffected |
| `GetCACerts` | Returns all CA certs as `CACertSeq` (genm id-it 17) |
| `GetRootCACertUpdate` | CA cert rollover preview — `newWithNew` (genm id-it 18) |
| `GetCertReqTemplate` | Key type + extension hints for CSR construction (genm id-it 19) |
| CRL update via genm | Returns current CRL (genm id-it 21/22) |
| Extended polling | `pollReq`/`pollRep` for all message types (RFC 9480 §3.4) |
| Well-known URI | `POST/GET /.well-known/cmp[/p/<label>]` (RFC 9811) |
| Client error ack | Server acknowledges client `error` messages with `pkiconf` |

### ACME Protocol (RFC 8555)
| Challenge type | Description |
|---|---|
| `http-01` | Token served at `/.well-known/acme-challenge/<token>` |
| `dns-01` | TXT record at `_acme-challenge.<domain>` |
| `tls-alpn-01` | RFC 8737 — challenge cert served on port 443 via ALPN |

Full key rollover support (RFC 8555 §7.3.5) — compatible with **acme.sh**, **certbot**, and any standard ACME client.

### SCEP Protocol (RFC 8894)
| Operation | Description |
|---|---|
| `GetCACaps` | Advertise server capabilities (AES, SHA-256, Renewal, POST) |
| `GetCACert` | Download CA certificate |
| `PKCSReq` | Enrol — submit CSR wrapped in CMS, receive signed certificate |
| `CertPoll` | Poll for a pending certificate by transaction ID |
| `GetCert` | Retrieve an issued certificate by serial number |
| `GetCRL` | Download the current Certificate Revocation List |
| `GetNextCACert` | Preview next CA certificate (rollover) |

Compatible with **Cisco IOS**, **Juniper**, **sscep**, **Windows NDES**, **Jamf**, **Microsoft Intune**, and any RFC 8894-compliant SCEP client.

### EST Protocol (RFC 7030)
| Operation | Description |
|---|---|
| `cacerts` | Download CA certificate chain (PKCS#7) |
| `simpleenroll` | Enrol — submit PKCS#10 CSR, receive signed cert |
| `simplereenroll` | Renew with existing TLS client certificate |
| `csrattrs` | Download CSR attribute hints (key type, extensions) |
| `serverkeygen` | Server generates key pair + cert, returns `multipart/mixed` |

Authentication: **HTTP Basic** (username:password) and/or **TLS client certificate** — both active simultaneously. EST always runs over HTTPS.

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

### 2. TLS + ACME + SCEP + EST (staging/production)

```bash
python pki_cmpv2_server.py \
  --tls --port 8443 \
  --tls-hostname pki.internal \
  --acme-port 8888 \
  --scep-port 8889 --scep-challenge mysecret \
  --est-port 8444 \
  --alpn-h2 --alpn-cmp --alpn-acme
```

### 3. Mutual TLS + bootstrap + all protocols

```bash
python pki_cmpv2_server.py \
  --mtls --port 8443 \
  --bootstrap-port 8080 \
  --acme-port 8888 \
  --scep-port 8889 --scep-challenge mysecret \
  --est-port 8444 --est-user admin:secret

# Issue a client cert via the bootstrap endpoint
curl http://localhost:8080/bootstrap?cn=myclient -o bundle.pem

# Split the bundle
openssl x509 -in bundle.pem -out client.crt
openssl pkey -in bundle.pem -out client.key

# Use it with mTLS
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

CMPv3 options (RFC 9480):
  --cmpv3                   Enable CMPv3 handler (default: on)
  --no-cmpv3                Force CMPv2-only mode

EST options (RFC 7030):
  --est-port PORT           Run EST server on this port (e.g. 8444)
  --est-user USER:PASS      Add Basic auth user (repeatable)
  --est-require-auth        Require auth (Basic or TLS client cert)
  --est-tls-cert PATH       PEM server cert for EST HTTPS
  --est-tls-key PATH        PEM private key for --est-tls-cert

SCEP options:
  --scep-port PORT          Run SCEP server on this port (e.g. 8889)
  --scep-challenge SECRET   Challenge password for enrolment (empty = open)

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
| `GET` | `/bootstrap?cn=<n>` | Issue client cert bundle (bootstrap port) |
| `GET` | `/health` | Health check |
| `POST` | `/.well-known/cmp` | RFC 9811 well-known CMP endpoint |
| `POST` | `/.well-known/cmp/p/<label>` | Named CA CMP endpoint (RFC 9811) |
| `GET` | `/.well-known/cmp` | CA certificate (RFC 9811 discovery) |

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
acme.sh --issue \
  --server http://pki.internal:8888/acme/directory \
  -d mydevice.internal \
  --standalone \
  --insecure          # needed until the CA is in your system trust store
```

### Using with certbot

```bash
certbot certonly \
  --server http://pki.internal:8888/acme/directory \
  --standalone \
  -d mydevice.internal \
  --no-verify-ssl
```

---

## SCEP Server

Runs as a module integrated with the PKI server, or standalone:

```bash
# Standalone (open enrolment — no challenge)
python scep_server.py --port 8889 --ca-dir ./ca

# With challenge password
python scep_server.py --port 8889 --challenge mysecret
```

### SCEP endpoints

All operations are served at `/scep`. The server also accepts
`/cgi-bin/pkiclient.exe` and `/scep/pkiclient.exe` for compatibility
with Cisco IOS and Windows NDES clients.

| Method | `?operation=` | Description |
|---|---|---|
| `GET` | `GetCACaps` | Server capability advertisement |
| `GET` | `GetCACert` | Download CA certificate (DER) |
| `POST` | `PKCSReq` | Certificate enrolment (CMS-wrapped PKCS#10) |
| `POST` | `CertPoll` | Poll for pending certificate by transaction ID |
| `POST` | `GetCert` | Retrieve certificate by serial number |
| `POST` | `GetCRL` | Download current CRL |
| `GET` | `GetNextCACert` | Next CA certificate (rollover preview) |

### Authentication

**Challenge password** — set `--scep-challenge` to require a shared secret embedded in the PKCS#10 CSR `challengePassword` attribute. Compared using constant-time comparison to prevent timing attacks.

**Renewal without challenge** — if the requester includes a valid existing certificate (signed by this CA) in the CMS envelope, the challenge is automatically waived. This is the standard renewal flow used by MDM platforms.

### Using with sscep

```bash
# Fetch CA certificate
sscep getca -u http://pki.internal:8889/scep -c ca.crt

# Generate key + CSR
openssl genrsa -out client.key 2048
openssl req -new -key client.key -out client.csr \
  -subj "/CN=mydevice.internal"

# Enrol
sscep enroll \
  -u http://pki.internal:8889/scep \
  -c ca.crt -k client.key -r client.csr -l client.crt \
  -p mysecret

# Renew (existing cert used instead of challenge)
sscep enroll \
  -u http://pki.internal:8889/scep \
  -c ca.crt -k client.key -r client.csr -l client-renewed.crt \
  -O client.crt
```

### Using with Cisco IOS

```
crypto pki trustpoint PYPKI
 enrollment url http://pki.internal:8889/scep
 subject-name CN=router1.internal,O=MyOrg
 revocation-check none

crypto pki authenticate PYPKI
crypto pki enroll PYPKI
 password mysecret
```

### Using with Microsoft Intune / NDES

Point the SCEP URL in your Intune configuration profile to:
```
http://pki.internal:8889/scep
```
The server accepts the `/cgi-bin/pkiclient.exe` path used by NDES-compatible clients automatically.

---

## EST Server

Runs as a module integrated with the PKI server, or standalone:

```bash
# Standalone — open enrolment (no auth required)
python est_server.py --port 8444 --ca-dir ./ca

# With HTTP Basic auth user(s)
python est_server.py --port 8444 --user admin:secret --user device:pass123

# Require authentication
python est_server.py --port 8444 --user admin:secret --require-auth
```

EST always runs over HTTPS. If no `--tls-cert`/`--tls-key` are provided, a server certificate is auto-issued from the CA.

### EST endpoints

All operations are under `/.well-known/est`. A CA label variant `/.well-known/est/<label>/<op>` is also accepted.

| Method | Path | Description |
|---|---|---|
| `GET` | `/.well-known/est/cacerts` | CA chain (base64 PKCS#7) |
| `GET` | `/.well-known/est/csrattrs` | CSR attribute hints (base64 DER) |
| `POST` | `/.well-known/est/simpleenroll` | Enrol — submit PKCS#10 CSR |
| `POST` | `/.well-known/est/simplereenroll` | Renew with existing cert |
| `POST` | `/.well-known/est/serverkeygen` | Server-generated key + cert |

### Authentication

EST supports both methods simultaneously. Either is sufficient:

**HTTP Basic** — configure users with `--est-user USER:PASS` (or `--user` standalone). The server sends `401 + WWW-Authenticate` on failure.

**TLS client certificate** — the server runs with `ssl.CERT_OPTIONAL`. A certificate signed by the CA is accepted automatically; no additional configuration needed.

Use `--est-require-auth` to enforce that at least one method succeeds; omit it for open internal CAs.

### Using with curl

```bash
# 1. Download CA chain
curl --cacert ./ca/ca.crt \
  https://pki.internal:8444/.well-known/est/cacerts \
  | base64 -d > chain.p7

# 2. Get CSR attribute hints
curl --cacert ./ca/ca.crt \
  https://pki.internal:8444/.well-known/est/csrattrs \
  | base64 -d | openssl asn1parse -inform DER

# 3. Generate key + CSR
openssl genrsa -out client.key 2048
openssl req -new -key client.key -out client.csr -subj "/CN=mydevice.internal"

# 4. Enrol (Base64 DER CSR body, Basic auth)
curl -X POST --cacert ./ca/ca.crt \
  -u admin:secret \
  -H "Content-Transfer-Encoding: base64" \
  --data-binary "$(base64 client.csr)" \
  https://pki.internal:8444/.well-known/est/simpleenroll \
  | base64 -d > chain.p7

# 5. Extract certificate from PKCS#7
openssl pkcs7 -in chain.p7 -inform DER -print_certs -out client.crt

# 6. Server-generated key + cert (no CSR needed)
curl -X POST --cacert ./ca/ca.crt \
  -u admin:secret \
  https://pki.internal:8444/.well-known/est/serverkeygen \
  -o keygen_response.multipart
```

### Using with estclient (Python / Go tools)

Any RFC 7030-compliant client works. Popular options: `libest` (Cisco), `est` (Go), `python-estclient`. Point them at `https://pki.internal:8444/.well-known/est`.

---

## Ansible CA Import Role

Distributes the CA certificate to client machines across all major trust stores.

### Quick start

```bash
cd ca_import

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
| Python certifi | Any | `ca_import_python: true` |
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
├── scep.db             SQLite store of SCEP enrolment transactions
├── est/                EST TLS cert auto-issued here (if no --est-tls-cert)
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
| RFC 9483 | Lightweight CMP Profile (ALPN `cmpc`) | ✅ ALPN |
| RFC 8555 | ACME — Automatic Certificate Management | ✅ Full |
| RFC 8737 | ACME `tls-alpn-01` challenge | ✅ Full |
| RFC 8894 | SCEP — Simple Certificate Enrolment Protocol | ✅ Full |
| RFC 9480 | CMP Updates — CMPv3 features | ✅ Full |
| RFC 9811 | CMP well-known URI paths | ✅ Full |
| RFC 7030 | EST — Enrollment over Secure Transport | ✅ Full |
| RFC 7301 | TLS ALPN Extension | ✅ Full |
| RFC 7638 | JWK Thumbprint | ✅ Full |
| RFC 5280 | X.509 Certificates and CRL profile | ✅ Full |

---

## License

MIT — see [LICENSE](LICENSE).
