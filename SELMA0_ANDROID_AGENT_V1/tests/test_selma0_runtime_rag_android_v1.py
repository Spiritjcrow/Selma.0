import importlib
import os
import shutil
import sys
import tempfile
import types
import unittest


class FakeRouter:
    def __init__(self):
        self.local_base = "http://127.0.0.1:8080/v1"
        self.online_base = ""
        self.online_model = ""
        self.last_messages = []

    def reply(self, messages):
        self.last_messages = messages
        return {"text": "local answer", "route": "local", "error": None}


class FakeGuardian:
    audit_path = "/tmp/selma0-test-audit.jsonl"

    def status(self):
        return {"active": True}


class Selma0RuntimeRagAndroidV1Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = tempfile.mkdtemp(prefix="selma0-rag-runtime-")
        os.environ["SELMA0_BASE_V1"] = cls.base

        router_module = types.ModuleType("selma0_llm_router_android_v1")
        router_module.Selma0LLMRouterAndroidV1 = FakeRouter
        guardian_module = types.ModuleType("selma0_safety_guardian_android_v1")
        guardian_module.Selma0SafetyGuardianAndroidV1 = FakeGuardian
        sys.modules[router_module.__name__] = router_module
        sys.modules[guardian_module.__name__] = guardian_module
        sys.modules.pop("selma0_memory_android_v1", None)
        cls.runtime = importlib.import_module("selma0_runtime_android_v1")

    @classmethod
    def tearDownClass(cls):
        cls.runtime.MEMORY_V1.close()
        for name in (
            "selma0_runtime_android_v1",
            "selma0_memory_android_v1",
            "selma0_llm_router_android_v1",
            "selma0_safety_guardian_android_v1",
        ):
            sys.modules.pop(name, None)
        os.environ.pop("SELMA0_BASE_V1", None)
        shutil.rmtree(cls.base)

    def setUp(self):
        self.runtime.MEMORY_V1.clear()
        self.runtime.ROUTER_V1.last_messages = []

    def test_chat_injects_retrieved_memory_as_untrusted_reference(self):
        self.runtime.MEMORY_V1.add(
            "user",
            "My emergency guardian contact is stored on this phone.",
        )

        result = self.runtime.SELMA0_V1.chat("Where is my guardian contact stored?")

        self.assertEqual("local answer", result["text"])
        reference = self.runtime.ROUTER_V1.last_messages[1]
        self.assertEqual("system", reference["role"])
        self.assertIn("untrusted reference data", reference["content"])
        self.assertIn("stored on this phone", reference["content"])

    def test_status_reports_retrieval_mode(self):
        status = self.runtime.SELMA0_V1.status()
        self.assertIn(
            status["memory_retrieval"],
            ("sqlite-fts5", "bounded-lexical-fallback"),
        )


if __name__ == "__main__":
    unittest.main()
