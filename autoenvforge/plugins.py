# plugins.py: Dict of lang plugins; load dynamically if folder exists
plugins = {}
try:
    import importlib.util
    import os
    plugin_dir = os.path.join(os.path.dirname(__file__), 'plugins')
    if os.path.exists(plugin_dir):
        for file in os.listdir(plugin_dir):
            if file.endswith('.py') and file != '__init__.py':
                lang = file[:-3]
                spec = importlib.util.spec_from_file_location(lang, os.path.join(plugin_dir, file))
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                plugins[lang] = module.Plugin()  # Assume each has a Plugin class with parse/generate/validate
except Exception:
    pass
class GoPlugin:
    def parse(self, path):
        # Simple go mod parse
        imports = []
        if os.path.exists(os.path.join(path, 'go.mod')):
            with open(os.path.join(path, 'go.mod'), 'r') as f:
                for line in f:
                    if line.startswith('require'):
                        imports.append(line.split()[1])
        return {'imports': imports}

    def generate(self, deps, path):
        # Run go mod init/tidy
        subprocess.run(['go', 'mod', 'init', 'autoenvforge'], cwd=path, capture_output=True)
        with open(os.path.join(path, 'go.mod'), 'a') as f:
            for dep in deps:
                f.write(f"require {dep}\n")
        subprocess.run(['go', 'mod', 'tidy'], cwd=path, check=True, capture_output=True)
        return {'go.mod': 'Generated and tidied'}

    def validate(self, path):
        try:
            subprocess.run(['go', 'test', './...'], cwd=path, check=True, capture_output=True)
            return {'success': True, 'issues': []}
        except subprocess.CalledProcessError as e:
            return {'success': False, 'issues': [str(e)]}

plugins['go'] = GoPlugin()

class RubyPlugin:
    def parse(self, path):
        gems = []
        if os.path.exists(os.path.join(path, 'Gemfile')):
            with open(os.path.join(path, 'Gemfile'), 'r') as f:
                for line in f:
                    if line.startswith('gem'):
                        gems.append(line.split()[1].strip("'\""))
        return {'imports': gems}  # Gems as imports

    def generate(self, deps, path):
        with open(os.path.join(path, 'Gemfile'), 'w') as f:
            f.write("source 'https://rubygems.org'\n")
            for dep, ver in deps.items():
                f.write(f"gem '{dep}', '{ver}'\n")
        subprocess.run(['bundle', 'install'], cwd=path, check=True, capture_output=True)
        return {'Gemfile': 'Generated', 'Gemfile.lock': 'Locked'}

    def validate(self, path):
        audit_output = subprocess.run(['bundle', 'audit'], cwd=path, capture_output=True).stdout.decode()
        issues = []
        if 'vulnerabilities' in audit_output.lower():
            issues.append(audit_output)
        return {'success': not bool(issues), 'issues': issues}

plugins['ruby'] = RubyPlugin()
