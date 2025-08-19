# AutoEnvForge

[![PyPI version](https://badge.fury.io/py/autoenvforge.svg)](https://badge.fury.io/py/autoenvforge)  
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)  
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)

A robust, AI-powered one-click tool that automatically detects and sets up development environments for any GitHub repository or local project. It scans code, infers dependencies using AI, generates reproducible setups (e.g., virtual environments, Dockerfiles), resolves conflicts, and validates everything in isolated environments. Designed to handle complex scenarios like multi-language monorepos, legacy code, and dependency conflicts, reducing setup time from hours to minutes.
![AutoEnvForge - Environment Setup Tool](https://github.com/user-attachments/assets/5b6b9bf7-d540-4094-a65a-6a5d011fe95e)

## Key Features
- **Automatic Language Detection**: Supports Python, JavaScript/TypeScript, Java, Go, Ruby out-of-the-box; extensible via plugins.
- **AI-Driven Dependency Inference**: Uses pre-trained models (e.g., CodeBERT) to detect hidden dependencies, suggest versions, and provide insights (e.g., "Deprecated dep detected; auto-upgraded").
- **File Generation**: Creates/updates requirements.txt, package.json, pom.xml, go.mod, Gemfile, .env, and multi-stage Dockerfiles.
- **Conflict Resolution**: Handles version mismatches with semver, auto-locking (e.g., pip-tools, npm lock), and auto-fixes during validation.
- **Validation & Simulation**: Runs installs in isolated envs (virtualenv, nvm, etc.), checks for vulnerabilities (safety, npm audit), and simulates Docker builds.
- **Insightful Reporting**: Generates Markdown reports with previews, insights, and JSON exports for automation.
- **Zero-Touch Mode**: `--auto-apply` for fully automated setup without prompts.
- **GitHub Actions Integration**: Auto-setup on PRs or pushes.
- **Extensibility**: Plugin system for adding new languages or custom behaviors.
- **Edge Case Handling**: Multi-subdir support for monorepos, caching for speed, retries on failures, OS-agnostic (Windows/Linux/macOS).

## Target Users
- Developers cloning unfamiliar repos.
- Open-source contributors onboarding quickly.
- Teams automating CI/CD bootstrapping.
- AI/ML projects like DCPE, where PyTorch/CUDA deps are inferred automatically.

## Goals & Unique Aspects
- Achieve 95%+ accuracy for popular languages.
- Provide diagnostics like "Inferred numpy from sklearn import; confidence 0.85".
- Unlike static tools (e.g., Dependabot), it uses AI for virtual simulations and context-aware resolutions.

## Installation
AutoEnvForge is available as a Python package. Requires Python 3.12+.

### From PyPI (Recommended)
```
pip install autoenvforge
```

### From Source (For Development)
1. Clone the repo: `git clone https://github.com/yourusername/autoenvforge.git`
2. Navigate: `cd autoenvforge`
3. Install dependencies: `pip install -r requirements.txt`
4. Install: `python setup.py install` (or `pip install .`)

**Prerequisites**:
- Git (for repo cloning).
- Docker (optional, for Dockerfile generation/validation).
- Language runtimes (e.g., Node.js for JS validation, Maven for Java) assumed installed on host for full validation; tool uses subprocess.

Test installation: `autoenvforge --help`

## Usage
The tool is CLI-based. Core command: `autoenvforge init <repo-url-or-path> [options]`

### Basic Workflow
1. **Input**: Repo URL (auto-clones) or local path.
2. **Output**: Generated env files, report, and applied changes (with confirmation or auto).
3. **Process**: Scan → Infer → Generate → Validate → Report → Apply.

### CLI Options
- `--lang <python|js|java|go|ruby|auto>`: Force primary language (default: auto-detect).
- `--docker`: Generate multi-stage Dockerfile (e.g., for GPU support in PyTorch projects).
- `--auto-apply`: Zero-touch mode—no prompts, directly applies changes.
- `--preview`: Generate report/preview without applying changes.
- `--verbose`: Detailed logs and progress bars.
- `--cache`: Cache scans/inferences for faster reruns.

### Examples

#### Local Project Setup (e.g., DCPE at D:\table)
```
autoenvforge init D:\table --auto-apply --docker --verbose --cache
```
- Scans local code.
- Infers deps (e.g., torch>=2.1.0 from imports).
- Generates requirements.txt, Dockerfile (e.g., FROM pytorch/pytorch:...).
- Validates in temp virtualenv (pip install, safety check).
- Applies files to D:\table.
- Outputs report: Insights on deps, validation status.

On Windows, use quotes for paths: `autoenvforge init 'D:\table' --auto-apply`

#### GitHub Repo URL (Auto-Clones)
```
autoenvforge init https://github.com/ali-vilab/DCPE --preview --verbose
```
- Clones to temp dir.
- Previews report without changes (safe for testing).
- Use `--auto-apply` to apply in cloned dir (or copy back manually).

#### Multi-Language Monorepo
For a repo with Python in /api and JS in /web:
- Auto-detects subdirs.
- Generates per-subdir: /api/requirements.txt, /web/package.json.
- Multi-stage Dockerfile copies subdirs.

### Post-Run Steps
1. **Activate Env**:
   - Python: `python -m venv venv && venv\Scripts\activate && pip install -r requirements.txt`
   - JS: `npm install`
   - Etc. (tool validates this works).

2. **Docker Build** (If Generated):
   ```
   docker build -t myproject .
   docker run --gpus all myproject  # For GPU
   ```

3. **Manual Extras** (Tool Can't Handle):
   - Model downloads (e.g., for DCPE: Hugging Face weights).
   - Hardware drivers (e.g., CUDA).

### GitHub Actions Integration
Automate env setup on PRs/pushes. Add to `.github/workflows/autoenv.yml`:

```yaml
name: AutoEnvForge Setup
on: [push, pull_request]
jobs:
  setup-env:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Install Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.12'
    - name: Install AutoEnvForge
      run: pip install autoenvforge
    - name: Run AutoEnvForge
      run: autoenvforge init . --auto-apply --docker --verbose
    - name: Commit Changes
      run: |
        git config --local user.email "action@github.com"
        git config --local user.name "GitHub Action"
        git add .
        git commit -m "Auto: Env setup by AutoEnvForge" || echo "No changes to commit"
        git push
```

This auto-generates/commits env files on events.

## Extending with Plugins
Add support for new languages (e.g., Rust) via plugins:
1. Create `autoenvforge/plugins/rust.py`:
   ```python
   class Plugin:
       def parse(self, path):
           # Implement parsing (e.g., read Cargo.toml)
           return {'imports': []}

       def generate(self, deps, path):
           # Generate Cargo.toml, run cargo build
           pass

       def validate(self, path):
           # Run cargo test
           pass
   ```
2. Tool auto-loads on init.

## Troubleshooting
- **Missing Deps in Inference**: Rerun with --verbose; edit generated files manually. Tool's AI is pre-trained—fine-tune if needed.
- **Validation Fails**: Check report for issues (e.g., "Vuln in dep X"). Auto-fixes handle conflicts; manual downgrade if rare.
- **Windows Paths**: Use single quotes or double backslashes (e.g., D:\\table).
- **No Internet**: Tool works offline post-install (models cached); version fetches fallback to 'latest'.
- **Large Repos**: Increase timeout if scan slow; use --cache.
- **Errors**: E.g., "No tree-sitter for lang" → Fallback to basic parsing. Report bugs on GitHub.

## Development & Contributions
- **Structure**: Modular (scanner.py, inferencer.py, etc.).
- **Testing**: Run `pytest tests/test_main.py`.
- **AI Fine-Tuning**: Extend inferencer.py with custom datasets for better dep prediction.
- Contributions welcome! Fork, PR with features/tests.

## License
MIT License. See [LICENSE](LICENSE) for details.
