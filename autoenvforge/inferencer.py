import os
import json
import semver
import requests  # For fetching latest versions (offline fallback)
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
import torch
from tqdm import tqdm
from . import plugins

class Inferencer:
    def __init__(self, verbose=False, cache=False):
        self.verbose = verbose
        self.cache = cache
        self.cache_file = os.path.join(os.path.dirname(__file__), 'dep_cache.json')
        self.model_name = "huggingface/CodeBERTa-small-v1"  # Lightweight code model
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(self.model_name, num_labels=10)  # Multi-label for dep types
        self.pipeline = pipeline("text-classification", model=self.model, tokenizer=self.tokenizer, device=0 if torch.cuda.is_available() else -1, top_k=None)

    def infer(self, scanned_data):
        # Load cache
        if self.cache and os.path.exists(self.cache_file):
            with open(self.cache_file, 'r') as f:
                cached = json.load(f)
            if cached.get('hash') == hash(str(scanned_data)):  # Simple hash check
                if self.verbose:
                    print("Using cached inference.")
                return cached['inferred']

        inferred = {
            'deps': {},  # {dep: version}
            'hidden': [],  # Implied deps
            'conflicts': [],  # Resolved issues
            'insights': [],  # Explanations
            'per_subdir': {}  # For monorepos
        }

        for subdir, parsed in tqdm(scanned_data['parsed'].items(), desc="Inferring deps", disable=not self.verbose):
            sub_inferred = {'deps': {}, 'hidden': [], 'insights': []}
            configs = scanned_data['configs'].get(subdir, {})
            lang = list(scanned_data['subdirs'][subdir])[0] if subdir in scanned_data['subdirs'] else scanned_data['primary_lang']

            # Merge existing configs
            existing_deps = self._merge_existing_configs(configs, lang)

            # AI inference on parsed code
            for imp in parsed['imports']:
                # Prompt for AI: Predict dep, version, hidden
                prompt = f"Predict dependencies for import '{imp}' in {lang} code. Suggest version and hidden deps."
                results = self.pipeline(prompt)[0]  # Returns list of labels/scores
                for result in results:
                    if result['score'] > 0.7:  # High confidence
                        dep = result['label']  # Assume model labels like 'numpy:1.26'
                        version = dep.split(':')[-1] if ':' in dep else 'latest'
                        sub_inferred['deps'][dep.split(':')[0]] = version
                        sub_inferred['insights'].append(f"Inferred {dep} from {imp} with score {result['score']:.2f}")

                # Hidden/recursive: Rule + AI
                hidden = self._infer_hidden(imp, lang)
                sub_inferred['hidden'].extend(hidden)

            # Merge existing and inferred
            for dep, ver in existing_deps.items():
                if dep in sub_inferred['deps']:
                    resolved_ver = self._resolve_version_conflict(ver, sub_inferred['deps'][dep], dep, lang)
                    sub_inferred['deps'][dep] = resolved_ver
                    if ver != resolved_ver:
                        inferred['conflicts'].append(f"Resolved {dep} from {ver} to {resolved_ver}")
                else:
                    sub_inferred['deps'][dep] = ver

            # Fetch latest if 'latest'
            for dep in list(sub_inferred['deps'].keys()):
                if sub_inferred['deps'][dep] == 'latest':
                    sub_inferred['deps'][dep] = self._get_latest_version(dep, lang)

            # Check deprecations/vulns (basic)
            for dep, ver in sub_inferred['deps'].items():
                if self._is_deprecated(dep, ver, lang):
                    sub_inferred['insights'].append(f"Deprecated: {dep}@{ver}; suggest upgrade")
                    # Auto-suggest upgrade
                    latest = self._get_latest_version(dep, lang)
                    if semver.compare(latest, ver) > 0:
                        sub_inferred['deps'][dep] = latest
                        inferred['conflicts'].append(f"Auto-upgraded {dep} to {latest}")

            inferred['per_subdir'][subdir] = sub_inferred
            inferred['deps'].update(sub_inferred['deps'])
            inferred['hidden'].extend(sub_inferred['hidden'])
            inferred['insights'].extend(sub_inferred['insights'])

        # Cache
        if self.cache:
            with open(self.cache_file, 'w') as f:
                json.dump({'hash': hash(str(scanned_data)), 'inferred': inferred}, f)

        if self.verbose:
            print(f"Inferred: {json.dumps(inferred, indent=2)}")
        return inferred

    def _merge_existing_configs(self, configs, lang):
        merged = {}
        if lang == 'python' and 'requirements.txt' in configs:
            for line in configs['requirements.txt']:
                if '==' in line:
                    dep, ver = line.split('==')
                    merged[dep.strip()] = ver.strip()
        # Similar for other langs (js: parse package.json JSON, etc.)
        elif lang == 'js' and 'package.json' in configs:
            try:
                pkg = json.loads('\n'.join(configs['package.json']))
                merged.update(pkg.get('dependencies', {}))
                merged.update(pkg.get('devDependencies', {}))
            except json.JSONDecodeError:
                pass
        # Extend for java, go, ruby using plugins or parsers
        return merged

    def _infer_hidden(self, imp, lang):
        # Rule-based examples
        rules = {
            'python': {'numpy': ['scipy', 'matplotlib'], 'sklearn': ['numpy', 'scipy']},
            'js': {'react': ['react-dom'], 'express': ['body-parser']}
        }
        return rules.get(lang, {}).get(imp, [])

    def _resolve_version_conflict(self, ver1, ver2, dep, lang):
        try:
            if semver.valid(ver1) and semver.valid(ver2):
                return max(ver1, ver2, key=semver.VersionInfo.parse)
            else:
                return ver2  # Prefer inferred
        except ValueError:
            return 'latest'

    def _get_latest_version(self, dep, lang):
        # Offline fallback to 'latest'; online if possible
        try:
            if lang == 'python':
                resp = requests.get(f"https://pypi.org/pypi/{dep}/json", timeout=2)
                return resp.json()['info']['version']
            # Similar for npm, maven, etc.
        except Exception:
            return 'latest'

    def _is_deprecated(self, dep, ver, lang):
        # Basic check; extend with DB or API
        deprecated = {'python': {'tensorflow': '<2.0'}}
        return dep in deprecated.get(lang, {}) and semver.compare(ver, deprecated[lang][dep].lstrip('<')) < 0