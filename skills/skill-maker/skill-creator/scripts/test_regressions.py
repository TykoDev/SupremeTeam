"""Regression tests for creator validation, packaging, and pipe handling."""
import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from scripts.quick_validate import validate_skill
from scripts.package_skill import package_skill
from scripts.run_eval import run_single_query

class CreatorRegressionTests(unittest.TestCase):
    def test_invalid_frontmatter(self):
        with tempfile.TemporaryDirectory() as root:
            for fields in ['name: ""\ndescription: Good', 'name: sample\ndescription: "  "', *[f'name: sample\ndescription: Good\ncompatibility: {v}' for v in ('false','0','[]','null')], 'name: sample\ndescription: Good\n7: foo\nunknown: bar']:
                with self.subTest(fields=fields):
                    (Path(root)/'SKILL.md').write_text(f'---\n{fields}\n---\n',encoding='utf-8')
                    self.assertFalse(validate_skill(root)[0])

    def test_package_excludes_itself(self):
        with tempfile.TemporaryDirectory() as root:
            skill=Path(root)/'sample'
            skill.mkdir()
            (skill/'SKILL.md').write_text('---\nname: sample\ndescription: Good\n---\n',encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                output=package_skill(skill,skill)
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(archive.namelist(),['sample/SKILL.md'])

    def run_child(self, body, timeout=3, exited=False):
        original=subprocess.Popen
        children=[]
        with tempfile.TemporaryDirectory() as root:
            def launch(*args,**kwargs):
                child=original([sys.executable,'-c',body],**kwargs)
                children.append(child)
                if exited:
                    child.wait(timeout=3)
                return child
            with patch('scripts.run_eval.subprocess.Popen',side_effect=launch):
                result=run_single_query('query','sample','Description',timeout,root)
            self.assertFalse(list((Path(root)/'.claude'/'commands').glob('*.md')))
            self.assertIsNotNone(children[0].poll())
            return result

    def test_already_exited_final_line(self):
        body="from pathlib import Path; import json; name=next(Path('.claude/commands').glob('*.md')).stem; print(json.dumps({'type':'assistant','message':{'content':[{'type':'tool_use','name':'Skill','input':{'skill':name}}]}}),end='')"
        self.assertTrue(self.run_child(body,exited=True))

    def test_running_pipe(self):
        body="from pathlib import Path; import json,time; name=next(Path('.claude/commands').glob('*.md')).stem; print(json.dumps({'type':'assistant','message':{'content':[{'type':'tool_use','name':'Read','input':{'file_path':name}}]}}),flush=True); time.sleep(10)"
        self.assertTrue(self.run_child(body))

    def test_timeout_cleanup(self):
        self.assertFalse(self.run_child('import time; time.sleep(10)',timeout=0.1))

if __name__=='__main__':
    unittest.main()
