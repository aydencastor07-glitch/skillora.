# Construit le livre « Das Gesetzbuch des Geistes » en HTML (A5, style de la couverture : ivoire, titres dorés),
# puis render_pdf.js le transforme en PDF.  usage : python3 build_book.py && node render_pdf.js
import json, os, re, html
D = os.path.dirname(os.path.abspath(__file__))
J = json.load(open(os.path.join(D, 'gesetze', 'gesetze.json')))
G, NUTZEN, TEILE = J['gesetze'], J['nutzen'], {int(k): v for k, v in J['teile'].items()}
ACCOUNT = '@magniizz'
def md(s):   # **gras** et *italique* → HTML
    s = html.escape(s, quote=False)
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s); s = re.sub(r'\*(.+?)\*', r'<em>\1</em>', s)
    return s
def md_block(path):   # petit convertisseur pour l'introduction et la conclusion
    out = []; lst = False
    for line in open(path).read().split('\n'):
        if line.startswith('# '): continue
        if line.startswith('## '): out.append(f'<h3>{md(line[3:])}</h3>'); continue
        if line.strip() == '': continue
        out.append(f'<p>{md(line)}</p>')
    return '\n'.join(out)
CSS = '''
@font-face { font-family: Cinzel; src: url(fonts/Cinzel-500.ttf); font-weight: 500; }
@font-face { font-family: Cinzel; src: url(fonts/Cinzel-700.ttf); font-weight: 700; }
@font-face { font-family: Garamond; src: url(fonts/EBGaramond-400.ttf); font-weight: 400; }
@font-face { font-family: Garamond; src: url(fonts/EBGaramond-600.ttf); font-weight: 600; }
@font-face { font-family: Garamond; src: url(fonts/EBGaramond-400i.ttf); font-style: italic; }
@page { size: 148mm 210mm; margin: 0; }
:root { --ivory: #f5f0e6; --ink: #2a2622; --gold: #a8803a; --gold2: #c9a25a; --dark: #17140f; }
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { background: var(--ivory); }
body { font-family: Garamond, serif; color: var(--ink); font-size: 11.6pt; line-height: 1.38; }
.page { width: 148mm; height: 210mm; position: relative; overflow: hidden; page-break-after: always; padding: 15mm 14mm 16mm;
        background: radial-gradient(ellipse at 50% 35%, #fbf8f2 0%, var(--ivory) 60%, #ebe3d4 100%); }
.page.cover { padding: 0; background: #000; }
.page.cover img { width: 100%; height: 100%; object-fit: cover; display: block; }
.pn { position: absolute; bottom: 7mm; left: 0; right: 0; text-align: center; font-family: Cinzel; font-size: 7.5pt; color: var(--gold); letter-spacing: 2px; }
.rule { display: flex; align-items: center; justify-content: center; gap: 6px; margin: 2.2mm auto 3mm; width: 62%; }
.rule:before, .rule:after { content: ''; flex: 1; height: 1px; background: var(--gold2); }
.rule i { width: 6px; height: 6px; background: var(--gold); transform: rotate(45deg); display: block; }
.kicker { font-family: Cinzel; font-weight: 700; color: var(--gold); letter-spacing: 3px; font-size: 8.5pt; text-align: center; }
h2 { font-family: Cinzel; font-weight: 700; font-size: 17pt; line-height: 1.15; text-align: center; color: var(--ink); margin-top: 1.5mm; }
blockquote { font-style: italic; text-align: center; font-size: 11.4pt; line-height: 1.32; color: #3b342c; margin: 0 2mm 3mm; }
blockquote b { font-style: normal; font-family: Cinzel; font-weight: 700; font-size: 7.6pt; letter-spacing: 1.5px; color: var(--gold); display: block; margin-bottom: 1mm; }
.hook { font-weight: 600; font-size: 11.6pt; line-height: 1.3; margin-bottom: 2mm; }
p { margin-bottom: 1.6mm; }
h4 { font-family: Cinzel; font-weight: 700; font-size: 8pt; letter-spacing: 2px; color: var(--gold); margin: 2.6mm 0 1.2mm; }
.nutzen { border-left: 2px solid var(--gold2); padding: 0.4mm 0 0.4mm 3mm; font-style: italic; }
ol { margin-left: 4.5mm; } li { margin-bottom: 1mm; padding-left: 1mm; } li::marker { font-family: Cinzel; color: var(--gold); font-weight: 700; }
.merke { background: var(--dark); color: #f1e6cf; text-align: center; padding: 2.4mm 4mm; margin-top: 3mm; border-radius: 1.5mm; font-size: 10.8pt; }
.merke b { font-family: Cinzel; color: var(--gold2); font-size: 7.6pt; letter-spacing: 2px; margin-right: 2mm; }
.foot { display: flex; justify-content: space-between; align-items: baseline; margin-top: 2.6mm; font-size: 9.4pt; }
.tag { font-family: Cinzel; font-size: 7.8pt; letter-spacing: 1.2px; color: var(--ink); white-space: nowrap; }
.tag span { display: inline-block; width: 3.2mm; height: 3.2mm; border: 1.2px solid var(--gold); margin-right: 1.5mm; vertical-align: -0.6mm; }
.next { font-style: italic; color: #6b5d48; text-align: right; margin-left: 4mm; }
.next b { font-style: normal; color: var(--gold); font-family: Cinzel; font-size: 7.4pt; letter-spacing: 1px; }
.center { display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; }
.titlepage h1 { font-family: Cinzel; font-weight: 500; color: var(--gold); font-size: 23pt; line-height: 1.15; letter-spacing: 1px; }
.titlepage .sub { font-family: Cinzel; font-size: 9.5pt; letter-spacing: 2px; margin-top: 2mm; }
.titlepage .acc { font-family: Cinzel; color: var(--gold); letter-spacing: 4px; font-size: 10pt; margin-top: 18mm; }
.titlepage .copy { position: absolute; bottom: 12mm; left: 0; right: 0; font-size: 7.5pt; color: #8a7b66; }
.prose h1 { font-family: Cinzel; font-weight: 700; font-size: 17pt; text-align: center; }
.prose h3 { font-family: Cinzel; font-weight: 700; font-size: 9pt; letter-spacing: 2px; color: var(--gold); margin: 4mm 0 1.5mm; }
.prose p { font-size: 11.8pt; margin-bottom: 2.6mm; }
.toc h1 { font-family: Cinzel; font-weight: 700; font-size: 17pt; text-align: center; }
.toc .part { font-family: Cinzel; font-weight: 700; color: var(--gold); font-size: 7.8pt; letter-spacing: 2px; margin: 3.2mm 0 1mm; }
.toc .row { display: flex; font-size: 9.6pt; line-height: 1.32; } .toc .row .n { width: 7mm; color: var(--gold); font-family: Cinzel; font-size: 8pt; padding-top: 0.6mm; }
.toc .row .t { flex: 1; } .toc .row .p { color: #8a7b66; }
.teil { background: radial-gradient(ellipse at 50% 45%, #2a241c 0%, var(--dark) 70%); color: #f1e6cf; }
.teil .k { font-family: Cinzel; color: var(--gold2); letter-spacing: 6px; font-size: 10pt; }
.teil h1 { font-family: Cinzel; font-weight: 500; font-size: 20pt; line-height: 1.2; margin: 4mm 6mm; }
.teil p { font-style: italic; font-size: 11.5pt; color: #d9ccb2; max-width: 95mm; }
.teil .pn { color: var(--gold2); }
'''
pages = []; pn = [0]
def page(inner, cls='', num=True):
    pn[0] += 1
    pages.append(f'<section class="page {cls}">{inner}' + (f'<div class="pn">{pn[0]}</div>' if num else '') + '</section>')
