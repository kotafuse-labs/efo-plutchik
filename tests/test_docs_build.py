"""docs/ (reference page and served copies of the ontology) is in sync with ontology/ and releases/."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_docs_are_up_to_date():
    r = subprocess.run([sys.executable, "scripts/build_docs.py", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_every_term_has_an_anchor():
    from rdflib import Graph, URIRef
    ns = "https://w3id.org/efo-plutchik#"
    g = Graph().parse(ROOT / "ontology" / "efo-plutchik.ttl")
    page = (ROOT / "docs" / "index.html").read_text()
    terms = {str(s)[len(ns):] for s in g.subjects() if isinstance(s, URIRef) and str(s).startswith(ns) and str(s) != ns}
    assert len(terms) == 93
    assert all(f'id="{t}"' in page for t in terms)
