## DevOps Canary Files

This directory holds the Azure DevOps YAML canary files for the proof lab.

They are here to make the lab intent obvious, not to claim that this repo
fully provisions every Azure DevOps prerequisite by itself.

Current boundary:

- the stranger still needs a real Azure DevOps org/project/repo context
- the stranger still needs working Azure DevOps auth
- this lab owns the tracked YAML canary layer and the repo/pipeline sync seam
  where the Azure DevOps API allows it

The default proof setup is:

- project: `Azurefox Proof Lab`
- repo: `lab-proof`
- variable group: `af-proof-lab-vars`
- Azure Resource Manager service connection: `af-rg-reader`

The current canaries only need the variable group to exist; one placeholder
variable such as `LAB_PROOF_SECRET=not-real` is enough.

Use the sync helper after those prerequisites exist:

```bash
python3 scripts/sync_devops_canaries.py --org "https://dev.azure.com/<org-name>/"
```

The canaries are intentionally small and each one proves a specific AzureFox
behavior:

- `/azure-pipelines.yml`
  - direct root-YAML evidence canary
  - service connection and variable group are visible directly in the root file
- `/pipelines/template-follow.yml`
  - same-repo template-follow canary
  - the root file delegates into a local template
- `/templates/deploy-canary.yml`
  - local template that holds the Azure-facing evidence
- `/pipelines/named-target.yml`
  - explicit named-target canary for stronger `chains deployment-path` joins
