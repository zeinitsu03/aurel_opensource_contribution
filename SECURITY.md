# Security Policy

This page explains how to report security issues and what Aurel does with network access and tokens.

## Quick Summary

- Do not report vulnerabilities in public issues.
- Aurel does not run code from analyzed repositories.
- Aurel does not write to analyzed repositories.
- GitHub tokens are optional and are only sent to GitHub requests.
- Core analysis does not require hosted AI services, paid APIs, or secrets.

## Reporting A Vulnerability

Please do not report security vulnerabilities in public issues.

If you find a security problem in Aurel:

1. Contact the maintainers privately, or use GitHub private vulnerability reporting if it is enabled for the repository.
2. Include the affected version, reproduction steps, and impact.
3. Give the maintainers time to review before sharing details publicly.

## Supported Versions

Aurel is currently in early development. Security fixes will target the latest version on the main branch.

## Scope

The CLI reads a remote repository URL, may make unauthenticated public API requests, and can optionally use a GitHub token supplied by the user. Aurel only sends the GitHub token to GitHub requests. It does not store credentials, run untrusted repository code, or write to analyzed repositories.

## Network Behavior

Aurel needs outbound HTTPS access to the selected provider API. A `Could not reach remote provider` message means the CLI started but the network request failed because of connectivity, proxy, firewall, DNS, or provider availability. If a proxy is required, configure it in the shell environment before running Aurel.
