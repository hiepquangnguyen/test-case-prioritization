import unittest
from scripts.stage4_design_audit import physical_split
from scripts.stage4_source_audit import declaration


def row(i,stage='linux',timestamp=None):
    return dict(project='p',pr_name='pr',build_id=str(i),stage_id=stage,
                build_timestamp=str(i if timestamp is None else timestamp))


class DesignAuditTests(unittest.TestCase):
    def test_physical_split_keeps_stages_together_and_ignores_outcomes(self):
        rows=[row(i,s) for i in range(20) for s in ('linux','windows')]
        assignment,ordered,bounds=physical_split(rows)
        self.assertEqual(len(ordered),20)
        self.assertEqual(sum(s=='warmup' for s in assignment.values()),4)
        self.assertEqual(sum(s=='development' for s in assignment.values()),6)
        self.assertEqual(sum(s=='reserved_confirmation' for s in assignment.values()),10)
        changed=[dict(r,outcome=1,build_result='ABORTED',duration=9876) for r in reversed(rows)]
        self.assertEqual(physical_split(changed),(assignment,ordered,bounds))

    def test_timestamp_ties_do_not_cross_split_boundary(self):
        rows=[row(i,timestamp=3 if i in (3,4) else i) for i in range(20)]
        assignment,_,_=physical_split(rows)
        self.assertEqual(assignment[('p','pr','3')],assignment[('p','pr','4')])
        with self.assertRaises(ValueError):physical_split([row(i,timestamp=0) for i in range(20)])

    def test_inconsistent_stage_start_fails(self):
        rows=[row(i) for i in range(20)]+[row(0,'windows',2)]
        with self.assertRaises(ValueError):physical_split(rows)

    def test_declared_source_package_and_comments(self):
        self.assertTrue(declaration(b'package org.example; public class Test {}','org.example.Test'))
        self.assertFalse(declaration(b'package other; public class Test {}','org.example.Test'))
        self.assertFalse(declaration(b'/* package org.example; class Test {} */','org.example.Test'))
        self.assertTrue(declaration(b'package org.example; public class Test {}','org.example.Test$Inner'))


if __name__=='__main__':unittest.main()
