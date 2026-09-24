"""Render the animated quote: line one types out, the attribution fades in
right after in a softer color, both hold, then the loop restarts."""
import base64
import os

QUOTE = "An idiot admires complexity, a genius admires simplicity."
BY = "— Terry A. Davis"
W, H, SIZE, CHAR = 820, 80, 18, 18 * 0.6  # Fira Code advance is 0.6em
LOOP, TYPE_END, BY_IN, HOLD_END = 10.0, 2.6, 2.9, 9.4  # seconds

font = base64.b64encode(open(os.path.join(os.path.dirname(__file__), "assets", "fira-code.woff2"), "rb").read()).decode()
x0, full = (W - len(QUOTE) * CHAR) / 2, len(QUOTE) * CHAR

# Typing: reveal one character per step, then hold, then clear
steps = len(QUOTE)
times = [TYPE_END * i / steps / LOOP for i in range(steps + 1)] + [HOLD_END / LOOP]
widths = [f"{CHAR * i:.1f}" for i in range(steps + 1)] + ["0"]
t = lambda s: f"{s / LOOP:.4f}"

svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs><style>@font-face{{font-family:Fira;src:url(data:font/woff2;base64,{font})}}text{{font-family:Fira,monospace;font-size:{SIZE}px}}</style>
<clipPath id="type"><rect x="{x0:.1f}" y="0" height="{H / 2}" width="0">
<animate attributeName="width" dur="{LOOP}s" repeatCount="indefinite" calcMode="discrete"
 keyTimes="{';'.join(f'{k:.4f}' for k in times)};1" values="{';'.join(widths)};0"/></rect></clipPath></defs>
<text x="{x0:.1f}" y="30" fill="#00FFFF" clip-path="url(#type)">{QUOTE}</text>
<text x="{W / 2}" y="62" text-anchor="middle" fill="#7fb8c4" font-style="italic" opacity="0">{BY}
<animate attributeName="opacity" dur="{LOOP}s" repeatCount="indefinite"
 keyTimes="0;{t(BY_IN)};{t(BY_IN + 0.4)};{t(HOLD_END - 0.3)};{t(HOLD_END)};1" values="0;0;1;1;0;0"/></text>
</svg>"""
open("quote.svg", "w", encoding="utf-8").write(svg)
print("Wrote quote.svg")
