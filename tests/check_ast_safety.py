import sys
import re
import pathlib

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

js_dir = pathlib.Path("src/web/js")
pattern = re.compile(r'\$\{([^}]+)\}')

safe_patterns = [
    "escapeHtml", "icon(", "platBadge", "statusDot", "Number(", "fmtTime(",
    "elapsedText(", "runStatusPill(", "resultPill(", "holderInitial(", "btnCls(",
    "platGrad(", "tabBtn(", "row(", "countOf(", "cards.map", "ch.pinned ?",
    "platOptions.join", "rows.map", "visibleGroups.map", "group.matchingChannels",
    "chunks.map", "r.days_left", "dotCls", "dotPulse", "pendBadge", "pinStar",
    "presenceLine", "cardHighlight", "mainActionAttr", "mainDisabled", "mainColor",
    "mainText", "pendN ?", "when", "safeId", "safeName", "safeAccEmail", "safeAccDisplay",
    "safeLockedBy", "platLabel", "statusText", "actBtn", "accCell", "rowHighlight",
    "pinBtn", "logoHtml", "colBorder", "countBadgeText", "hasPinned ?", "channelCount",
    "platformCount", "allBtn", "actionBtns", "kindCls", "initial", "grad", "size",
    "rounded", "txt", "nextIdx", "fieldId", "badgeCls", "isIncoming ?"
]

print("=== Scanning JS files for potentially unsafe template interpolations ===")
found = 0
for js_file in sorted(js_dir.glob("*.js")):
    code = js_file.read_text(encoding="utf-8")
    lines = code.splitlines()
    for lno, line in enumerate(lines, 1):
        # We only care about lines with template string interpolation
        matches = pattern.findall(line)
        if not matches:
            continue
        for expr in matches:
            expr_clean = expr.strip()
            is_safe = False
            for sp in safe_patterns:
                if sp in expr_clean:
                    is_safe = True
                    break
            if not is_safe:
                print(f"[{js_file.name}:{lno}] Potentially unescaped: ${{{expr_clean}}}")
                print(f"   Line: {line.strip()}")
                found += 1

print(f"\nTotal potential findings: {found}")
