#!/bin/bash
# Portability smoke under Git Bash, NOT a physical macOS acceptance test.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
QA="$ROOT/../_qa/mac-installer-$(date +%s)-$$"
mkdir -p "$QA/bin" "$QA/Plugins/com.rambla.autocut"
printf 'AUTOCUT' > "$QA/Plugins/com.rambla.autocut/main.js"
printf 'V3.1' > "$QA/RAMBLA_SRT_Range.lua"
printf 'SDK' > "$QA/WorkflowIntegration.node"
cat > "$QA/bin/shasum" <<'HASH'
#!/bin/bash
shift 2
exec sha256sum "$@"
HASH
chmod +x "$QA/bin/shasum"
export PATH="$QA/bin:$PATH"
/bin/bash "$ROOT/install/install-mac.sh" --plugin-root "$QA/Plugins" --sdk "$QA/WorkflowIntegration.node" --quiet
cmp "$QA/WorkflowIntegration.node" "$QA/Plugins/com.rambla.srt/WorkflowIntegration.node"
printf 'broken' > "$QA/Plugins/com.rambla.srt/main.js"
/bin/bash "$ROOT/install/install-mac.sh" --plugin-root "$QA/Plugins" --sdk "$QA/WorkflowIntegration.node" --quiet
cmp "$ROOT/plugin/main.js" "$QA/Plugins/com.rambla.srt/main.js"
[ "$(cat "$QA/Plugins/com.rambla.autocut/main.js")" = AUTOCUT ]
[ "$(cat "$QA/RAMBLA_SRT_Range.lua")" = V3.1 ]
[ -d "$QA/RAMBLA SRT Install Backups" ]
[ "$(find "$QA/Plugins" -name manifest.xml | wc -l | tr -d ' ')" = 1 ]
echo 'Mac shell installer simulation: install/repair/backup/isolation PASS (not physical Mac QA)'
