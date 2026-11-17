"""Offline checks for the HyperCore visual-system slice; Python stdlib only."""
from html.parser import HTMLParser
from pathlib import Path
import json
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]

class AssetParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images=[]
        self.scripts=[]
    def handle_starttag(self, tag, attrs):
        d=dict(attrs)
        if tag=='img': self.images.append(d.get('src',''))
        if tag=='script': self.scripts.append(d.get('src'))

class HyperCoreStaticTests(unittest.TestCase):
    def test_html_exists_and_tracks_eight_evidence_gates(self):
        html=(ROOT/'index.html').read_text(encoding='utf-8')
        self.assertIn('Selma° HyperCore', html)
        self.assertIn('NOT VERIFIED',html)
        self.assertIn('Unverified user-supplied references',html)
        for gate in ('source','runner','sdk','lint','tests','apk','sha256','install'):
            self.assertIn("['"+gate+"'",html)
        self.assertNotIn('fetch(', html)
        self.assertNotIn('eval(', html)
    def test_referenced_assets_exist(self):
        parser=AssetParser();parser.feed((ROOT/'index.html').read_text(encoding='utf-8'))
        self.assertEqual(len(parser.images),5)
        self.assertEqual(parser.scripts,[None])
        for path in parser.images:
            self.assertTrue((ROOT/path).is_file(),path)
    def test_svg_xml_and_accessible_names(self):
        icons=list((ROOT/'assets/icons').glob('*.svg'))
        self.assertEqual(len(icons),7)
        self.assertIn('evidence-provenance.svg', {path.name for path in icons})
        ns='{http://www.w3.org/2000/svg}'
        for path in icons:
            root=ET.parse(path).getroot()
            self.assertEqual(root.tag,ns+'svg')
            label=root.attrib.get('aria-label')
            labelledby=root.attrib.get('aria-labelledby','').split()
            if not label:
                ids={node.attrib['id'] for node in root.iter() if node.tag in (ns+'title',ns+'desc') and 'id' in node.attrib}
                self.assertTrue(labelledby and all(ref in ids for ref in labelledby),path.name)
            self.assertFalse(any(node.tag in (ns+'script',ns+'foreignObject') for node in root.iter()))
    def test_tokens_are_parseable(self):
        tokens=json.loads((ROOT/'assets/tokens.json').read_text(encoding='utf-8'))
        self.assertEqual(tokens['colors']['coreBlue'],'#0078FF')
        self.assertFalse(tokens['integration_verified']) # old design kit metadata remains historical

if __name__=='__main__': unittest.main()
