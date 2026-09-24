# Contributing to Legends Ambient Intelligence

Thank you for your interest in contributing.

## Development Setup

1. Clone the repository and set up a virtual environment:

```sh
python -m venv .venv
source .venv/bin/activate  # Or on Windows: .venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
```

2. Run unit tests:

```sh
python -m unittest discover -s tests -p "test_*.py" -v
```

## Pull Request Guidelines

- Ensure all existing and new unit tests pass cleanly offline.
- Do not introduce em dashes (Unicode U+2014) into documentation or code comments.
- Keep the core package free of mandatory heavy GPU or PyTorch dependencies so lightweight environments and CLI operations remain instant.
