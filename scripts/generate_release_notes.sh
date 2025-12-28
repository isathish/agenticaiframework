#!/bin/bash
# Script to generate release notes using GitHub Copilot
# Usage: ./generate_release_notes.sh <previous_tag> <new_tag>

set -e

PREVIOUS_TAG="${1:-$(git describe --tags --abbrev=0 HEAD^ 2>/dev/null || echo '')}"
NEW_TAG="${2:-$(git describe --tags --abbrev=0 2>/dev/null || echo 'HEAD')}"

if [ -z "$PREVIOUS_TAG" ]; then
    echo "Error: Could not determine previous tag"
    echo "Usage: $0 <previous_tag> <new_tag>"
    exit 1
fi

echo "Generating release notes from $PREVIOUS_TAG to $NEW_TAG"
echo "=================================================="

# Create temporary directory for analysis
TEMP_DIR=$(mktemp -d)
trap "rm -rf $TEMP_DIR" EXIT

# Collect commit information
git log "$PREVIOUS_TAG..$NEW_TAG" --pretty=format:"%H|%s|%b|%an|%ad" --date=short > "$TEMP_DIR/commits.txt"

# Get file statistics
git diff --stat "$PREVIOUS_TAG..$NEW_TAG" > "$TEMP_DIR/file_stats.txt"

# Get changed Python files with line counts
git diff --stat "$PREVIOUS_TAG..$NEW_TAG" -- "*.py" | head -20 > "$TEMP_DIR/python_changes.txt"

# Count different types of changes
TOTAL_COMMITS=$(git rev-list --count "$PREVIOUS_TAG..$NEW_TAG")
FILES_CHANGED=$(git diff --name-only "$PREVIOUS_TAG..$NEW_TAG" | wc -l)
LINES_ADDED=$(git diff --shortstat "$PREVIOUS_TAG..$NEW_TAG" | grep -oE '[0-9]+ insertion' | grep -oE '[0-9]+' || echo 0)
LINES_DELETED=$(git diff --shortstat "$PREVIOUS_TAG..$NEW_TAG" | grep -oE '[0-9]+ deletion' | grep -oE '[0-9]+' || echo 0)

# Categorize commits using conventional commit format
grep -iE "^[^|]*\|(feat|feature|add):" "$TEMP_DIR/commits.txt" | cut -d'|' -f2 > "$TEMP_DIR/features.txt" || touch "$TEMP_DIR/features.txt"
grep -iE "^[^|]*\|(fix|bug):" "$TEMP_DIR/commits.txt" | cut -d'|' -f2 > "$TEMP_DIR/fixes.txt" || touch "$TEMP_DIR/fixes.txt"
grep -iE "^[^|]*\|(docs|doc):" "$TEMP_DIR/commits.txt" | cut -d'|' -f2 > "$TEMP_DIR/docs.txt" || touch "$TEMP_DIR/docs.txt"
grep -iE "^[^|]*\|(test):" "$TEMP_DIR/commits.txt" | cut -d'|' -f2 > "$TEMP_DIR/tests.txt" || touch "$TEMP_DIR/tests.txt"
grep -iE "^[^|]*\|(chore|ci|build):" "$TEMP_DIR/commits.txt" | cut -d'|' -f2 > "$TEMP_DIR/chore.txt" || touch "$TEMP_DIR/chore.txt"

# Check for breaking changes
grep -i "breaking" "$TEMP_DIR/commits.txt" > "$TEMP_DIR/breaking.txt" || touch "$TEMP_DIR/breaking.txt"

# Get contributor list
git log "$PREVIOUS_TAG..$NEW_TAG" --pretty=format:"%an" | sort -u > "$TEMP_DIR/contributors.txt"

# Generate release notes
OUTPUT_FILE="RELEASE_NOTES.md"

cat > "$OUTPUT_FILE" << EOF
# Release Notes - $NEW_TAG

**Release Date**: $(date +%Y-%m-%d)
**Previous Version**: $PREVIOUS_TAG


## 📊 Overview

This release includes:
- **$TOTAL_COMMITS** commits
- **$FILES_CHANGED** files changed
- **$LINES_ADDED** insertions, **$LINES_DELETED** deletions
- **$(wc -l < "$TEMP_DIR/features.txt")** new features
- **$(wc -l < "$TEMP_DIR/fixes.txt")** bug fixes
- **$(wc -l < "$TEMP_DIR/docs.txt")** documentation updates
- **$(wc -l < "$TEMP_DIR/contributors.txt")** contributors


