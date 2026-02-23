# ca_import — Ansible Role

Installs a custom CA certificate into client machine trust stores.
Designed to work with the PyPKI CMPv2 + ACME server.

## Supported platforms

| Platform | System store | Tool |
|---|---|---|
| Ubuntu / Debian | ✓ | `update-ca-certificates` |
| RHEL / CentOS / Fedora | ✓ | `update-ca-trust` |
| macOS | ✓ | `security add-trusted-cert` |
| Any (Java) | optional | `keytool` |
| Any (Python) | optional | `certifi` bundle |
| Any (curl) | optional | merged PEM + `/etc/environment` |
| Any (Firefox/Chromium) | optional | `certutil` / NSS |

## Quickstart

```bash
# 1. Edit inventory/hosts.yml with your hosts
# 2. Run the playbook
ansible-playbook ca_import.yml \
  -e ca_import_fetch_url=http://pki.internal:8080/ca/cert.pem

# Enable extra stores
ansible-playbook ca_import.yml \
  -e ca_import_fetch_url=http://pki.internal:8080/ca/cert.pem \
  -e ca_import_java=true \
  -e ca_import_python=true \
  -e ca_import_curl=true \
  -e ca_import_nss=true

# Remove the CA from all stores
ansible-playbook ca_import.yml \
  -e ca_import_fetch_url=http://pki.internal:8080/ca/cert.pem \
  -e ca_import_remove=true

# Only update a specific store (use tags)
ansible-playbook ca_import.yml --tags java

# Only run verification (no changes)
ansible-playbook ca_import.yml --tags verify
```

## Variables

| Variable | Default | Description |
|---|---|---|
| `ca_import_fetch_url` | `""` | Fetch CA cert from this URL (e.g. `http://pki:8080/ca/cert.pem`) |
| `ca_import_local_path` | `""` | Copy CA cert from this path on the controller |
| `ca_import_pem_content` | `""` | Inline PEM string (useful with Vault) |
| `ca_import_name` | `pypki-ca` | Filename used in trust stores |
| `ca_import_label` | `PyPKI Internal CA` | Display name (Keychain, NSS) |
| `ca_import_system` | `true` | Install into OS trust store |
| `ca_import_java` | `false` | Install into JVM cacerts |
| `ca_import_java_home` | `""` | JAVA_HOME (auto-detected if empty) |
| `ca_import_java_storepass` | `changeit` | Java keystore password |
| `ca_import_python` | `false` | Append to Python certifi bundle |
| `ca_import_python_bin` | `python3` | Python binary to locate certifi |
| `ca_import_curl` | `false` | Build merged bundle for curl/libcurl |
| `ca_import_nss` | `false` | Import into NSS databases (Firefox/Chromium) |
| `ca_import_macos_keychain` | `true` | Use macOS System Keychain |
| `ca_import_validate` | `true` | Validate PEM before installing |
| `ca_import_remove` | `false` | Remove instead of install |
| `ca_import_fetch_timeout` | `30` | HTTP fetch timeout (seconds) |

## Integrating with Vault

```yaml
# group_vars/all.yml
ca_import_pem_content: "{{ lookup('hashi_vault', 'secret/pypki/ca_pem') }}"
```

## How the CA URL relates to the PKI server

The PKI server exposes the CA cert at:

```
GET http://<host>:<port>/ca/cert.pem   # PEM format
GET http://<host>:<port>/ca/cert.der   # DER format
```

So for a server running at `pki.internal:8080`:

```yaml
ca_import_fetch_url: "http://pki.internal:8080/ca/cert.pem"
```

`validate_certs: false` is used intentionally during the fetch — you are
bootstrapping trust, so you cannot yet verify the server.

## File layout

```
ca_import/
├── ansible.cfg
├── ca_import.yml               # main playbook
├── inventory/
│   └── hosts.yml               # example inventory
└── roles/
    └── ca_import/
        ├── defaults/main.yml   # all variables with defaults
        ├── handlers/main.yml   # update-ca-certificates / update-ca-trust
        ├── meta/main.yml
        ├── tasks/
        │   ├── main.yml        # orchestration
        │   ├── system_debian.yml
        │   ├── system_ubuntu.yml
        │   ├── system_redhat.yml
        │   ├── system_darwin.yml
        │   ├── system_unsupported.yml
        │   ├── java.yml
        │   ├── python.yml
        │   ├── curl.yml
        │   └── nss.yml
        └── templates/
            └── verify_ca_trust.sh.j2   # post-install verification script
```
