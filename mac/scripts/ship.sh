#!/bin/sh
# usage: V=<version> TAP=<tap folder> MAKE=<make> scripts/ship.sh, from mac/ (make ship does this). One release of Abhyasa.app.
# The local steps are all or nothing: when a step fails before the commits, the files that ship changed go back as they were.
# The remote steps can run again: publish is skipped when mac-v<V> is on GitHub already, a commit is made only when a file
# changed, and a push with nothing new does nothing. So after a failure, run make ship V=<version> again.
set -eu
: "${V:?Give the version: make ship V=<version>}"
: "${TAP:?TAP is the folder of the Homebrew tap}"
MAKE=${MAKE:-make}
unset GITHUB_TOKEN   # the keyring of gh signs in; a stale token in the environment would win over it

test -z "$(git -C .. status --porcelain)" || { echo "abhyasa has changes that are not committed" >&2; exit 1; }
test -z "$(git -C "$TAP" status --porcelain)" || { echo "$TAP has changes that are not committed" >&2; exit 1; }

# Wait up to 10 minutes for the wheel on PyPI's simple index (the index that uv reads). No file changes before this.
n=0
until curl -fsS https://pypi.org/simple/abhyasa/ | grep -q "abhyasa-$V-py3-none-any.whl"; do
  n=$((n + 1))
  test $n -le 40 || { echo "abhyasa $V is not on PyPI after 10 minutes. Release it with nbdev-pypi, then run make ship again." >&2; exit 1; }
  echo "Waiting for abhyasa $V on PyPI ($n of 40)"; sleep 15
done

committed=0 shipped=0
undo() {
  test $shipped = 1 && return
  if test $committed = 1; then echo "make ship stopped after the commits. Run make ship V=$V again to push." >&2; return; fi
  git -C .. checkout -- mac/Resources README.md nbs/index.ipynb
  git -C "$TAP" checkout -- Casks
  git -C "$TAP" clean -fq -- Casks   # a cask file that this run copied in
  echo "make ship stopped. The files are as they were before. Run make ship V=$V again." >&2
}
trap 'undo' EXIT

python3 - <<'EOF'
import os, re, pathlib
p = pathlib.Path('Resources/Pin/pyproject.toml'); s = p.read_text(); v = os.environ['V']
f = lambda m: 'abhyasa[' + ','.join(x for x in m[1].split(',') if x.strip() not in ('', 'repos')) + ']==' + v
t = re.sub(r'abhyasa\[([^\]]*)\]==[^"]+', f, s, count=1)
if t == s and f'=={v}"' not in s: raise SystemExit(f'no abhyasa pin in {p}')
p.write_text(t)
EOF
grep -n 'abhyasa\[' Resources/Pin/pyproject.toml
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $V" Resources/Info.plist
"$MAKE" lock
# ZIP is exported with the name of the old version; with it unset, publish and cask make the name from the new Info.plist
if gh release view "mac-v$V" >/dev/null 2>&1; then echo "mac-v$V is on GitHub already, so ship does not build or publish it again"
else env -u ZIP "$MAKE" publish; fi
env -u ZIP "$MAKE" cask

git -C "$TAP" add Casks/abhyasa.rb
git -C "$TAP" diff --cached --quiet || git -C "$TAP" commit -m "Abhyasa $V"
git -C .. add mac/Resources README.md nbs/index.ipynb
git -C .. diff --cached --quiet || git -C .. commit -m "Pin Abhyasa.app $V to abhyasa $V"
committed=1
git -C "$TAP" -c credential.helper= -c "credential.helper=!gh auth git-credential" push
git -C .. -c credential.helper= -c "credential.helper=!gh auth git-credential" push
shipped=1
echo "Abhyasa $V is shipped."
