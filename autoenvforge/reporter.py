import json
from . import plugins

class Reporter:
    def __init__(self, verbose=False):
        self.verbose = verbose

    def generate_report(self, scanned_data, inferred_deps, validation_results, generated_files):
        report = "# AutoEnvForge Comprehensive Report\n\n"
        report += "## Scanned Repo Overview\n"
        report += f"- Primary Language: {scanned_data['primary_lang']}\n"
        report += f"- Detected Languages: {scanned_data['langs']}\n"
        report += f"- Subdirectories: {list(scanned_data['subdirs'].keys())}\n\n"

        report += "## Inferred Dependencies and Insights\n"
        for subdir, sub_inferred in inferred_deps['per_subdir'].items():
            report += f"### {subdir or 'Root'}\n"
            report += "#### Dependencies\n" + "\n".join([f"- {dep}@{ver}" for dep, ver in sub_inferred['deps'].items()]) + "\n"
            report += "#### Hidden Deps\n" + "\n".join(sub_inferred['hidden']) + "\n"
            report += "#### Insights and Conflicts\n" + "\n".join(sub_inferred['insights'] + inferred_deps['conflicts']) + "\n\n"

        report += "## Generated Files\n" + "\n".join([f"- {path}" for path in generated_files.keys()]) + "\n\n"

        report += "## Validation Results\n"
        if validation_results['success']:
            report += "All checks passed.\n"
        else:
            report += "Issues found:\n" + "\n".join(validation_results['issues']) + "\n"
            if validation_results['auto_fixes']:
                report += "Auto-fixes applied:\n" + "\n".join(validation_results['auto_fixes']) + "\n"
        for subdir, res in validation_results['per_subdir'].items():
            report += f"- {subdir}: {'Passed' if res['success'] else 'Failed'}\n"

        # JSON export for automation
        json_data = {
            'scanned': scanned_data,
            'inferred': inferred_deps,
            'validation': validation_results,
            'generated': list(generated_files.keys())
        }
        with open(os.path.join(scanned_data['repo_path'], 'autoenvforge_report.json'), 'w') as f:
            json.dump(json_data, f, indent=2)

        return report