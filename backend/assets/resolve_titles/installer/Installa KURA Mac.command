#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
package="$PWD/KURA_paper_title_v9_STANDALONE_FIXED.drfx"
root="$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Templates"
target="$root/KURA_paper_title_v9_STANDALONE_FIXED.drfx"
if [ ! -f "$package" ]; then echo 'Preset DRFX non trovato accanto a questo installer.'; exit 1; fi
if [ -e "$target" ] && ! cmp -s "$package" "$target"; then echo 'Un preset diverso ha lo stesso nome. Non e stato sovrascritto.'; exit 1; fi
if [ -f "$target" ] && [ -f "$root/Edit/Titles/KURA_paper_title_v9/KURA_paper_title_v9.setting" ]; then
    echo 'Preset KURA gia presente. Nessun file modificato.'
    echo 'Per lo stile corretto e necessario il font Montserrat.'
    exit 0
fi
stage="$(mktemp -d "${TMPDIR:-/tmp}/rmbl-kura.XXXXXXXX")"
trap 'rm -rf -- "$stage"' EXIT
ditto -x -k "$package" "$stage"
while IFS= read -r -d '' file; do
    relative="${file#"$stage"/}"
    dest="$root/$relative"
    if [ -e "$dest" ] && ! cmp -s "$file" "$dest"; then
        echo "Esiste gia una versione diversa: $dest. Non e stata sovrascritta."
        exit 1
    fi
done < <(find "$stage" -type f -print0)
mkdir -p "$root"
if [ ! -e "$target" ]; then cp -n "$package" "$target"; fi
created=0
while IFS= read -r -d '' file; do
    relative="${file#"$stage"/}"
    dest="$root/$relative"
    if [ ! -e "$dest" ]; then mkdir -p "$(dirname "$dest")"; cp -n "$file" "$dest"; created=$((created+1)); fi
done < <(find "$stage" -type f -print0)
if [ "$created" -eq 0 ]; then echo 'Preset KURA gia presente e verificato.'
else echo 'Preset KURA installato. Riavvia Resolve per visualizzarlo nella libreria.'; fi
echo 'Per lo stile corretto e necessario il font Montserrat.'
