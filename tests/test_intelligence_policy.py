"""No network, API keys, or model calls in intelligence policy tests."""
import unittest

from core.intelligence_policy import (
    ASTRA, LOCAL, LUNA, SOL, RouteRequest, Workload, select_model,
)


class IntelligenceRoutingTests(unittest.TestCase):
    def test_defaults_fail_closed_without_local_model(self):
        route = select_model(RouteRequest(Workload.ROUTINE))
        self.assertEqual("unavailable", route.channel)
        self.assertIsNone(route.model)

    def test_default_is_offline_first_even_for_complex_tasks(self):
        for kind in Workload:
            route = select_model(RouteRequest(kind, local_ready=True))
            self.assertEqual(LOCAL, route.model)
            self.assertEqual("local", route.channel)

    def test_quality_switch_requires_cloud_enabled_and_approved(self):
        for enabled, approved in [(True, False), (False, True), (False, False)]:
            request = RouteRequest(
                Workload.DEEP, local_ready=True, online_enabled=enabled,
                online_approved=approved, prefer_high_quality=True,
                premium_approved=True,
            )
            self.assertEqual(LOCAL, select_model(request).model)

    def test_sensitive_data_does_not_leave_device_without_extra_approval(self):
        request = RouteRequest(
            Workload.DEEP, local_ready=True, online_enabled=True,
            online_approved=True, prefer_high_quality=True,
            sensitive=True, premium_approved=True,
        )
        self.assertEqual(LOCAL, select_model(request).model)

    def test_sensitive_data_unavailable_when_no_local_and_no_extra_approval(self):
        request = RouteRequest(
            Workload.CODING, online_enabled=True, online_approved=True,
            sensitive=True,
        )
        self.assertEqual("unavailable", select_model(request).channel)

    def test_routine_chooses_luna_when_online_opted_in(self):
        request = RouteRequest(
            Workload.ROUTINE, online_enabled=True, online_approved=True,
            available_online=(LUNA, SOL),
        )
        self.assertEqual(LUNA, select_model(request).model)

    def test_coding_chooses_sol(self):
        request = RouteRequest(
            Workload.CODING, online_enabled=True, online_approved=True,
            available_online=(LUNA, SOL),
        )
        self.assertEqual(SOL, select_model(request).model)

    def test_deep_chooses_sol_by_default(self):
        request = RouteRequest(
            Workload.DEEP, online_enabled=True, online_approved=True,
            available_online=(SOL, ASTRA),
        )
        self.assertEqual(SOL, select_model(request).model)

    def test_astra_requires_explicit_premium_approval(self):
        request = RouteRequest(
            Workload.DEEP, online_enabled=True, online_approved=True,
            premium_approved=True, available_online=(SOL, ASTRA),
        )
        self.assertEqual(ASTRA, select_model(request).model)

    def test_unavailable_cloud_models_do_not_invent_model_availability(self):
        request = RouteRequest(
            Workload.DEEP, online_enabled=True, online_approved=True,
            premium_approved=True, available_online=(LUNA,),
        )
        self.assertIsNone(select_model(request).model)

    def test_fallback_to_local_when_online_models_missing(self):
        request = RouteRequest(
            Workload.CODING, local_ready=True, online_enabled=True,
            online_approved=True, prefer_high_quality=True,
            available_online=(),
        )
        self.assertEqual(LOCAL, select_model(request).model)

    def test_invalid_flags_rejected(self):
        with self.assertRaises(TypeError):
            RouteRequest(Workload.DEEP, premium_approved="yes")
        with self.assertRaises(TypeError):
            RouteRequest("deep")


if __name__ == "__main__":
    unittest.main()
