# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

---

## [0.3.0] — 2026-02-23

### Added — ACME certbot compatibility (11 RFC 8555 compliance fixes)

- **`new-account` 200 vs 201 status codes** — return `201 Created` for new
  accounts and `200 OK` for existing ones, as required by RFC 8555 §7.3
- **`onlyReturnExisting` flag** — clients that pass this flag (certbot uses it
  on reconnect) now receive `accountDoesNotExist` instead of a silent new
  account being created
- **`Link: <authz>;rel="up"` on challenge responses** — required header per
  RFC 8555 §7.5.1; certbot uses it to locate the authorization URL after
  triggering a challenge
- **`Location` header on finalize response** — RFC 8555 §7.4 requires this;
  certbot polls the order URL from this header to detect the `valid` transition
- **`Link: <directory>;rel="index"` on all error responses** — RFC 8555 §6.7
  requirement; allows clients to re-bootstrap after any error
- **`renewalInfo` stub in directory** — certbot ≥2.8 checks for this field
  (draft-ietf-acme-ari); added stub URL returning 404, which certbot treats
  as "not supported" and continues normally
- **`GET /acme/terms`** — certbot fetches the ToS URL from the directory and
  displays it to the user during registration; now returns a plaintext response
- **`GET /acme/renewal-info`** — returns a clean 404 JSON error instead of
  an unrouted 404, preventing certbot from logging parse errors
- **Unauthenticated `GET` for order, authz and cert resources** — certbot
  polls these endpoints with plain `GET` (not POST-as-GET) to track status
  changes; previously returned 404, causing certbot to stall
- **`Content-Length: 0` on revocation** — explicit empty body on `200 OK`
  revocation responses prevents client connection hang
- **`content_type` parameter on `_send_json`** — allows individual handlers
  to override the response Content-Type cleanly

### Fixed

- `create_or_find_account` now returns `(is_new: bool, account: dict)` so the
  HTTP status code can be set correctly per RFC 8555 §7.3
- Already-processed challenge responses now also include the `Link: rel="up"`
  header, not just newly-triggered ones

---

## [0.2.0] — 2026-02-23

### Added — ACME protocol (RFC 8555) + ALPN + key rollover

#### ACME server (`acme_server.py`)

- Full RFC 8555 ACME server implemented as a standalone module that shares
  the `CertificateAuthority` from `pki_cmpv2_server.py`
- SQLite-backed store for accounts, orders, authorizations, challenges and
  certificates (`ca/acme.db`)
- **Challenge types:**
  - `http-01` — real HTTP fetch to `/.well-known/acme-challenge/<token>`
  - `dns-01` — DNS TXT record lookup with optional auto-approve for internal CAs
  - `tls-alpn-01` — RFC 8737 challenge certificate with `id-pe-acmeIdentifier`
    extension, served over a dedicated SSLContext advertising `acme-tls/1`
- **Key rollover** — full RFC 8555 §7.3.5 implementation at
  `POST /acme/key-change`; double-JWS structure enforced (outer signed by old
  key, inner signed by new key); atomic database update
- **Account management** — JWK/KID flows, JWK thumbprint (RFC 7638) based
  account identity, contact storage
- **Order lifecycle** — `new-order → authz → challenge → finalize → cert`
  with background async validation thread per challenge
- **Certificate download** — `application/pem-certificate-chain` with full
  leaf + CA chain
- **Revocation** — `POST /acme/revoke-cert` authenticated by account key or
  certificate key
- Integrated into `pki_cmpv2_server.py` via `--acme-port`; can also run
  standalone

#### ALPN support (`pki_cmpv2_server.py`)

- `build_tls_context()` extended with `alpn_protocols` parameter (RFC 7301)
- Four named constants on `CertificateAuthority`:
  - `ALPN_HTTP1 = "http/1.1"`
  - `ALPN_H2    = "h2"`
  - `ALPN_CMP   = "cmpc"` (RFC 9483 — CMP over TLS)
  - `ALPN_ACME  = "acme-tls/1"` (RFC 8737)
- New CLI flags: `--alpn-h2`, `--alpn-cmp`, `--alpn-acme`, `--no-alpn-http`
- `build_acme_tls_alpn_context()` — generates a throwaway challenge
  certificate for `tls-alpn-01` with the correct `id-pe-acmeIdentifier`
  critical extension
- ALPN protocol list shown in server startup banner

#### Ansible CA import role (`ca_import/`)

