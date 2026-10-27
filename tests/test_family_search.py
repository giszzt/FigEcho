"""Regression coverage for family grouping without breaking legacy search."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from test_style_library import style_library as lib, make_job, add_args


class FamilySearchTests(unittest.TestCase):
    def entry(self, slug, family, variant, expression):
        return dict(slug=slug, name=slug, aliases=[], tags=[], best_for=[], status='candidate', portability_status='untested', organization=dict(family_id=family, family_name=family, variant_id=variant, variant_name=variant, facets=dict(use_cases=['research-proposal'], archetypes=['roadmap'], expressions=[expression])))

    def search(self, entries, **kw):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'catalog.json').write_text(json.dumps({'templates':entries}), encoding='utf-8')
            args = dict(library=root, query='', limit=10, include_archived=False)
            args.update(kw)
            return lib.search_catalog(SimpleNamespace(**args))

    def test_group_limit_does_not_drop_matching_sibling_variants(self):
        entries=[self.entry('a','family','text','text-framework'),self.entry('b','family','illustrated','illustrated-mechanism'),self.entry('c','other','text','text-framework')]
        result=self.search(entries,limit=1)
        self.assertEqual(len(result['results']),1)
        self.assertEqual(len(result['groups']),1)
        self.assertEqual(len(result['groups'][0]['variants']),2)

    def test_explicit_illustrated_preference_and_intersection_filters(self):
        entries=[self.entry('a','family','text','text-framework'),self.entry('b','family','illustrated','illustrated-mechanism')]
        result=self.search(entries,query='科研申报技术路线带图示')
        self.assertEqual(result['groups'][0]['recommended_slug'],'b')
        result=self.search(entries,expressions=['illustrated-mechanism'],archetypes=['roadmap'])
        self.assertEqual([x['slug'] for x in result['results']],['b'])
        self.assertEqual(self.search(entries,archetypes=['feedback'])['groups'],[])

    def test_legacy_pack_and_archived_visibility(self):
        entry=self.entry('legacy','family','text','text-framework');del entry['organization']
        result=self.search([entry])
        self.assertEqual(result['groups'][0]['family_id'],'legacy')
        entry['status']='archived'
        self.assertFalse(self.search([entry])['groups'])
        self.assertTrue(self.search([entry],include_archived=True)['groups'])

    def test_classification_preserves_prompt_and_refresh_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);job=make_job(root);library=root/'library'
            lib.add_pack(add_args(library,job))
            slug='pastel-research-grid'
            _,before=lib.get_pack(library,slug)
            lib.classify_pack(SimpleNamespace(library=library,slug=slug,family_id='research',family_name='科研',variant_id='illustrated',variant_name='图示版',use_cases=['paper']))
            lib.refresh_pack(SimpleNamespace(library=library,slug=slug))
            _,after=lib.get_pack(library,slug)
            self.assertEqual(before['prompt_sha256'],after['prompt_sha256'])
            self.assertEqual(after['organization']['facets']['use_cases'],['paper'])
            self.assertTrue(lib.validate_library(library)['ok'])

    def test_unknown_taxonomy_is_rejected(self):
        value=self.entry('a','family','text','text-framework')['organization']
        value['facets']['expressions']=['made-up']
        with self.assertRaises(ValueError):lib.validate_organization(value)

    def test_family_conflict_rejected_before_pack_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);job=make_job(root);library=root/'library'
            lib.add_pack(add_args(library,job))
            slug='pastel-research-grid'
            pack_dir,pack=lib.get_pack(library,slug)
            baseline=(pack_dir/'style-pack.json').read_bytes()
            catalog=lib.ensure_library(library)
            sibling=self.entry('sibling','shared','text','text-framework')
            catalog['templates'].append(sibling)
            lib.atomic_json(library/'catalog.json',catalog)
            with self.assertRaisesRegex(ValueError,'variant_id'):
                lib.classify_pack(SimpleNamespace(library=library,slug=slug,family_id='shared',family_name='shared',variant_id='text'))
            with self.assertRaisesRegex(ValueError,'family_name'):
                lib.classify_pack(SimpleNamespace(library=library,slug=slug,family_id='shared',family_name='conflict',variant_id='new'))
            self.assertEqual(baseline,(pack_dir/'style-pack.json').read_bytes())


if __name__=='__main__':unittest.main()
