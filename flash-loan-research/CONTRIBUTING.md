# Contributing to BOB-FL

Thank you for your interest in contributing to BOB-FL! This document provides guidelines and instructions for contributing to the project.

## 📋 Table of Contents

- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Code Style](#code-style)
- [Testing](#testing)
- [Documentation](#documentation)
- [Bug Reports](#bug-reports)
- [Feature Requests](#feature-requests)
- [Pull Requests](#pull-requests)

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- Git
- pip
- Virtual environment (recommended)

### Setup

1. **Fork the repository**
   ```bash
   git clone https://github.com/Cyberdude01/BOB-FL.git
   cd BOB-FL
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

5. **Run initial tests**
   ```bash
   python phase3_demo.py
   python phase4_demo.py
   python phase56_integrated_workflow.py
   ```

## 🛠️ Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Make Your Changes

- Follow the code style guidelines
- Add tests for new functionality
- Update documentation as needed
- Ensure all existing tests still pass

### 3. Test Your Changes

```bash
# Run individual phase demos
python phase3_demo.py
python phase4_demo.py
python phase56_integrated_workflow.py

# Run additional tests if available
pytest tests/
```

### 4. Commit Your Changes

```bash
git add .
git commit -m "feat: add your feature description"
```

### 5. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
# Create a pull request on GitHub
```

## 🎨 Code Style

### Python Style Guide

- Follow PEP 8 guidelines
- Use 4 spaces for indentation
- Maximum line length: 88 characters
- Use descriptive variable and function names
- Add docstrings to all public functions and classes
- Type hints are encouraged but not required

### Code Structure

- Keep functions focused and single-purpose
- Limit function length to under 50 lines
- Use meaningful variable names
- Add comments for complex logic
- Follow the existing project structure

### Example

```python
def execute_opportunity(opportunity: Opportunity, network: str) -> ExecutionResult:
    """
    Execute a flash loan opportunity on the specified network.
    
    Args:
        opportunity: The opportunity to execute
        network: Target blockchain network
        
    Returns:
        ExecutionResult with execution details
    """
    # Implementation here
    pass
```

## 🧪 Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=.

# Run specific test file
pytest tests/test_phase3.py
```

### Writing Tests

- Write tests for new functionality
- Include both positive and negative test cases
- Mock external dependencies when possible
- Use descriptive test names

### Example Test

```python
import pytest
from phase3_execution_system import Opportunity, Phase3Orchestrator

def test_opportunity_validation():
    """Test opportunity validation logic."""
    opportunity = Opportunity(
        id="test_opportunity",
        timestamp=datetime.now(),
        estimated_profit_usd=1000.0,
        liquidity_usd=50000.0,
        confidence_score=0.8
    )
    
    orchestrator = Phase3Orchestrator()
    plan = orchestrator.plan_execution("arbitrum", opportunity)
    
    assert plan["network"] == "arbitrum"
    assert "error" not in plan
```

## 📚 Documentation

### Documentation Guidelines

- Update README.md for significant changes
- Add inline comments for complex logic
- Document new APIs or configuration options
- Keep phase documentation up to date

### Adding New Phases

1. Create new phase files following existing naming conventions
2. Update the main README.md
3. Add phase-specific documentation
4. Create demo/test scripts for the new phase

## 🐛 Bug Reports

When reporting bugs, please include:

1. **Bug Description**: Clear and concise description of the issue
2. **Steps to Reproduce**: Step-by-step instructions to reproduce the bug
3. **Expected Behavior**: What should happen
4. **Actual Behavior**: What actually happens
5. **Environment**: Python version, OS, dependencies
6. **Error Messages**: Any error messages or logs

### Bug Report Template

```markdown
## Bug Description
[Describe the issue]

## Steps to Reproduce
1. [Step 1]
2. [Step 2]
3. [Step 3]

## Expected Behavior
[What should happen]

## Actual Behavior
[What actually happens]

## Environment
- Python version: [version]
- OS: [OS name and version]
- Dependencies: [list relevant dependencies]

## Error Messages
```

## ✨ Feature Requests

When requesting features, please include:

1. **Feature Description**: Clear description of the requested feature
2. **Use Case**: Why this feature is needed
3. **Implementation Suggestions**: Optional - ideas for implementation
4. **Alternatives**: Optional - any alternatives you've considered

### Feature Request Template

```markdown
## Feature Description
[Describe the feature you want]

## Use Case
[Explain why this feature would be useful]

## Implementation Suggestions
[Optional: Ideas for how this could be implemented]

## Alternatives
[Optional: Any alternatives you've considered]
```

## 🔀 Pull Requests

### Pull Request Checklist

- [ ] Code follows style guidelines
- [ ] Tests are included and passing
- [ ] Documentation is updated
- [ ] Branch is up to date with main
- [ ] PR title is descriptive
- [ ] PR description explains changes
- [ ] All checks are passing

### PR Template

```markdown
## Description
[Brief description of changes]

## Changes Made
- [Change 1]
- [Change 2]
- [Change 3]

## Testing
[Describe how changes were tested]

## Related Issues
Closes #[issue number]
```

## 🤝 Community Guidelines

- Be respectful and inclusive
- Help others when you can
- Ask questions and share knowledge
- Follow the code of conduct

## 📞 Getting Help

If you need help with contributions:
- Check the documentation
- Search existing issues
- Create a new issue with questions
- Join community discussions

---

Thank you for contributing to BOB-FL! 🎉