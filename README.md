# S17/G3 AI Security Compliance Review

An AI-assisted security-compliance review project using Hong Kong S17 and G3 as the initial reference corpus.

## Project documents

- [Project framework](docs/PROJECT_FRAMEWORK.md)
- [Plan and progress](docs/PROJECT_PLAN_AND_PROGRESS.md)
- [Standards inventory](docs/STANDARDS.md)

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
docs/       Project decisions, plans, and standards inventory
src/        Main application code
scripts/    Manual developer commands
tests/      Automated tests
data/       Raw, generated, and private data (not committed)
```
