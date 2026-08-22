# S17/G3 AI Security Compliance Review

An AI-assisted security-compliance review project using Hong Kong S17 and G3 as the initial reference corpus.

## Project documents

- [System framework](docs/FRAMEWORK.md)
- [Process and plan](docs/PROCESS_AND_PLAN.md)

## Python environment

This project uses Conda. After Conda is installed, create and activate the project
environment from the repository root:

```powershell
conda env create -f environment.yml
conda activate fyp-security-compliance
```

When `environment.yml` changes:

```powershell
conda env update -f environment.yml --prune
```

## Directory overview

```text
docs/       Public English architecture and roadmap documentation
src/        Main application code
scripts/    Manual developer commands
tests/      Automated tests
data/       Raw, generated, and private data (not committed)
```
