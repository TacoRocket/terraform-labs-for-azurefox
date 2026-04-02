# Security Policy

## Scope

This repository contains a public OpenTofu lab for validating AzureFox against a disposable Azure
subscription. The lab intentionally provisions risky posture for testing and demonstrations.

Please do not report the following as security issues by themselves:

- public IP exposure that is clearly part of the documented lab shape
- public blob access that is clearly part of the documented lab shape
- elevated lab RBAC that is clearly part of the documented validation design

Those choices are intentional inside a disposable test subscription. What matters is whether the
repo accidentally broadens risk, leaks sensitive material, or creates unsafe defaults beyond the
documented lab boundary.

## Report A Vulnerability

If you find a real security issue in this repository or its automation:

- use GitHub's private vulnerability reporting for this repository if available
- otherwise open a GitHub issue only for non-sensitive hardening suggestions
- do not publish credentials, tokens, tenant identifiers, state files, or other sensitive artifacts
  in a public issue

Examples of issues worth reporting privately:

- accidental credential or secret exposure in the repo or workflows
- unsafe GitHub Actions permissions or supply-chain exposure
- workflow behavior that could expose sensitive lab outputs unexpectedly
- infrastructure defaults that exceed the documented lab blast radius

## Handling Guidance

When testing this repo:

- use a throwaway subscription dedicated to this lab
- avoid production or shared tenants
- treat generated proof artifacts as sensitive until reviewed, especially if they contain tenant
  identifiers, principal ids, or deployment metadata