- Multi-platform Ansible role for distributing the CA certificate to client
  machines
- **System trust store:** Debian/Ubuntu (`update-ca-certificates`), RHEL/Fedora
  (`update-ca-trust`), macOS (`security add-trusted-cert`)
- **Optional stores:** Java cacerts (`keytool`), Python certifi bundle, curl
  merged PEM bundle + `/etc/environment`, Mozilla NSS (`certutil`)
- Three CA cert source modes: fetch from PKI server URL, copy local file,
  inline PEM content (HashiCorp Vault compatible)
- Post-install Jinja2 verification script deployed and executed on each target
- Idempotent — safe to run repeatedly; `ca_import_remove: true` cleanly
  deregisters from all stores
- Inventory example with groups: `linux_servers`, `java_servers`,
  `python_servers`, `workstations`, `macos`, `ci_runners`

---

## [0.1.0] — 2026-02-23

### Added — Initial release

#### Certificate Authority

- Self-signed RSA-4096 root CA, auto-generated on first run
- SQLite certificate store (`ca/certificates.db`) with full issuance history
- Certificate revocation with reason codes
- CRL (Certificate Revocation List) generation and serving
- Hot-reloadable configuration via `ca/config.json` and `PATCH /config`

#### CMPv2 protocol (RFC 4210 / RFC 4211 / RFC 6712)

- Full ASN.1/DER parser and builder (no external ASN.1 library required for
  core operations; `pyasn1` used for advanced parsing)
- Supported message types: `ir`, `cr`, `kur`, `rr`, `certConf`, `genm/genp`,
  `p10cr`
- HTTP transport per RFC 6712 (`application/pkixcmp`)
- CRMF subject and public key extraction

#### TLS

- One-way TLS mode (`--tls`) — server certificate only
- Mutual TLS mode (`--mtls`) — client certificate required
- Auto-issued server TLS certificate with configurable SAN hostname
- Bring-your-own certificate (`--tls-cert` / `--tls-key`)
- Hardened cipher suites: ECDHE+AESGCM, CHACHA20; disabled RC4/DES/MD5
- TLS 1.2 minimum version
- `build_tls_context()` unified context builder for both TLS modes

#### Bootstrap endpoint

- `GET /bootstrap?cn=<name>` on a separate plain-HTTP port
- Issues a client certificate and returns PEM bundle (cert + key + CA)
- Intended for initial mTLS client onboarding on trusted networks

#### HTTP API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/` | CMPv2 endpoint |
| `GET`  | `/ca/cert.pem` | CA certificate (PEM) |
| `GET`  | `/ca/cert.der` | CA certificate (DER) |
| `GET`  | `/ca/crl` | Certificate Revocation List |
| `GET`  | `/api/certs` | All issued certificates (JSON) |
| `GET`  | `/api/whoami` | mTLS client identity |
| `GET`  | `/config` | Current configuration |
| `PATCH`| `/config` | Live configuration update |
| `GET`  | `/health` | Health check |

#### Live configuration

- `ServerConfig` class with thread-safe hot-reload from `ca/config.json`
- Priority chain: defaults ← config file ← CLI flags ← `PATCH /config`
- Configurable validity periods: end-entity, client cert, TLS server, CA
- CLI flags: `--end-entity-days`, `--client-cert-days`, `--tls-server-days`,
  `--ca-days`

#### Project

- MIT licence
- `README.md` with full CLI reference, API table, protocol compliance matrix,
  CA directory layout, and quick-start examples
- `SPDX-License-Identifier: MIT` headers on all source files

---

## Tag and release recommendations

```
v0.1.0   Initial release — CA + CMPv2 + mTLS
v0.2.0   ACME (RFC 8555) + ALPN + key rollover + Ansible CA import role
v0.3.0   certbot compatibility — 11 RFC 8555 compliance fixes
```

Since the repo currently has a single un-tagged commit containing all three
milestones, the recommended approach is:

```bash
# Tag the current state as v0.3.0 (latest)
git tag -a v0.3.0 -m "v0.3.0: certbot compatibility — 11 RFC 8555 compliance fixes"
git push origin v0.3.0

# Create a GitHub Release via CLI (requires gh)
gh release create v0.3.0 \
  --title "v0.3.0 — certbot compatibility" \
  --notes-file CHANGELOG.md

# Or create it in the browser at:
# https://github.com/lucianpopovici/network/releases/new
```

For future commits, tag each logical milestone separately so GitHub's release
history reflects the three development phases.
