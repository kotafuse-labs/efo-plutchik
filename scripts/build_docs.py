#!/usr/bin/env python3
"""Build the human-readable documentation and the served copies of the ontology under docs/.

Output:
  docs/index.html                 reference page; every term has an anchor equal to its local name,
                                  so https://w3id.org/efo-plutchik#Joy lands on the entry for Joy
  docs/efo-plutchik.ttl           current version (copy of ontology/efo-plutchik.ttl)
  docs/<version>/efo-plutchik.ttl one copy per released version (current + releases/<version>/)

Usage:
  python scripts/build_docs.py           # write
  python scripts/build_docs.py --check   # exit 1 if docs/ is out of date
"""
import argparse
import html
import shutil
import sys
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS, SKOS

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "ontology" / "efo-plutchik.ttl"
DOCS = ROOT / "docs"
PLU = Namespace("https://w3id.org/efo-plutchik#")
ONT = URIRef(str(PLU))
REPO_URL = "https://github.com/kotafuse-labs/efo-plutchik"

SECTIONS = [
    ("Classes", [OWL.Class]),
    ("Object properties", [OWL.ObjectProperty]),
    ("Datatype properties", [OWL.DatatypeProperty]),
    ("Basic emotions", [PLU.BasicEmotion]),
    ("Intensity variants", [PLU.IntensityVariant]),
    ("Primary dyads", [PLU.PrimaryDyad]),
    ("Secondary dyads", [PLU.SecondaryDyad]),
    ("Tertiary dyads", [PLU.TertiaryDyad]),
    ("Intensity levels", [PLU.IntensityLevel]),
    ("Derivation rules", [PLU.DerivationRule]),
]
SKIP = {RDF.type, RDFS.label, SKOS.definition}


def local(u) -> str:
    return str(u)[len(str(PLU)):]


def lang(g, s, p, code):
    vals = sorted(str(o) for o in g.objects(s, p) if isinstance(o, Literal) and o.language == code)
    return vals[0] if vals else ""


def show(g, o) -> str:
    if isinstance(o, URIRef):
        if str(o).startswith(str(PLU)) and o != ONT:
            return f'<a href="#{html.escape(local(o))}">plu:{html.escape(local(o))}</a>'
        try:
            name = g.namespace_manager.qname(o)
        except Exception:
            name = str(o)
        return f'<a href="{html.escape(str(o))}">{html.escape(name)}</a>'
    if isinstance(o, Literal):
        return html.escape(str(o))
    return ""


def entry(g, s) -> str:
    rows = {}
    for p, o in g.predicate_objects(s):
        if p in SKIP or not isinstance(o, (URIRef, Literal)):
            continue
        rows.setdefault(g.namespace_manager.qname(p), set()).add(show(g, o))
    types = sorted(g.namespace_manager.qname(t) for t in g.objects(s, RDF.type)
                   if isinstance(t, URIRef) and t != OWL.NamedIndividual)
    out = [f'<article id="{html.escape(local(s))}">',
           f'<h3>{html.escape(lang(g, s, RDFS.label, "en") or local(s))} '
           f'<span class="ja" lang="ja">{html.escape(lang(g, s, RDFS.label, "ja"))}</span></h3>',
           f'<p class="iri"><code>plu:{html.escape(local(s))}</code> · {html.escape(", ".join(types))}</p>',
           f'<p>{html.escape(lang(g, s, SKOS.definition, "en"))}</p>',
           f'<p class="ja" lang="ja">{html.escape(lang(g, s, SKOS.definition, "ja"))}</p>']
    if rows:
        out.append("<dl>")
        for k in sorted(rows):
            out.append(f"<dt>{html.escape(k)}</dt><dd>{', '.join(sorted(rows[k]))}</dd>")
        out.append("</dl>")
    out.append("</article>")
    return "\n".join(out)


def versions():
    """{version: path of the TTL}. The current file plus every releases/<version>/efo-plutchik.ttl."""
    g = Graph().parse(SRC)
    out = {str(g.value(ONT, OWL.versionInfo)): SRC}
    for p in sorted((ROOT / "releases").glob("*/efo-plutchik.ttl")):
        out[p.parent.name] = p
    return out


