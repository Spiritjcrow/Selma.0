import unittest
from dataclasses import dataclass

@dataclass(frozen=True)
class Request:
    agent: str
    action: str
    expires: int

def authorize(request, now, stopped, grants):
    return not stopped and now < request.expires and (request.agent, request.action) in grants

class AssuranceTests(unittest.TestCase):
    def setUp(self):
        self.grants = frozenset({('builder','test')})
        self.request = Request('builder','test',10)
    def test_allowed(self):
        self.assertTrue(authorize(self.request,1,False,self.grants))
    def test_shutdown(self):
        self.assertFalse(authorize(self.request,1,True,self.grants))
    def test_expiry(self):
        self.assertFalse(authorize(self.request,10,False,self.grants))
    def test_unknown_action(self):
        self.assertFalse(authorize(Request('builder','deploy',10),1,False,self.grants))
    def test_unknown_agent(self):
        self.assertFalse(authorize(Request('unknown','test',10),1,False,self.grants))

if __name__ == '__main__': unittest.main(verbosity=2)
