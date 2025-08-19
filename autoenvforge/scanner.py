import os
import json
import tempfile
from tenacity import retry, stop_after_attempt
import pygit2
from tree_sitter import Language, Parser
import tree_sitter_languages
from tqdm import tqdm
from . import plugins

class Scanner:
    def __init__(self, repo_input, verbose=False, cache=False):
        self.repo_input = repo_input
        self.verbose = verbose
        self.cache = cache
        self.cache_file = os.path.join(tempfile.gettempdir(), 'autoenvforge_cache.json')
        self.repo_path = None

    @retry(stop=stop_after_attempt(3))
    def scan(self, forced_lang=None):
        # Load cache if exists
        if self.cache and os.path.exists(self.cache_file):
            with open(self.cache_file, 'r') as f:
                cached = json.load(f)
            if cached.get('repo') == self.repo_input:
                if self.verbose:
                    print("Using cached scan data.")
                return cached['data']

        # Clone or use local with retry
        if self.repo_input.startswith('http'):
            self.repo_path = tempfile.mkdtemp()
            pygit2.clone_repository(self.repo_input, self.repo_path)
        else:
            self.repo_path = os.path.abspath(self.repo_input)
        if self.verbose:
            print(f"Repo path: {self.repo_path}")

        # Detect languages and subdirs
        langs, subdirs = self._detect_languages_and_subdirs()
        primary_lang = forced_lang or max(langs, key=langs.get, default='python')

        # Parse files and configs per lang/subdir
        parsed = {}
        configs = {}
        for subdir, sub_langs in tqdm(subdirs.items(), desc="Scanning subdirs", disable=not self.verbose):
            sub_path = os.path.join(self.repo_path, subdir)
            for sub_lang in sub_langs:
                parsed[subdir] = self._parse_files(sub_path, sub_lang)
                configs[subdir] = self._detect_configs(sub_path, sub_lang)

        data = {
            'repo_path': self.repo_path,
            'primary_lang': primary_lang,
            'langs': langs,
            'subdirs': subdirs,
            'parsed': parsed,
            'configs': configs  # e.g., {'/': {'requirements.txt': ['numpy==1.0']}}
        }

        # Cache results
        if self.cache:
            with open(self.cache_file, 'w') as f:
                json.dump({'repo': self.repo_input, 'data': data}, f)

        return data

    def _detect_languages_and_subdirs(self):
        langs = {'python': 0, 'js': 0, 'java': 0, 'go': 0, 'ruby': 0}
        subdirs = {'/': set()}
        for root, dirs, files in os.walk(self.repo_path):
            rel_root = os.path.relpath(root, self.repo_path)
            subdirs.setdefault(rel_root, set())
            for file in files:
                if file.endswith('.py'):
                    langs['python'] += 1
                    subdirs[rel_root].add('python')
                elif file.endswith(('.js', '.ts', '.jsx')):
                    langs['js'] += 1
                    subdirs[rel_root].add('js')
                elif file.endswith('.java'):
                    langs['java'] += 1
                    subdirs[rel_root].add('java')
                elif file.endswith('.go'):
                    langs['go'] += 1
                    subdirs[rel_root].add('go')
                elif file.endswith('.rb'):
                    langs['ruby'] += 1
                    subdirs[rel_root].add('ruby')
        if self.verbose:
            print(f"Detected langs: {langs}, subdirs: {subdirs}")
        return langs, subdirs

    def _parse_files(self, path, lang):
        if lang in plugins:
            return plugins[lang].parse(path)  # Use plugin if available
        try:
            ts_lang = Language(tree_sitter_languages.get_language(lang))
            parser = Parser(ts_lang)
        except Exception:
            if self.verbose:
                print(f"Fallback to basic parsing for {lang}")
            return {'imports': []}  # Fallback

        parsed = {'imports': [], 'functions': []}  # Extended for deeper analysis
        for root, _, files in os.walk(path):
            for file in files:
                if not any(file.endswith(ext) for ext in ts_lang.file_types): continue
                file_path = os.path.join(root, file)
                with open(file_path, 'rb') as f:
                    code = f.read()
                tree = parser.parse(code)
                # Query for imports and functions (example for Python; extend per lang)
                import_query = ts_lang.query("(import_statement) @import")
                func_query = ts_lang.query("(function_definition) @func")
                imports = [self._extract_text(code, node) for node, _ in import_query.captures(tree.root_node)]
                funcs = [self._extract_text(code, node) for node, _ in func_query.captures(tree.root_node)]
                parsed['imports'].extend(imports)
                parsed['functions'].extend(funcs)
        return parsed

    def _extract_text(self, code, node):
        return code[node.start_byte:node.end_byte].decode('utf-8', errors='ignore').strip()

    def _detect_configs(self, path, lang):
        configs = {}
        config_files = {
            'python': ['requirements.txt', 'setup.py', 'Pipfile', 'pyproject.toml'],
            'js': ['package.json', 'yarn.lock', 'package-lock.json'],
            'java': ['pom.xml', 'build.gradle'],
            'go': ['go.mod', 'go.sum'],
            'ruby': ['Gemfile', 'Gemfile.lock']
        }.get(lang, [])
        for file in config_files:
            full_path = os.path.join(path, file)
            if os.path.exists(full_path):
                with open(full_path, 'r') as f:
                    configs[file] = f.read().splitlines()
        return configs