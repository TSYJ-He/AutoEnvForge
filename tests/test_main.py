import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock
from autoenvforge.main import cli
from autoenvforge.scanner import Scanner

@pytest.fixture
def runner():
    return CliRunner()

def test_init_preview(runner):
    result = runner.invoke(cli, ['init', 'mock_repo', '--preview'])
    assert result.exit_code == 0
    assert 'Preview' in result.output

@patch('autoenvforge.scanner.pygit2.clone_repository')
def test_scanner_clone(mock_clone, tmp_path):
    mock_repo_path = tmp_path / 'repo'
    mock_clone.return_value = MagicMock(path=str(mock_repo_path))
    scanner = Scanner('https://github.com/mock', verbose=False)
    data = scanner.scan()
    assert data['repo_path'] == str(mock_repo_path)  # Simplified

def test_inferencer_merge():
    # Add more tests for merge, resolution, etc.
    pass  # Expand as needed

# Run with pytest tests/test_main.py