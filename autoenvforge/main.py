import click
from tenacity import retry, stop_after_attempt, wait_fixed
from tqdm import tqdm
from .scanner import Scanner
from .inferencer import Inferencer
from .generator import Generator
from .validator import Validator
from .reporter import Reporter
from . import plugins  # Loaded from __init__

@click.group()
def cli():
    pass

@cli.command()
@click.argument('repo', required=True)
@click.option('--lang', default='auto', help='Primary language or "auto"')
@click.option('--docker', is_flag=True, help='Generate multi-stage Dockerfile')
@click.option('--auto-apply', is_flag=True, help='Apply without any confirmation (zero-touch)')
@click.option('--preview', is_flag=True, help='Preview report without applying')
@click.option('--verbose', is_flag=True, help='Detailed output')
@click.option('--cache', is_flag=True, help='Use/ update dep cache for faster inference')
def init(repo, lang, docker, auto_apply, preview, verbose, cache):
    with tqdm(total=5, desc="AutoEnvForge Progress", disable=not verbose) as pbar:
        try:
            scanner = Scanner(repo, verbose, cache)
            pbar.update(1)
            scanned_data = scanner.scan(lang if lang != 'auto' else None)

            inferencer = Inferencer(verbose, cache)
            pbar.update(1)
            inferred_deps = inferencer.infer(scanned_data)

            generator = Generator(verbose)
            pbar.update(1)
            generated_files = generator.generate(scanned_data, inferred_deps, docker)

            validator = Validator(verbose)
            pbar.update(1)
            validation_results = validator.validate(generated_files, scanned_data['repo_path'])

            reporter = Reporter(verbose)
            pbar.update(1)
            report = reporter.generate_report(scanned_data, inferred_deps, validation_results, generated_files)

            if verbose or preview:
                click.echo(report)

            if preview:
                click.echo("Preview mode: No changes applied.")
                return

            if auto_apply or click.confirm("Apply generated env? (y/n)"):
                generator.apply(generated_files, scanned_data['repo_path'])
                click.echo("Env applied successfully.")
            else:
                click.echo("Changes not applied.")
        except Exception as e:
            click.echo(f"Error: {str(e)}", err=True)

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def safe_operation(func, *args, **kwargs):
    return func(*args, **kwargs)  # Wrapper for retries in modules

if __name__ == '__main__':
    cli()