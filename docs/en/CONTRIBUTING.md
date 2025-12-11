# Contributing to Dingo

Thanks for your interest in contributing to Dingo! All kinds of contributions are welcome, including but not limited to the following:

* Fix typo or bugs
* Add documentation or translate the documentation into other languages
* Add new features and components
* Add new evaluation rules, prompts, or models
* Improve test coverage and performance

## What is PR

`PR` is the abbreviation of `Pull Request`. Here's the definition of `PR` in the official document of Github.

Pull requests let you tell others about changes you have pushed to a branch in a repository on GitHub. Once a pull request is opened, you can discuss and review the potential changes with collaborators and add follow-up commits before your changes are merged into the base branch.

## Basic Workflow

1. Get the most recent codebase
2. Checkout a new branch from `dev` branch
3. Commit your changes (Don't forget to use pre-commit hooks!)
4. Push your changes and create a PR
5. Discuss and review your code
6. Merge your branch to `dev` branch

## Procedures in Detail

### 1. Get the Most Recent Codebase

* **When you work on your first PR**

  Fork the Dingo repository: click the **fork** button at the top right corner of Github page

  Clone forked repository to local
  ```bash
  git clone git@github.com:XXX/dingo.git
  ```

  Add source repository to upstream
  ```bash
  git remote add upstream git@github.com:MigoXLab/dingo.git
  ```

* **After your first PR**

  Checkout the latest branch of the local repository and pull the latest branch of the source repository.
  ```bash
  git checkout dev
  git pull upstream dev
  ```

### 2. Checkout a New Branch from `dev` Branch

```bash
git checkout dev -b branchname
```

### 3. Commit Your Changes

* **If you are a first-time contributor**, please install and initialize pre-commit hooks from the repository root directory first.
  ```bash
  pip install -U pre-commit
  pre-commit install
  ```

* **Commit your changes** as usual. Pre-commit hooks will be triggered to stylize your code before each commit.
  ```bash
  # coding
  git add [files]
  git commit -m 'messages'
  ```

  > **Note**: Sometimes your code may be changed by pre-commit hooks. In this case, please remember to re-stage the modified files and commit again.

### 4. Push Your Changes to the Forked Repository and Create a PR

* **Push the branch** to your forked remote repository
  ```bash
  git push origin branchname
  ```

* **Create a PR**

  Go to your forked repository on GitHub and click "New pull request"

* **Revise PR message template** to describe your motivation and modifications made in this PR. You can also link the related issue to the PR manually in the PR message.

* **You can also ask a specific person** to review the changes you've proposed.

### 5. Discuss and Review Your Code

* Modify your codes according to reviewers' suggestions and then push your changes.

### 6. Merge Your Branch to `dev` Branch and Delete the Branch

* After the PR is merged by the maintainer, you can delete the branch you created in your forked repository.
  ```bash
  git branch -d branchname # delete local branch
  git push origin --delete branchname # delete remote branch
  ```

## Development Setup

### Environment Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/MigoXLab/dingo.git
   cd dingo
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -e .
   pip install -r requirements/runtime.txt
   ```

4. **Install pre-commit hooks**
   ```bash
   pre-commit install
   ```

### Running Tests

```bash
# Run all tests
python -m pytest test/

# Run specific test file
python -m pytest test/scripts/data/dataset/test_hf_dataset.py

# Run with coverage
python -m pytest --cov=dingo test/
```

### Running Examples

```bash
# Test CLI functionality
python -m dingo.run.cli --input test/env/local_plaintext.json

# Start local demo
cd app_gradio
python app.py
```

## Code Style

We adopt PEP8 as the preferred code style.

We use the following tools for linting and formatting:

* **flake8**: A wrapper around some linter tools
* **isort**: A Python utility to sort imports
* **black**: A formatter for Python files
* **pre-commit**: Git hooks for code quality

Style configurations can be found in `setup.cfg` and `.pre-commit-config.yaml`.

### Code Quality Guidelines

1. **Follow PEP8** for Python code style
2. **Use type hints** where appropriate
3. **Write docstrings** for all public functions and classes
4. **Keep functions small** and focused on a single responsibility
5. **Use meaningful variable names**
6. **Add comments** for complex logic

### Example Code Style

```python
from typing import List, Optional

from dingo.io.input import Data
from dingo.model.modelres import ModelRes


class ExampleRule:
    """Example rule for demonstration purposes.

    This rule checks for specific patterns in text data.

    Args:
        pattern: Regular expression pattern to match
        threshold: Minimum threshold for rule activation
    """

    def __init__(self, pattern: str, threshold: float = 0.5) -> None:
        self.pattern = pattern
        self.threshold = threshold

    def eval(self, input_data: Data) -> ModelRes:
        """Evaluate input data against the rule.

        Args:
            input_data: Input data to evaluate

        Returns:
            ModelRes: Evaluation result
        """
        res = ModelRes()
        # Implementation here
        return res
```

## Contributing Guidelines

### Adding New Features

1. **Create an issue** first to discuss the feature
2. **Follow the existing architecture** patterns
3. **Add comprehensive tests** for new functionality
4. **Update documentation** as needed
5. **Ensure backward compatibility** when possible

### Adding New Evaluation Rules

1. **Inherit from appropriate base class** (`BaseRule` for rule-based evaluation)
2. **Register your rule** using the `@Model.rule_register` decorator
3. **Add comprehensive tests** in the `test/` directory
4. **Document the rule** with clear docstrings and examples

Example:
```python
from dingo.model import Model
from dingo.model.rule.base import BaseRule
from dingo.config.input_args import EvaluatorRuleArgs
from dingo.io import Data
from dingo.model.modelres import ModelRes

@Model.rule_register('QUALITY_BAD_CUSTOM', ['default'])
class CustomRule(BaseRule):
    """Custom rule for specific quality check."""

    dynamic_config = EvaluatorRuleArgs(pattern=r'custom_pattern')

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        res = ModelRes()
        # Implementation
        return res
```

### Adding New LLM Models

1. **Inherit from appropriate base class** (`BaseOpenAI` for OpenAI-compatible APIs)
2. **Register your model** using the `@Model.llm_register` decorator
3. **Handle API keys and configuration** properly
4. **Add error handling** for API failures

### Adding New Prompts

1. **Follow existing prompt structure** in `dingo/model/prompt/`
2. **Use clear and specific prompt templates**
3. **Test prompts** with different models
4. **Document prompt purpose** and expected outputs

### Documentation

1. **Update README.md** if adding major features
2. **Add docstrings** to all public functions and classes
3. **Create examples** in the `examples/` directory
4. **Update configuration documentation** in `docs/config.md`

## Testing Guidelines

### Writing Tests

1. **Use pytest** for all tests
2. **Create test data** in `test/data/` directory
3. **Mock external dependencies** (APIs, file systems)
4. **Test edge cases** and error conditions
5. **Maintain high test coverage**

### Test Structure

```
test/
├── data/                    # Test data files
├── scripts/                 # Test scripts
├── test_rules.py           # Rule tests
├── test_models.py          # Model tests
└── test_integration.py     # Integration tests
```

### Example Test

```python
import pytest
from dingo.io.input import Data
from dingo.model.rule.rule_common import RuleContentNull


class TestRuleContentNull:
    """Test cases for RuleContentNull."""

    def test_null_content(self):
        """Test rule with null content."""
        data = Data(data_id='test', content='')
        result = RuleContentNull().eval(data)
        assert result.is_bad is True

    def test_valid_content(self):
        """Test rule with valid content."""
        data = Data(data_id='test', content='Valid content')
        result = RuleContentNull().eval(data)
        assert result.is_bad is False
```

## About Contributing Test Datasets

### Submitting Test Datasets

* Please implement logic for **automatic dataset downloading** in the code; or provide a method for obtaining the dataset in the PR
* If the dataset is not yet public, please indicate so
* Ensure datasets comply with **licensing requirements**

### Submitting Data Configuration Files

* Provide a **README** in the same directory as the data configuration
* The README should include:
  * A brief description of the dataset
  * The official link to the dataset
  * Some test examples from the dataset
  * Evaluation results of the dataset on relevant models
  * Citation of the dataset

### Dataset Integration

* Add dataset configuration to appropriate rule groups
* Test dataset with existing evaluation rules
* Document any special requirements or preprocessing steps

## Release Process

### Version Numbering

We follow semantic versioning (SemVer):
* **Major version** (X.0.0): Breaking changes
* **Minor version** (X.Y.0): New features, backward compatible
* **Patch version** (X.Y.Z): Bug fixes, backward compatible

### Release Checklist

1. Update version in `setup.py`
2. Update `CHANGELOG.md` with new features and fixes
3. Run full test suite
4. Update documentation
5. Create release PR to `main` branch
6. Tag release after merge

## Community

### Getting Help

* **GitHub Issues**: For bugs and feature requests
* **Discord**: For real-time discussion and support
* **WeChat**: For Chinese community support

### Communication Guidelines

1. **Be respectful** and inclusive
2. **Search existing issues** before creating new ones
3. **Provide clear descriptions** and reproduction steps
4. **Use appropriate labels** for issues and PRs

## License

By contributing to Dingo, you agree that your contributions will be licensed under the Apache 2.0 License.

## Acknowledgments

We appreciate all contributors who help make Dingo better! Your contributions, whether code, documentation, or feedback, are valuable to the community.

---

For more detailed information about specific components, please refer to:
* [Configuration Guide](../config.md)
* [Metrics Documentation](../metrics.md)
