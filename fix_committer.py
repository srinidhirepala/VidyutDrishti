"""
Rewrite committer to Asha0509 on commits where
  author = Asha0509  AND  committer = srinidhirepala
All other commits are untouched.
"""
import subprocess, os

NEW_NAME  = "Asha0509"
NEW_EMAIL = "23wh1a6617@bvrithyderabad.edu.in"

# bash env-filter script (runs inside Git's sh.exe)
FILTER = (
    'if [ "$GIT_AUTHOR_NAME" = "Asha0509" ] && [ "$GIT_COMMITTER_NAME" = "srinidhirepala" ]; then '
    f'export GIT_COMMITTER_NAME="{NEW_NAME}"; '
    f'export GIT_COMMITTER_EMAIL="{NEW_EMAIL}"; '
    'fi'
)

env = os.environ.copy()
env["FILTER_BRANCH_SQUELCH_WARNING"] = "1"

result = subprocess.run(
    ["git", "filter-branch", "-f", "--env-filter", FILTER, "--", "--all"],
    cwd=r"c:\Hackathon\VidyutDrishti",
    env=env,
    capture_output=True, text=True
)
print(result.stdout)
print(result.stderr)
print("Exit code:", result.returncode)
