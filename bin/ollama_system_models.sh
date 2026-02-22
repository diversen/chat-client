#!/usr/bin/env bash
set -euo pipefail

# Prints: <model>  System Message included: YES|NO
# YES means the installed model's TEMPLATE contains {{ .System }} (so Ollama can inject system messages)

ollama list | awk 'NR>1{print $1}' | while read -r m; do
  mf="$(ollama show --modelfile "$m" 2>/dev/null || true)"
  if printf "%s" "$mf" | grep -qE '\{\{\s*\.System\s*\}\}'; then
    printf "%-28s System Message included: YES\n" "$m"
  else
    printf "%-28s System Message included: NO\n" "$m"
  fi
done