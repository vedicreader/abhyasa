#!/bin/sh
# usage: scripts/notarize.sh <zip>. Exit 3: no credentials. Credentials, first match wins:
# $NOTARY_CONFIG, ~/.config/abhyasa/notary.json or Sanketa's ~/.config/sanketa/notary.json (the same team)
# {"key_id","issuer_id","key_path"}; env NOTARY_KEY_PATH,
# NOTARY_KEY_ID, NOTARY_ISSUER; env NOTARY_PROFILE (a notarytool keychain profile).
set -eu
zip="$1"
cfg="${NOTARY_CONFIG:-$HOME/.config/abhyasa/notary.json}"
if [ -z "${NOTARY_CONFIG:-}" ] && [ ! -f "$cfg" ]; then cfg="$HOME/.config/sanketa/notary.json"; fi
if [ -f "$cfg" ]; then
  eval "$(python3 -c '
import json, os, shlex, sys
c = json.load(open(sys.argv[1]))
p = os.path.join(os.path.dirname(sys.argv[1]), os.path.expanduser(c["key_path"]))
for k, v in (("NOTARY_KEY_PATH", p), ("NOTARY_KEY_ID", c["key_id"]), ("NOTARY_ISSUER", c["issuer_id"])): print(f"{k}={shlex.quote(v)}")
' "$cfg")"
  echo "notary: API key $NOTARY_KEY_ID from $cfg"
fi
if [ -n "${NOTARY_KEY_PATH:-}" ]; then set -- --key "$NOTARY_KEY_PATH" --key-id "$NOTARY_KEY_ID" --issuer "$NOTARY_ISSUER"
elif [ -n "${NOTARY_PROFILE:-}" ]; then set -- --keychain-profile "$NOTARY_PROFILE"
else exit 3; fi
field() { python3 -c 'import json,sys; print(json.loads(sys.stdin.read() or "{}").get(sys.argv[1], ""))' "$1"; }
err="$(mktemp -t abhyasa-notary)"
out="$(xcrun notarytool submit "$zip" "$@" --wait --output-format json 2>"$err")" || true
id="$(echo "$out" | field id 2>/dev/null || true)"; status="$(echo "$out" | field status 2>/dev/null || true)"
if [ -z "$id" ]; then
  echo "$out"; cat "$err"
  case "$out$(cat "$err")" in *403*|*[Rr]ole*|*[Pp]ermission*) echo "notary: this key cannot notarize. Use a key with the Developer or Admin role.";; esac
  exit 1
fi
echo "notary: submission $id: $status"
[ "$status" = Accepted ] && exit 0
xcrun notarytool log "$id" "$@" | python3 -c '
import json, sys
for i in json.load(sys.stdin).get("issues") or []: print(i.get("severity"), i.get("path"), i.get("message"), sep=": ")'
exit 1
