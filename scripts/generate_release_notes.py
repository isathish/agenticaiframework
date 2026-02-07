#!/usr/bin/env python3
"""
AI-Powered Release Notes Generator using GitHub Copilot or OpenAI
"""

import os
import sys
import subprocess
import json
from datetime import datetime
from typing import List, Dict, Optional
import argparse


class ReleaseNotesGenerator:
    """Generate intelligent release notes using AI"""
    
    def __init__(self, repo_path: str = "."):
        self.repo_path = repo_path
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        
    def get_commits_between_tags(self, previous_tag: str, new_tag: str) -> List[Dict]:
        """Get all commits between two tags"""
        cmd = [
            "git", "-C", self.repo_path, "log",
            f"{previous_tag}..{new_tag}",
            "--pretty=format:%H|%s|%b|%an|%ae|%ad",
            "--date=short"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        commits = []
        
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            parts = line.split('|')
            if len(parts) >= 2:
                commits.append({
                    'hash': parts[0][:7],
                    'subject': parts[1],
                    'body': parts[2] if len(parts) > 2 else '',
                    'author': parts[3] if len(parts) > 3 else '',
                    'email': parts[4] if len(parts) > 4 else '',
                    'date': parts[5] if len(parts) > 5 else '',
                })
        
        return commits
    
    def get_file_statistics(self, previous_tag: str, new_tag: str) -> Dict:
        """Get file change statistics"""
        # Get diff stats
        cmd = ["git", "-C", self.repo_path, "diff", "--shortstat", 
               f"{previous_tag}..{new_tag}"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        stats_line = result.stdout.strip()
        
        # Parse stats
        files_changed = 0
        insertions = 0
        deletions = 0
        
        import re
        if match := re.search(r'(\d+) files? changed', stats_line):
            files_changed = int(match.group(1))
        if match := re.search(r'(\d+) insertions?', stats_line):
            insertions = int(match.group(1))
        if match := re.search(r'(\d+) deletions?', stats_line):
            deletions = int(match.group(1))
        
        # Get changed files list
        cmd = ["git", "-C", self.repo_path, "diff", "--name-only", 
               f"{previous_tag}..{new_tag}"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        changed_files = result.stdout.strip().split('\n')
        
        return {
            'files_changed': files_changed,
            'insertions': insertions,
            'deletions': deletions,
            'changed_files': changed_files
        }
    
    def categorize_commits(self, commits: List[Dict]) -> Dict[str, List[Dict]]:
        """Categorize commits by type"""
        categories = {
            'features': [],
            'fixes': [],
            'docs': [],
            'tests': [],
            'refactor': [],
            'performance': [],
            'security': [],
            'breaking': [],
            'chore': []
        }
        
        for commit in commits:
            subject = commit['subject'].lower()
            body = commit['body'].lower()
            
            # Check for breaking changes first
            if 'breaking' in body or 'breaking change' in subject:
                categories['breaking'].append(commit)
            # Security
            elif any(k in subject for k in ['security', 'cve', 'vulnerability']):
                categories['security'].append(commit)
            # Features
            elif any(k in subject for k in ['feat:', 'feature:', 'add:', 'new:']):
                categories['features'].append(commit)
            # Fixes
            elif any(k in subject for k in ['fix:', 'bug:', 'patch:', 'hotfix:']):
                categories['fixes'].append(commit)
            # Documentation
            elif any(k in subject for k in ['docs:', 'doc:', 'documentation:']):
                categories['docs'].append(commit)
            # Tests
            elif any(k in subject for k in ['test:', 'tests:', 'testing:']):
                categories['tests'].append(commit)
            # Performance
            elif any(k in subject for k in ['perf:', 'performance:', 'optimize:']):
                categories['performance'].append(commit)
            # Refactor
            elif any(k in subject for k in ['refactor:', 'refactoring:']):
                categories['refactor'].append(commit)
            # Chore
            elif any(k in subject for k in ['chore:', 'ci:', 'build:', 'deps:']):
                categories['chore'].append(commit)
            else:
                categories['chore'].append(commit)
        
        return categories
    
    def generate_basic_notes(self, commits: List[Dict], stats: Dict, 
                           categories: Dict, previous_tag: str, new_tag: str) -> str:
        """Generate basic release notes without AI"""
        notes = f"# Release {new_tag}\n\n"
        notes += f"**Release Date**: {datetime.now().strftime('%Y-%m-%d')}\n"
        notes += f"**Previous Version**: {previous_tag}\n\n"
        notes += "---\n\n"
        
        # Summary
        notes += "##  Release Summary\n\n"
        notes += f"This release includes:\n"
        notes += f"- **{len(commits)}** commits\n"
        notes += f"- **{stats['files_changed']}** files changed\n"
        notes += f"- **{stats['insertions']}** insertions (+)\n"
        notes += f"- **{stats['deletions']}** deletions (-)\n"
        notes += f"- **{len(categories['features'])}** new features\n"
        notes += f"- **{len(categories['fixes'])}** bug fixes\n"
        notes += f"- **{len(categories['docs'])}** documentation updates\n\n"
        notes += "---\n\n"
        
        # Breaking changes
        if categories['breaking']:
            notes += "##  Breaking Changes\n\n"
            for commit in categories['breaking']:
                notes += f"- {commit['subject']} ({commit['hash']})\n"
            notes += "\n"
        
        # Security
        if categories['security']:
            notes += "##  Security\n\n"
            for commit in categories['security']:
                notes += f"- {commit['subject']} ({commit['hash']})\n"
            notes += "\n"
        
        # Features
        if categories['features']:
            notes += "##  New Features\n\n"
            for commit in categories['features']:
                notes += f"- {commit['subject']} ({commit['hash']})\n"
            notes += "\n"
        
        # Fixes
        if categories['fixes']:
            notes += "##  Bug Fixes\n\n"
            for commit in categories['fixes']:
                notes += f"- {commit['subject']} ({commit['hash']})\n"
            notes += "\n"
        
        # Performance
        if categories['performance']:
            notes += "##  Performance Improvements\n\n"
            for commit in categories['performance']:
                notes += f"- {commit['subject']} ({commit['hash']})\n"
            notes += "\n"
        
        # Documentation
        if categories['docs']:
            notes += "##  Documentation\n\n"
            for commit in categories['docs']:
                notes += f"- {commit['subject']} ({commit['hash']})\n"
            notes += "\n"
        
        # Tests
        if categories['tests']:
            notes += "##  Testing\n\n"
            for commit in categories['tests']:
                notes += f"- {commit['subject']} ({commit['hash']})\n"
            notes += "\n"
        
        # Refactoring
        if categories['refactor']:
            notes += "##  Code Refactoring\n\n"
            for commit in categories['refactor']:
                notes += f"- {commit['subject']} ({commit['hash']})\n"
            notes += "\n"
        
        # Maintenance
        if categories['chore']:
            notes += "##  Maintenance\n\n"
            for commit in categories['chore'][:10]:
                notes += f"- {commit['subject']} ({commit['hash']})\n"
            if len(categories['chore']) > 10:
                notes += f"- ... and {len(categories['chore']) - 10} more changes\n"
            notes += "\n"
        
        # Contributors
        authors = set(commit['author'] for commit in commits if commit.get('author'))
        if authors:
            notes += "##  Contributors\n\n"
            notes += f"Thank you to all {len(authors)} contributors:\n\n"
            for author in sorted(authors):
                notes += f"- @{author.replace(' ', '')}\n"
            notes += "\n"
        
        # Installation
        version = new_tag.lstrip('v')
        notes += "##  Installation\n\n"
        notes += "```bash\n"
        notes += f"pip install agenticaiframework=={version}\n"
        notes += "```\n\n"
        
        notes += "Or upgrade:\n\n"
        notes += "```bash\n"
        notes += "pip install --upgrade agenticaiframework\n"
        notes += "```\n\n"
        
        # Links
        notes += "---\n\n"
        notes += f"**Full Changelog**: [`{previous_tag}...{new_tag}`]"
        notes += f"(https://github.com/isathish/agenticaiframework/compare/{previous_tag}...{new_tag})\n"
        
        return notes
    
    def enhance_with_openai(self, basic_notes: str, commits: List[Dict]) -> Optional[str]:
        """Enhance release notes using OpenAI GPT"""
        if not self.openai_api_key:
            return None
        
        try:
            import openai
            
            client = openai.OpenAI(api_key=self.openai_api_key)
            
            # Prepare commit context
            commit_context = "\n".join([
                f"- {c['subject']}" for c in commits[:30]
            ])
            
            prompt = f"""You are an expert technical writer creating release notes for AgenticAI Framework, 
a Python framework for building intelligent AI agents.

Current release notes (basic version):
{basic_notes[:3000]}

Recent commits:
{commit_context}

Please enhance these release notes by:
1. Making the language more engaging and clear
2. Adding context about user impact for major features
3. Highlighting the most important changes
4. Keeping the same markdown structure and emoji
5. Adding brief explanations where helpful
6. Maintaining a professional but friendly tone

Return only the enhanced markdown release notes."""
            
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert technical writer."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2500,
                temperature=0.7
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f" OpenAI enhancement failed: {e}", file=sys.stderr)
            return None
    
    def generate(self, previous_tag: str, new_tag: str, 
                output_file: str = "RELEASE_NOTES.md",
                use_ai: bool = True) -> str:
        """Generate complete release notes"""
        print(f" Generating release notes: {previous_tag} → {new_tag}")
        
        # Collect data
        print(" Analyzing commits...")
        commits = self.get_commits_between_tags(previous_tag, new_tag)
        
        print(" Analyzing file changes...")
        stats = self.get_file_statistics(previous_tag, new_tag)
        
        print(" Categorizing commits...")
        categories = self.categorize_commits(commits)
        
        # Generate basic notes
        print(" Generating base release notes...")
        basic_notes = self.generate_basic_notes(
            commits, stats, categories, previous_tag, new_tag
        )
        
        # Try AI enhancement
        final_notes = basic_notes
        if use_ai and self.openai_api_key:
            print(" Enhancing with AI (OpenAI GPT)...")
            enhanced = self.enhance_with_openai(basic_notes, commits)
            if enhanced:
                final_notes = enhanced
                print(" AI enhancement successful!")
            else:
                print(" Using basic notes (AI enhancement unavailable)")
        else:
            print(" Using basic notes (AI disabled or no API key)")
        
        # Save to file
        with open(output_file, 'w') as f:
            f.write(final_notes)
        
        print(f"\n Release notes saved to: {output_file}")
        print("\nPreview:")
        print("=" * 60)
        print(final_notes[:1000] + "..." if len(final_notes) > 1000 else final_notes)
        print("=" * 60)
        
        return final_notes


def main():
    parser = argparse.ArgumentParser(
        description="Generate AI-powered release notes"
    )
    parser.add_argument(
        "--previous-tag",
        required=True,
        help="Previous version tag"
    )
    parser.add_argument(
        "--new-tag",
        required=True,
        help="New version tag"
    )
    parser.add_argument(
        "--output",
        default="RELEASE_NOTES.md",
        help="Output file path"
    )
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Disable AI enhancement"
    )
    parser.add_argument(
        "--repo-path",
        default=".",
        help="Path to git repository"
    )
    
    args = parser.parse_args()
    
    generator = ReleaseNotesGenerator(repo_path=args.repo_path)
    generator.generate(
        previous_tag=args.previous_tag,
        new_tag=args.new_tag,
        output_file=args.output,
        use_ai=not args.no_ai
    )


if __name__ == "__main__":
    main()
