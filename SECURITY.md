# Security Policy

## Supported Versions

Only the latest version of the Firebase RTDB Lossless Restore Toolkit is supported and receives security updates. If you discover a vulnerability, please upgrade to the latest release before reporting.

| Version | Supported |
| ------- | --------- |
| >= 0.1.0 | Yes       |
| < 0.1.0  | No        |

## Reporting a Vulnerability

We take the security of this project seriously. If you believe you have found a security vulnerability, please do **NOT** open a public issue. Instead, report it privately to the maintainer:

* **Email**: [berkayturanci@gmail.com](mailto:berkayturanci@gmail.com)

Please include a detailed description of the vulnerability, including steps to reproduce, potential impact, and any suggested fixes. We will acknowledge receipt of your report within 48 hours and work with you to resolve the issue as quickly as possible.

## Verifying release artifacts

Each GitHub Release attaches the built `*.whl` and `*.tar.gz`, plus:

* `SHA256SUMS` — SHA-256 checksums of the distribution files.
* `sbom.cdx.json` — a CycloneDX Software Bill of Materials for the package and
  its dependencies.

To verify a download, place the artifacts and `SHA256SUMS` in the same directory
and run:

```bash
sha256sum -c SHA256SUMS
```

Every line should report `OK`. The SBOM can be inspected with any CycloneDX-aware
tool to review the dependency tree before installing in a sensitive environment.