page('<img src="couverture_plate.jpg">', 'cover', False)
page(f'<div class="rule"><i></i></div><h1>Das Gesetzbuch<br>des Geistes</h1><div class="rule"><i></i></div>'
     f'<div class="sub">21 Gesetze, die dein Leben formen</div><div class="acc">{ACCOUNT}</div>'
     f'<div class="copy">© 2026 {ACCOUNT} · Alle Rechte vorbehalten.<br>Dieses Buch ersetzt keine medizinische oder psychologische Beratung.</div>', 'center titlepage', False)
page('<h1>Einleitung</h1><div class="rule"><i></i></div>' + md_block(os.path.join(D, 'gesetze', '00_einleitung.md')), 'prose')
# sommaire : numéros de page calculés (couverture, titre, intro, sommaire, puis une page par partie + une par loi)
first = 5; num_of = {}; p = first
for i in range(1, 22):
    if i in TEILE: p += 1
    num_of[i] = p; p += 1
toc = '<h1>Inhalt</h1><div class="rule"><i></i></div>'
for i, g in enumerate(G, 1):
    if i in TEILE: toc += f'<div class="part">{TEILE[i][0]} · {TEILE[i][1]}</div>'
    toc += f'<div class="row"><span class="n">{i}</span><span class="t">{md(g[0])}</span><span class="p">{num_of[i]}</span></div>'
toc += f'<div class="part">Schlusswort</div>'
page(toc, 'toc')
for i, (titel, wer, zitat, hook, absatz, uebung, merke, morgen) in enumerate(G, 1):
    if i in TEILE:
        k, t, s = TEILE[i]; page(f'<div class="k">{k.upper()}</div><div class="rule" style="width:40%"><i></i></div><h1>{t}</h1><p>{s}</p>', 'teil center')
    body = (f'<div class="kicker">GESETZ NR. {i}</div><h2>{md(titel)}</h2><div class="rule"><i></i></div>'
            f'<blockquote><b>{md(wer).upper()} SAGTE</b>„{md(zitat)}“</blockquote>'
            f'<div class="hook">{md(hook)}</div>' + ''.join(f'<p>{md(a)}</p>' for a in absatz) +
            f'<h4>WAS DIR DAS BRINGT</h4><div class="nutzen">{md(NUTZEN[i - 1])}</div>'
            f'<h4>DEINE ÜBUNG</h4><ol>' + ''.join(f'<li>{md(u)}</li>' for u in uebung) + '</ol>'
            f'<div class="merke"><b>MERKE</b>{md(merke)}</div>'
            f'<div class="foot"><span class="tag"><span></span>Tag {i} von 21</span>' + (f'<span class="next"><b>MORGEN →</b> {md(morgen)}</span>' if morgen else '<span></span>') + '</div>')
    page(body, 'law')
page('<h1>Schlusswort</h1><div class="rule"><i></i></div>' + md_block(os.path.join(D, 'gesetze', '99_schluss.md')), 'prose')
html_ = f'<!doctype html><html lang="de"><head><meta charset="utf-8"><title>Das Gesetzbuch des Geistes</title><style>{CSS}</style></head><body>{"".join(pages)}</body></html>'
open(os.path.join(D, 'livre.html'), 'w').write(html_); print(pn[0], 'pages')
