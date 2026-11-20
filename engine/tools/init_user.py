#!/usr/bin/env python3
"""
init_user.py — create your personal user/ folder from the starter template. Run once per clone.

    python engine/tools/init_user.py                # new clone: make user/, git-init it, install the hook
    python engine/tools/init_user.py --add-missing  # user/ exists: add only the files it lacks
    python engine/tools/init_user.py --dry-run      # show what would be created, write nothing

The template is engine/templates/user/: placeholder profile files, an example settings.toml and
search_terms.toml, the CV and letter LaTeX templates, and the empty workspace folders. Nothing in
user/ is ever overwritten. user/ becomes its own git repo (personal_data/ and secrets/ kept out),
and the engine's pre-commit guard is installed (git config core.hooksPath engine/hooks).
Afterwards: fill in the files (user/README.md lists the order), then run engine/tools/doctor.py.
"""
import argparse
import shutil
import subprocess
import sys

from paths import ENGINE, REPO, USER


TEMPLATE = ENGINE / "templates" / "user"


def target(src):
    """Where a template file lands in user/. The template ships user/'s .gitignore as `gitignore`:
    a real .gitignore inside engine/templates/ would hide the template's own files from the engine repo."""
    rel = src.relative_to(TEMPLATE)
    return USER / (rel.with_name(".gitignore") if rel.as_posix() == "gitignore" else rel)


def git(cwd, *args):
    r = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8")
    return r.returncode, (r.stdout + r.stderr).strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--add-missing", action="store_true", help="user/ exists: copy only the files it lacks")
    ap.add_argument("--dry-run", action="store_true", help="print what would be created, write nothing")
    a = ap.parse_args()

    if not TEMPLATE.is_dir():
        sys.exit(f"no template at {TEMPLATE}")
    fresh = not USER.exists()
    if not fresh and not a.add_missing:
        sys.exit(f"{USER} already exists — nothing done. Use --add-missing to add only the files it "
                 "lacks (nothing is overwritten).")

    files = [p for p in sorted(TEMPLATE.rglob("*")) if p.is_file()]
    todo = [p for p in files if not target(p).exists()]
    verb = "would create" if a.dry_run else "created"
    for src in todo:
        dst = target(src)
        if not a.dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        print(f"  {verb}  user/{dst.relative_to(USER).as_posix()}")
    print(f"{len(todo)} file(s) {verb}, {len(files) - len(todo)} already present (left untouched).")
    if a.dry_run:
        return

    # user/ as its own repo, so personal edits have history and undo.
    code, top = git(USER, "rev-parse", "--show-toplevel")
    if code or top.replace("\\", "/").rstrip("/").lower() != USER.as_posix().rstrip("/").lower():
        code, out = git(USER, "init")
        print("user/ is now its own git repo." if not code else f"git init in user/ failed: {out}")
        if not code:
            git(USER, "add", "-A")
            code, out = git(USER, "commit", "-q", "-m", "Starter profile from engine/templates/user")
            if code:
                print("  (no first commit: set git user.name / user.email, then commit in user/ yourself)")

    # The engine's pre-commit guard keeps personal terms out of the engine repo.
    code, _ = git(REPO, "rev-parse", "--git-dir")
    if not code:
        code, hooks = git(REPO, "config", "--get", "core.hooksPath")
        if hooks.replace("\\", "/").rstrip("/") != "engine/hooks":
            git(REPO, "config", "core.hooksPath", "engine/hooks")
            print("Installed the pre-commit share guard (core.hooksPath = engine/hooks).")

    print("\nNext: fill in the files in the order user/README.md gives (or open Claude Code here and ask\n"
          "it to interview you and fill them), then run:  python engine/tools/doctor.py")


if __name__ == "__main__":
    main()