EOF

# Breaking changes (if any)
if [ -s "$TEMP_DIR/breaking.txt" ]; then
    cat >> "$OUTPUT_FILE" << EOF
## ⚠️ Breaking Changes

$(cat "$TEMP_DIR/breaking.txt" | cut -d'|' -f2 | sed 's/^/- /')


EOF
fi

# Features
if [ -s "$TEMP_DIR/features.txt" ]; then
    cat >> "$OUTPUT_FILE" << EOF
## ✨ New Features

$(cat "$TEMP_DIR/features.txt" | sed 's/^/- /')

EOF
fi

# Bug fixes
if [ -s "$TEMP_DIR/fixes.txt" ]; then
    cat >> "$OUTPUT_FILE" << EOF
## 🐛 Bug Fixes

$(cat "$TEMP_DIR/fixes.txt" | sed 's/^/- /')

EOF
fi

# Documentation
if [ -s "$TEMP_DIR/docs.txt" ]; then
    cat >> "$OUTPUT_FILE" << EOF
## 📚 Documentation

$(cat "$TEMP_DIR/docs.txt" | sed 's/^/- /')

EOF
fi

# Testing
if [ -s "$TEMP_DIR/tests.txt" ]; then
    cat >> "$OUTPUT_FILE" << EOF
## 🧪 Testing

$(cat "$TEMP_DIR/tests.txt" | sed 's/^/- /')

EOF
fi

# Maintenance
if [ -s "$TEMP_DIR/chore.txt" ]; then
    cat >> "$OUTPUT_FILE" << EOF
## 🔧 Maintenance

$(head -10 "$TEMP_DIR/chore.txt" | sed 's/^/- /')
$([ $(wc -l < "$TEMP_DIR/chore.txt") -gt 10 ] && echo "- ... and $(expr $(wc -l < "$TEMP_DIR/chore.txt") - 10) more maintenance changes")

EOF
fi

# File changes summary
cat >> "$OUTPUT_FILE" << EOF
## 📁 Files Changed

\`\`\`
$(head -20 "$TEMP_DIR/file_stats.txt")
$([ $(wc -l < "$TEMP_DIR/file_stats.txt") -gt 20 ] && echo "... and more")
\`\`\`

EOF

# Contributors
cat >> "$OUTPUT_FILE" << EOF
## 👥 Contributors

Thank you to all contributors who made this release possible:

$(cat "$TEMP_DIR/contributors.txt" | sed 's/^/- @/' | sed 's/ //g')


## 📦 Installation

\`\`\`bash
pip install agenticaiframework==${NEW_TAG#v}
\`\`\`

Or upgrade from a previous version:

\`\`\`bash
pip install --upgrade agenticaiframework
\`\`\`


## 📖 Documentation

- [Full Documentation](https://isathish.github.io/agenticaiframework/)
- [API Reference](https://isathish.github.io/agenticaiframework/API_REFERENCE/)
- [Quick Start Guide](https://isathish.github.io/agenticaiframework/quick-start/)
- [Examples](https://isathish.github.io/agenticaiframework/EXAMPLES/)


**Full Changelog**: [\`$PREVIOUS_TAG...$NEW_TAG\`](https://github.com/isathish/agenticaiframework/compare/$PREVIOUS_TAG...$NEW_TAG)
EOF

echo ""
echo "✅ Release notes generated successfully!"
echo "📄 Output: $OUTPUT_FILE"
echo ""
echo "Preview:"
echo "=================================================="
cat "$OUTPUT_FILE"
echo "=================================================="

# If GitHub CLI is available and we're in a CI environment, create/update release
if command -v gh &> /dev/null && [ -n "$GITHUB_TOKEN" ]; then
    echo ""
    echo "Creating/updating GitHub release..."
    
    if gh release view "$NEW_TAG" >/dev/null 2>&1; then
        gh release edit "$NEW_TAG" --notes-file "$OUTPUT_FILE"
        echo "✅ Release updated successfully!"
    else
        gh release create "$NEW_TAG" \
            --title "Release $NEW_TAG" \
            --notes-file "$OUTPUT_FILE"
        echo "✅ Release created successfully!"
    fi
fi