def render() -> str:
    g = Graph().parse(SRC)
    seen, body, toc = set(), [], []
    for title, classes in SECTIONS:
        terms = sorted({s for c in classes for s in g.subjects(RDF.type, c)
                        if isinstance(s, URIRef) and str(s).startswith(str(PLU)) and s != ONT and s not in seen}, key=local)
        if not terms:
            continue
        seen.update(terms)
        anchor = "sec-" + title.lower().replace(" ", "-")
        toc.append(f'<li><a href="#{anchor}">{html.escape(title)}</a> ({len(terms)})</li>')
        body.append(f'<section><h2 id="{anchor}">{html.escape(title)}</h2>\n' + "\n".join(entry(g, s) for s in terms) + "\n</section>")
    missing = {s for s in g.subjects() if isinstance(s, URIRef) and str(s).startswith(str(PLU)) and s != ONT} - seen
    if missing:
        raise SystemExit(f"[stop] terms not covered by any section: {sorted(local(s) for s in missing)}")
    ver = str(g.value(ONT, OWL.versionInfo))
    vlinks = ", ".join(f'<a href="{v}/efo-plutchik.ttl">{v}</a>' for v in sorted(versions(), reverse=True))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EFO-Plutchik {html.escape(ver)}</title>
<style>
body {{ font-family: system-ui, sans-serif; line-height: 1.55; max-width: 54rem; margin: 0 auto; padding: 1rem; color: #1b1b1b; background: #fff; }}
h2 {{ border-bottom: 1px solid #ccc; padding-bottom: .2rem; margin-top: 2.5rem; }}
article {{ border-top: 1px solid #eee; padding: .6rem 0; }}
article:target {{ background: #fff8d6; }}
h3 {{ margin: .2rem 0; }}
.ja {{ color: #555; font-weight: normal; }}
.iri {{ margin: 0; font-size: .9rem; color: #555; }}
dl {{ display: grid; grid-template-columns: max-content 1fr; gap: .15rem 1rem; font-size: .9rem; margin: .4rem 0 0; }}
dt {{ color: #555; }} dd {{ margin: 0; overflow-wrap: anywhere; }}
@media (prefers-color-scheme: dark) {{
  body {{ color: #e6e6e6; background: #161616; }} a {{ color: #8ab4f8; }}
  .ja, .iri, dt {{ color: #aaa; }} article {{ border-color: #333; }} h2 {{ border-color: #444; }}
  article:target {{ background: #3a3413; }}
}}
</style>
</head>
<body>
<h1>EFO-Plutchik <small>{html.escape(ver)}</small></h1>
<p>{html.escape(str(g.value(ONT, DCTERMS.description)))}</p>
<dl>
<dt>Namespace</dt><dd><code>{html.escape(str(PLU))}</code> (prefix <code>plu:</code>)</dd>
<dt>Version IRI</dt><dd><code>{html.escape(str(g.value(ONT, OWL.versionIRI)))}</code></dd>
<dt>Modified</dt><dd>{html.escape(str(g.value(ONT, DCTERMS.modified)))}</dd>
<dt>License</dt><dd><a href="{html.escape(str(g.value(ONT, DCTERMS.license)))}">CC BY 4.0</a></dd>
<dt>Turtle</dt><dd><a href="efo-plutchik.ttl">efo-plutchik.ttl</a> (current); by version: {vlinks}</dd>
<dt>Source</dt><dd><a href="{REPO_URL}">{REPO_URL}</a> (SHACL shapes, competency questions, label mappings, validation code)</dd>
</dl>
<nav><ul>
{chr(10).join(toc)}
</ul></nav>
{chr(10).join(body)}
</body>
</html>
"""


def targets():
    out = {DOCS / "index.html": render().encode(), DOCS / "efo-plutchik.ttl": SRC.read_bytes(), DOCS / ".nojekyll": b""}
    for v, p in versions().items():
        out[DOCS / v / "efo-plutchik.ttl"] = p.read_bytes()
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    stale = [p for p, b in targets().items() if not p.exists() or p.read_bytes() != b]
    if args.check:
        if stale:
            sys.exit("[stale] " + ", ".join(str(p.relative_to(ROOT)) for p in stale))
        print("[ok] docs/ is up to date")
        return
    for p, b in targets().items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b)
    print(f"[done] {len(targets())} files under docs/ ({len(stale)} changed)")


if __name__ == "__main__":
    main()
