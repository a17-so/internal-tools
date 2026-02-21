# Contributing to Auto-Commenter

Thank you for your interest in contributing to Auto-Commenter! This document provides guidelines for contributing to the project.

---

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [How to Contribute](#how-to-contribute)
- [Code Style Guidelines](#code-style-guidelines)
- [Adding New Platforms](#adding-new-platforms)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)

---

## Getting Started

Before contributing, please:

1. Read the [README.md](README.md) to understand the project
2. Check existing [issues](../../issues) and [pull requests](../../pulls)
3. Set up your development environment

---

## Development Setup

### Prerequisites

- Claude Desktop or Claude CLI
- Playwright MCP server
- Node.js (for MCP setup)
- Git

### Installation Steps

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/auto-commenter.git
   cd auto-commenter
   ```

3. Set up MCP:
   ```bash
   npm install
   ```

4. Create your personalization file (see README.md)

---

## Project Structure

```
auto-commenter/
├── .claude/skills/reddit-commenter/  # Reddit automation skill
│   ├── SKILL.md                      # Single comment workflow
│   ├── BATCH.md                      # Batch mode workflow
│   └── resources/                    # Configuration files
├── tracking/reddit/                  # Activity tracking
├── leads/                            # Lead management
└── README.md                         # Documentation
```

---

## How to Contribute

### Types of Contributions

1. **Bug Reports**: Found a bug? Open an issue with:
   - Clear title and description
   - Steps to reproduce
   - Expected vs actual behavior
   - Your environment details

2. **Feature Requests**: Have an idea? Open an issue with:
   - Clear use case
   - Proposed solution
   - Alternative solutions considered

3. **Code Contributions**:
   - Bug fixes
   - New features
   - Documentation improvements
   - Platform additions (Twitter, LinkedIn, etc.)

### Before You Start

- Check if an issue already exists
- For major changes, open an issue first to discuss
- Make sure your idea aligns with project goals

---

## Code Style Guidelines

### Markdown Files

- Use clear, concise language
- Include examples where appropriate
- Use tables for structured data
- Keep line length reasonable (80-100 characters when possible)

### Documentation

- All new features must include documentation
- Update README.md if adding major features
- Include inline comments for complex logic
- Keep documentation up-to-date with code changes

### Personalization Files

- Must follow the template structure
- Include diverse examples (short, long, various tones)
- Provide clear criteria for each checklist item
- Avoid overly specific personal details

---

## Adding New Platforms

To add support for a new platform (e.g., Twitter, LinkedIn):

### 1. Create Platform Structure

```bash
mkdir -p .claude/skills/[platform]-commenter/resources
mkdir -p tracking/[platform]
```

### 2. Create Required Files

- `.claude/skills/[platform]-commenter/SKILL.md` - Single comment workflow
- `.claude/skills/[platform]-commenter/BATCH.md` - Batch workflow
- `.claude/skills/[platform]-commenter/resources/personalization_[platform].md` - Style guide
- `.claude/skills/[platform]-commenter/resources/subreddits.md` - Community guide (adapt naming)
- `.claude/skills/[platform]-commenter/resources/product.md` - Product info template
- `tracking/[platform]/template.md` - Tracking template
- `leads/[platform].md` - Leads template

### 3. Adapt for Platform Specifics

Consider:
- Character limits (e.g., Twitter's 280 chars)
- Platform-specific features (threads, hashtags, etc.)
- API limitations
- Rate limiting rules
- Community guidelines

### 4. Update Documentation

- Add platform to main README.md
- Create platform-specific setup guide
- Update CONTRIBUTING.md with platform-specific notes

### 5. Test Thoroughly

- Test single comment workflow
- Test batch mode
- Verify personalization works
- Check rate limiting behavior

---

## Testing

### Manual Testing Checklist

Before submitting a PR:

- [ ] Single comment creation works
- [ ] Batch mode works
- [ ] Personalization checklist is applied
- [ ] Tracking files are updated correctly
- [ ] Lead identification works
- [ ] No personal information in commits
- [ ] Documentation is clear and accurate

### Testing Your Changes

1. Create a test tracking file
2. Run single comment workflow
3. Verify output matches expected behavior
4. Check that personalization is applied
5. Test edge cases (no suitable posts, rate limits, etc.)

---

## Submitting Changes

### Pull Request Process

1. **Create a Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Your Changes**
   - Follow code style guidelines
   - Keep commits focused and atomic
   - Write clear commit messages

3. **Commit Your Changes**
   ```bash
   git add .
   git commit -m "Add: Brief description of changes"
   ```

   Commit message format:
   - `Add:` for new features
   - `Fix:` for bug fixes
   - `Update:` for updates to existing features
   - `Docs:` for documentation changes
   - `Refactor:` for code refactoring

4. **Push to Your Fork**
   ```bash
   git push origin feature/your-feature-name
   ```

5. **Open a Pull Request**
   - Go to the original repository
   - Click "New Pull Request"
   - Select your branch
   - Fill out the PR template

### PR Requirements

- Clear title and description
- Reference related issues
- Include screenshots/examples if applicable
- Pass all checks
- No personal information included
- Documentation updated

### PR Review Process

1. Maintainer reviews your PR
2. Address any requested changes
3. Once approved, maintainer will merge

---

## Important Notes

### Privacy and Security

**NEVER commit:**
- Your personal personalization file with real examples
- Actual tracking data
- Real lead information
- API keys or credentials
- Personal account information

**Before committing:**
- Review all changes carefully
- Use `.gitignore` properly
- Remove any personal references

### Code of Conduct

- Be respectful and constructive
- Welcome newcomers
- Focus on the project, not personalities
- Accept constructive criticism gracefully

---

## Questions?

- Open an issue for questions
- Check existing issues and PRs first
- Be patient and respectful

---

## Recognition

Contributors will be recognized in:
- GitHub contributors list
- Project README (for significant contributions)
- Release notes

Thank you for contributing to Auto-Commenter!
