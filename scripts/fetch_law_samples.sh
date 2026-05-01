#!/usr/bin/env bash
# scripts/fetch_law_samples.sh
#
# Fetch raw XML responses from 법제처 OpenAPI (https://www.law.go.kr/DRF/).
#
# Targets:
#   lawService.do (full document) -> data/raw/{law_id}/{mst}.xml
#       Canonical retention store per ADR-011. Gitignored, indefinite
#       retention, plain UTF-8, byte-for-byte from the API.
#   lawSearch.do  (search index)  -> docs/api-samples/search-{query}.xml
#       Developer-facing samples; not retention. ADR-011 "Out of scope" #2.
#
# Requires LAW_GO_KR_OC in environment (see README §"docs/api-samples/").
# Idempotent: existing files are skipped unless --force is set.
# Atomic: writes via tmp+rename so a crash mid-fetch leaves no half-files.

set -euo pipefail

API_BASE="https://www.law.go.kr/DRF"

# Phase-1 default set. law_id values verified against existing samples
# (Act 013993, Decree 014159).
PHASE1_DOCS=(
  "013993:228817"   # 중대재해처벌법 (Act)
  "014159:277417"   # 중대재해처벌법 시행령 (Decree)
)
PHASE1_SEARCHES=(
  "중대재해"
)

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAW_DIR="$REPO_ROOT/data/raw"
SAMPLES_DIR="$REPO_ROOT/docs/api-samples"

FORCE=0

die() { echo "ERROR: $*" >&2; exit 1; }

usage() {
  cat <<'USAGE'
Fetch raw XML responses from 법제처 OpenAPI.

  fetch_law_samples.sh                           # Phase-1 default set
  fetch_law_samples.sh --force                   # Phase-1, overwrite existing
  fetch_law_samples.sh --doc <law_id> <mst>     # single document
  fetch_law_samples.sh --search <query>          # single search
  fetch_law_samples.sh --help

Document fetches (lawService.do) write to data/raw/{law_id}/{mst}.xml
per ADR-011. Search fetches write to docs/api-samples/search-{query}.xml.
Requires LAW_GO_KR_OC in environment. Idempotent unless --force.
USAGE
}

check_env() {
  [[ -n "${LAW_GO_KR_OC:-}" ]] || die "LAW_GO_KR_OC is not set. See README.md."
  command -v curl >/dev/null || die "curl is not installed."
}

# fetch_to <target-path> <endpoint-url> <curl-arg>...
# Atomic fetch with idempotency and empty-response detection.
fetch_to() {
  local target="$1"; shift
  local endpoint="$1"; shift

  if [[ -e "$target" && "$FORCE" != "1" ]]; then
    echo "skip: ${target#$REPO_ROOT/} (exists; use --force to overwrite)"
    return 0
  fi

  mkdir -p "$(dirname "$target")"
  local tmpfile
  tmpfile="$(mktemp "${target}.XXXXXX")"
  trap 'rm -f "$tmpfile"' EXIT INT TERM HUP

  curl -sfG \
    --retry 3 --retry-delay 2 --retry-connrefused \
    --data-urlencode "OC=$LAW_GO_KR_OC" \
    "$@" \
    "$endpoint" \
    -o "$tmpfile" \
    || die "HTTP fetch failed: $endpoint"

  [[ -s "$tmpfile" ]] || die "Empty response: $endpoint"

  mv "$tmpfile" "$target"
  trap - EXIT INT TERM HUP
  sync
  echo "wrote: ${target#$REPO_ROOT/} ($(wc -c <"$target") bytes)"
}

fetch_doc() {
  local law_id="$1" mst="$2"
  fetch_to "$RAW_DIR/$law_id/$mst.xml" \
    "$API_BASE/lawService.do" \
    --data-urlencode "target=law" \
    --data-urlencode "type=XML" \
    --data-urlencode "MST=$mst"
}

fetch_search() {
  local query="$1"
  fetch_to "$SAMPLES_DIR/search-$query.xml" \
    "$API_BASE/lawSearch.do" \
    --data-urlencode "target=law" \
    --data-urlencode "type=XML" \
    --data-urlencode "display=5" \
    --data-urlencode "query=$query"
}

run_phase1() {
  for entry in "${PHASE1_DOCS[@]}"; do
    fetch_doc "${entry%:*}" "${entry#*:}"
  done
  for q in "${PHASE1_SEARCHES[@]}"; do
    fetch_search "$q"
  done
}

mode=phase1
args=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force) FORCE=1; shift ;;
    --doc)
      [[ $# -ge 3 ]] || die "--doc requires <law_id> <mst>"
      mode=doc; args=("$2" "$3"); shift 3
      ;;
    --search)
      [[ $# -ge 2 ]] || die "--search requires <query>"
      mode=search; args=("$2"); shift 2
      ;;
    --help|-h) usage; exit 0 ;;
    *) die "Unknown argument: $1 (try --help)" ;;
  esac
done

check_env

case "$mode" in
  phase1) run_phase1 ;;
  doc)    fetch_doc "${args[0]}" "${args[1]}" ;;
  search) fetch_search "${args[0]}" ;;
esac
