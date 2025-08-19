# AutoEnvForge

A robust one-click tool for auto-setting up dev environments from GitHub repos.
![AutoEnvForge - Environment Setup Tool.jpg](..%2FAutoEnvForge%20-%20Environment%20Setup%20Tool.jpg)
## Features
- Auto-detects languages (Python, JS, Java; extensible).
- AI-infers hidden deps (e.g., from code imports).
- Generates env files (requirements.txt, package.json, pom.xml, Dockerfile).
- Virtual simulation for validation (prevents broken setups).
- Insightful reports (e.g., dep rationales, warnings).
- GitHub Actions integration.

## Installation
pip install autoenvforge

## Usage
autoenvforge init <repo-url-or-path> [options]

Options:
--apply: Auto-apply generated files.
--docker: Generate Dockerfile.
--preview: Show preview without changes.
--lang <lang>: Force language (default: auto).
--verbose: Detailed output.

## GitHub Actions Example (.github/workflows/autoenv.yml)
name: AutoEnvForge
on: [pull_request]
jobs:
  setup-env:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Install AutoEnvForge
      run: pip install autoenvforge
    - name: Run AutoEnvForge
      run: autoenvforge init . --apply --docker
    - name: Commit Changes
      run: |
        git config --local user.email "action@github.com"
        git config --local user.name "GitHub Action"
        git add .
        git commit -m "Auto: Setup env with AutoEnvForge" || echo "No changes"
        git push

## Extending
Add new lang parsers in scanner.py and generators in generator.py.