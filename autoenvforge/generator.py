import os
import subprocess
import docker
import semver
from jinja2 import Template  # Add to requirements: jinja2==3.1.4
from tqdm import tqdm

class Generator:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.docker_client = docker.from_env()
    def generate(self, scanned_data, inferred_deps, generate_docker=False):
        generated_files = {}
        for subdir, sub_inferred in tqdm(inferred_deps['per_subdir'].items(), desc="Generating files", disable=not self.verbose):
            lang = list(scanned_data['subdirs'][subdir])[0] if subdir in scanned_data['subdirs'] else scanned_data['primary_lang']
            sub_path = os.path.join(scanned_data['repo_path'], subdir)

            # Generate lang-specific files with templates
            if lang == 'python':
                req_content = self._generate_python_reqs(sub_inferred['deps'])
                generated_files[os.path.join(subdir, 'requirements.txt')] = req_content
                # Auto-lock with poetry or pip-tools
                self._lock_python(sub_path, req_content)
                generated_files[os.path.join(subdir, 'requirements.lock')] = "Locked via pip-tools"  # Placeholder; actual lock file generated

            elif lang == 'js':
                pkg_content = self._generate_js_package(sub_inferred['deps'])
                generated_files[os.path.join(subdir, 'package.json')] = pkg_content
                # Run npm install for lock
                self._lock_js(sub_path)

            # Similar for java (pom.xml template), go (go mod init/tidy), ruby (Gemfile)
            # Use Jinja for templates
            template = Template("<!-- Example for {{lang}} -->")
            generated_files[os.path.join(subdir, f'build.{lang}')] = template.render(lang=lang, deps=sub_inferred['deps'])

            # .env for secrets (inferred from code, e.g., os.getenv calls)
            env_content = self._generate_env(parsed=scanned_data['parsed'][subdir])
            if env_content:
                generated_files[os.path.join(subdir, '.env')] = env_content

        # Multi-stage Dockerfile for monorepos
        if generate_docker:
            docker_content = self._generate_multi_docker(scanned_data, inferred_deps)
            generated_files['Dockerfile'] = docker_content

        return generated_files

    def _generate_python_reqs(self, deps):
        return "\n".join([f"{dep}=={ver}" for dep, ver in deps.items()])

    def _lock_python(self, sub_path, req_content):
        with open(os.path.join(sub_path, 'requirements.txt'), 'w') as f:
            f.write(req_content)
        try:
            subprocess.run(['poetry', 'lock'], cwd=sub_path, check=True, capture_output=True)
        except Exception:
            # Fallback to pip-compile (assume pip-tools installed)
            subprocess.run(['pip-compile', 'requirements.txt'], cwd=sub_path, check=True, capture_output=True)

    def _generate_js_package(self, deps):
        return json.dumps({
            "name": "auto-generated",
            "version": "1.0.0",
            "dependencies": {dep: ver for dep, ver in deps.items()}
        }, indent=2)

    def _lock_js(self, sub_path):
        try:
            subprocess.run(['npm', 'install', '--package-lock-only'], cwd=sub_path, check=True, capture_output=True)
        except Exception:
            pass  # Handle yarn if detected

    def _generate_env(self, parsed):
        # Infer from code, e.g., os.getenv('API_KEY')
        envs = []
        for func in parsed.get('functions', []):
            if 'getenv' in func or 'process.env' in func:
                var = func.split('(')[1].split(')')[0].strip("'\"")
                envs.append(f"{var}=your_value_here")
        return "\n".join(envs) if envs else ""

    def _generate_multi_docker(self, scanned_data, inferred_deps):
        stages = []
        for subdir, langs in scanned_data['subdirs'].items():
            for lang in langs:
                base = {'python': 'python:3.12', 'js': 'node:20', 'java': 'openjdk:21'}.get(lang, 'ubuntu:latest')
                stages.append(f"FROM {base} AS {lang}_{subdir.replace('/', '_')}\nCOPY {subdir} /app/{subdir}\nWORKDIR /app/{subdir}\nRUN install_deps_command")
        return "\n".join(stages) + "\nFROM ubuntu:latest\nCOPY --from=previous_stages /app /app\nCMD ['run_all']"  # Simplified multi-stage

    def apply(self, generated_files, repo_path):
        for rel_path, content in generated_files.items():
            full_path = os.path.join(repo_path, rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w') as f:
                f.write(content)
            if self.verbose:
                print(f"Applied {rel_path}")
