import os
import subprocess
import tempfile
import docker
import semver
from tqdm import tqdm
from . import plugins

class Validator:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.docker_client = docker.from_env()

    def validate(self, generated_files, repo_path):
        results = {'success': True, 'issues': [], 'per_subdir': {}, 'auto_fixes': []}
        for rel_path in tqdm(generated_files.keys(), desc="Validating", disable=not self.verbose):
            subdir = os.path.dirname(rel_path)
            lang = self._get_lang_from_path(rel_path)  # Infer from file ext
            temp_dir = tempfile.mkdtemp()
            try:
                # Copy generated file to temp
                temp_file = os.path.join(temp_dir, os.path.basename(rel_path))
                with open(temp_file, 'w') as f:
                    f.write(generated_files[rel_path])

                # Lang-specific validation in isolation
                if lang == 'python' and 'requirements.txt' in rel_path:
                    venv_path = os.path.join(temp_dir, 'venv')
                    subprocess.run(['virtualenv', venv_path], check=True, capture_output=True)
                    activate = os.path.join(venv_path, 'bin', 'activate') if os.name != 'nt' else os.path.join(venv_path, 'Scripts', 'activate.bat')
                    install_cmd = f"source {activate} && pip install -r {temp_file}"
                    try:
                        subprocess.run(install_cmd, shell=True, check=True, capture_output=True)
                    except subprocess.CalledProcessError as e:
                        results['issues'].append(f"Python install failed in {subdir}: {e.stderr.decode()}")
                        results['success'] = False
                        # Auto-fix: Try downgrading conflicting deps
                        fixed = self._auto_fix_python_conflict(e.stderr.decode(), generated_files, rel_path)
                        if fixed:
                            results['auto_fixes'].append(f"Auto-fixed Python conflict in {subdir}")

                    # Vuln check
                    safety_cmd = f"source {activate} && safety check"
                    vuln_output = subprocess.run(safety_cmd, shell=True, capture_output=True).stdout.decode()
                    if 'vulnerabilities' in vuln_output.lower():
                        results['issues'].append(f"Vulns found in {subdir}: {vuln_output}")

                elif lang == 'js' and 'package.json' in rel_path:
                    subprocess.run(['npm', 'install'], cwd=temp_dir, check=True, capture_output=True)
                    audit_output = subprocess.run(['npm', 'audit'], cwd=temp_dir, capture_output=True).stdout.decode()
                    if 'vulnerabilities' in audit_output.lower():
                        results['issues'].append(f"JS vulns in {subdir}: {audit_output}")

                # Similar for java (mvn verify), go (go mod tidy && go test), ruby (bundle install && bundle audit)
                elif lang in plugins:
                    plugin_results = plugins[lang].validate(temp_dir)
                    if not plugin_results['success']:
                        results['issues'].extend(plugin_results['issues'])
                        results['success'] = False

                # Docker validation if Dockerfile
                if 'Dockerfile' in rel_path:
                    try:
                        self.docker_client.images.build(path=temp_dir, tag='autoenvforge-validate', rm=True)
                    except docker.errors.BuildError as e:
                        results['issues'].append(f"Docker build failed: {str(e)}")
                        results['success'] = False

                results['per_subdir'][subdir] = {'success': not bool(results['issues'])}

            except Exception as e:
                results['issues'].append(f"Validation error in {subdir}: {str(e)}")
                results['success'] = False
            finally:
                # Clean up temp
                import shutil
                shutil.rmtree(temp_dir)

        if self.verbose:
            print(f"Validation results: {results}")
        return results

    def _get_lang_from_path(self, path):
        if 'requirements.txt' in path or 'pyproject.toml' in path: return 'python'
        if 'package.json' in path: return 'js'
        # Extend similarly
        return 'unknown'

    def _auto_fix_python_conflict(self, error_output, generated_files, rel_path):
        # Parse error for conflict, e.g., "numpy requires scipy<1.0 but you have 1.1"
        if 'requires' in error_output and 'but you have' in error_output:
            # Extract dep and version range
            parts = error_output.split('requires')[1].split('but you have')
            req_dep_ver = parts[0].strip()
            current_ver = parts[1].split()[1]
            # Downgrade/upgrade in generated content
            content = generated_files[rel_path]
            lines = content.splitlines()
            for i, line in enumerate(lines):
                if current_ver in line:
                    # Simple replace; use semver to find compatible
                    compatible_ver = semver.bump_patch(current_ver)  # Placeholder logic
                    lines[i] = line.replace(current_ver, compatible_ver)
                    generated_files[rel_path] = '\n'.join(lines)
                    return True
        return False