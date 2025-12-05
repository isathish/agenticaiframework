# Release Notes Generation Scripts

This directory contains scripts and workflows for automatically generating AI-powered release notes using GitHub Copilot and other AI services.

## 📁 Files

### GitHub Actions Workflows

1. **`.github/workflows/release-notes.yml`**
   - Automated workflow triggered on git tags
   - Generates comprehensive release notes using AI
   - Supports OpenAI GPT-4 for enhancement
   - Creates or updates GitHub releases

### Scripts

2. **`generate_release_notes.sh`**
   - Bash script for quick release note generation
   - Works locally or in CI/CD pipelines
   - No external dependencies required
   - Automatically categorizes commits

3. **`generate_release_notes.py`**
   - Advanced Python script with AI integration
   - Supports OpenAI GPT-4 for enhancement
   - Rich commit analysis and categorization
   - Command-line interface

## 🚀 Usage

### Automatic (CI/CD Pipeline)

The release notes are automatically generated when you push code to main or create a new tag:

```bash
# Push to main - automated version bump and release
git push origin main

# Or manually trigger with specific version
gh workflow run python-package.yml -f release_type=minor
```

### Manual Generation (Local)

#### Using Bash Script

```bash
# Generate for latest tags
./scripts/generate_release_notes.sh

# Generate for specific tags
./scripts/generate_release_notes.sh v0.1.0 v0.2.0
```

#### Using Python Script

```bash
# Basic usage
python scripts/generate_release_notes.py \
  --previous-tag v0.1.0 \
  --new-tag v0.2.0

# With AI enhancement (requires OPENAI_API_KEY)
export OPENAI_API_KEY="your-key-here"
python scripts/generate_release_notes.py \
  --previous-tag v0.1.0 \
  --new-tag v0.2.0 \
  --output RELEASE_NOTES.md

# Without AI enhancement
python scripts/generate_release_notes.py \
  --previous-tag v0.1.0 \
  --new-tag v0.2.0 \
  --no-ai
```

### Using GitHub Actions Workflow

Trigger the release notes workflow manually:

```bash
# For a specific tag
gh workflow run release-notes.yml -f tag=v0.2.0
```

## 🤖 AI Enhancement

The scripts support AI-powered enhancement of release notes using:

### OpenAI GPT-4

Set up OpenAI API key as a repository secret:

1. Go to repository Settings → Secrets → Actions
2. Add secret: `OPENAI_API_KEY`
3. The workflow will automatically use it

### Features of AI Enhancement

- **Improved clarity**: Makes technical changes understandable
- **User impact**: Highlights what matters to users
- **Context**: Adds helpful explanations
- **Consistency**: Ensures professional tone
- **Prioritization**: Emphasizes important changes

## 📋 Release Notes Structure

Generated release notes include:

```markdown
# Release vX.Y.Z

## 📊 Release Summary
- Commit count, file changes, line changes
- Summary by category

## ⚠️ Breaking Changes (if any)
- Critical changes that require user action

## 🔒 Security
- Security fixes and updates

## ✨ New Features
- New capabilities and features

## 🐛 Bug Fixes
- Issues resolved

## ⚡ Performance Improvements
- Speed and efficiency gains

## 📚 Documentation
- Docs updates

## 🧪 Testing
- Test improvements

## ♻️ Code Refactoring
- Internal improvements

## 🔧 Maintenance
- Chores, CI, dependencies

## 👥 Contributors
- All contributors

## 📦 Installation
- How to install/upgrade
```

## 🔧 Configuration

### Environment Variables

```bash
# Required for AI enhancement
export OPENAI_API_KEY="sk-..."

# Required for GitHub operations
export GITHUB_TOKEN="ghp_..."

# Optional: Anthropic API (future support)
export ANTHROPIC_API_KEY="sk-ant-..."
```

### GitHub Secrets

Configure in repository settings:

- `OPENAI_API_KEY` - OpenAI API key for GPT-4
- `GITHUBPATTOKEN` - Personal access token for pushing changes
- `PYPI_TOKEN` - PyPI API token for publishing

## 📝 Commit Message Format

For best categorization, use conventional commit format:

```bash
feat: Add new feature
fix: Fix bug in component
docs: Update documentation
test: Add test coverage
chore: Update dependencies
perf: Improve performance
refactor: Refactor code
security: Fix security issue
```

## 🎯 Examples

### Example 1: Basic Release Notes

```bash
# Generate basic notes without AI
./scripts/generate_release_notes.sh v0.1.0 v0.2.0
```

Output includes:
- Categorized commits
- File statistics
- Contributors
- Installation instructions

### Example 2: AI-Enhanced Release Notes

```bash
# With OpenAI enhancement
export OPENAI_API_KEY="your-key"
python scripts/generate_release_notes.py \
  --previous-tag v0.1.0 \
  --new-tag v0.2.0
```

Output includes:
- All basic content
- Enhanced descriptions
- User impact explanations
- Professional polish

### Example 3: CI/CD Automatic Generation

```yaml
# In your workflow
- name: Generate Release Notes
  run: |
    python scripts/generate_release_notes.py \
      --previous-tag ${{ steps.previous_tag.outputs.tag }} \
      --new-tag ${{ steps.current_tag.outputs.tag }}
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

## 🔍 How It Works

### 1. Data Collection
- Extract commits between tags
- Analyze file changes
- Count additions/deletions
- Identify contributors

### 2. Categorization
- Parse conventional commit messages
- Detect breaking changes
- Identify security updates
- Group by type (feat, fix, docs, etc.)

### 3. Basic Generation
- Create structured markdown
- Add statistics and summaries
- Include all categories
- List contributors

### 4. AI Enhancement (Optional)
- Send context to AI model
- Request improvements
- Add user impact details
- Polish language and clarity

### 5. Publishing
- Save to file
- Create GitHub release
- Update CHANGELOG.md
- Commit changes

## 🎨 Customization

### Modify Templates

Edit the scripts to customize output:

```python
# In generate_release_notes.py
def generate_basic_notes(self, ...):
    notes = f"# Custom Title {new_tag}\n\n"
    # Your custom format here
    return notes
```

### Add Custom Categories

```python
# Add new commit categories
categories = {
    'features': [],
    'fixes': [],
    'custom_category': [],  # Add your category
}
```

### Adjust AI Prompts

```python
# Customize AI enhancement
prompt = """Your custom instructions for AI
to generate release notes in your preferred style..."""
```

## 🐛 Troubleshooting

### Issue: No commits found

```bash
# Check tags exist
git tag -l

# Verify tag range
git log v0.1.0..v0.2.0
```

### Issue: AI enhancement fails

```bash
# Verify API key
echo $OPENAI_API_KEY

# Check Python dependencies
pip install openai

# Use without AI
python scripts/generate_release_notes.py --no-ai ...
```

### Issue: GitHub release creation fails

```bash
# Verify GitHub token
echo $GITHUB_TOKEN

# Check permissions
gh auth status

# Manually create release
gh release create v0.2.0 --notes-file RELEASE_NOTES.md
```

## 📚 Related Documentation

- [GitHub Actions Workflows](../.github/workflows/)
- [CHANGELOG.md](../CHANGELOG.md)
- [Contributing Guidelines](../CONTRIBUTING.md)
- [Version Management](../docs/VERSIONING.md)

## 🤝 Contributing

To improve the release notes generation:

1. Test changes locally first
2. Update documentation
3. Add examples
4. Submit PR with description

## 📄 License

Same as main project - see [LICENSE](../LICENSE)
