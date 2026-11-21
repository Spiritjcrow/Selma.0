import unittest
from copy import deepcopy
from selma_tanka_optimizer import (read_rows,validate_config,score_rows,select_balanced,filepath_risk,DEFAULT_WEIGHTS)

class CoordinationTests(unittest.TestCase):
    def setUp(self):
        self.rows=[{
           'path':f'workspace/ws1/{name}','bytes':'100','sha256':'a'*64,
           'category':'workspace','search_indexed':'1','proposed_destination':lane,
           'integration_status':'PENDING_REVIEW','notes':''
        } for name,lane in [ ('agent_core.py','SelmaOS / Android agent'),
                             ('agent_tests.py','SelmaOS / Android agent'),
                             ('bridge.py','SelmaOS / Android agent'),
                             ('other.py','Workspace triage queue')]]
    def test_weights(self):
        self.assertEqual(validate_config({'weights':DEFAULT_WEIGHTS}),DEFAULT_WEIGHTS)
        with self.assertRaises(ValueError):validate_config({'weights':dict(DEFAULT_WEIGHTS,goal=2)})
    def test_inference_is_provisional(self):
        scored,inf=score_rows(self.rows,DEFAULT_WEIGHTS)
        self.assertEqual(scored[-1]['candidate_lane'],'SelmaOS / Android agent')
        self.assertEqual(scored[-1]['lane_source'],'INFERRED_FROM_WORKSPACE')
        self.assertLess(scored[-1]['lane_confidence'],1)
        self.assertEqual(scored[-1]['integration_status'],'PENDING_REVIEW')
    def test_sensitive_gate(self):
        record=deepcopy(self.rows[0]);record['path']='sessions/personal.jsonl';record['category']='sessions';record['integration_status']='RESTRICTED'
        self.assertEqual(filepath_risk(record),'RESTRICTED')
        output,_=score_rows(self.rows+[record],DEFAULT_WEIGHTS)
        self.assertEqual(output[-1]['score'],0)
        self.assertNotIn(output[-1]['record_id'],{x['record_id'] for x in select_balanced(output,20)})
    def test_deterministic_sort_independent(self):
        a,_=score_rows(self.rows,DEFAULT_WEIGHTS)
        b,_=score_rows(list(reversed(self.rows)),DEFAULT_WEIGHTS)
        self.assertEqual({r['record_id']:r['score'] for r in a},{r['record_id']:r['score'] for r in b})
        self.assertEqual([r['record_id'] for r in select_balanced(a,4)],
                         [r['record_id'] for r in select_balanced(b,4)])
    def test_score_range_and_readiness(self):
        x,_=score_rows(self.rows,DEFAULT_WEIGHTS)
        y=deepcopy(self.rows);y[0]['search_indexed']='0'
        z,_=score_rows(y,DEFAULT_WEIGHTS)
        self.assertGreater(x[0]['score'],z[0]['score'])
        self.assertTrue(all(0<=a['score']<=100 for a in x))
    def test_private_patterns(self):
        row=deepcopy(self.rows[0]);row['path']='workspace/ws1/turn_history/raw/chunk_01.md'
        self.assertEqual(filepath_risk(row),'PRIVATE_REVIEW')
    def test_real_register_unique(self):
        from pathlib import Path
        path=Path(__file__).with_name('TANKA_ROUTING_REGISTER_2026-11-21.csv')
        if path.exists():self.assertEqual(len(read_rows(path)),848)

if __name__=='__main__':unittest.main()