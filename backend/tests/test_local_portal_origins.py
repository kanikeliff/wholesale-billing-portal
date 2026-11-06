from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, Client


class LocalPortalOriginTests(TestCase):
    def test_authenticated_mutations_accept_both_local_frontend_origins(self):
        user = get_user_model().objects.create_user(username="origin-test")
        for origin in ("http://localhost:5173", "http://127.0.0.1:5173"):
            self.assertIn(origin, settings.CSRF_TRUSTED_ORIGINS)
            self.assertIn(origin, settings.CORS_ALLOWED_ORIGINS)
            client = Client(enforce_csrf_checks=True)
            client.force_login(user)
            token = client.get("/api/v1/auth/csrf/").json()["csrfToken"]
            response = client.patch(
                "/api/v1/billing-records/00000000-0000-0000-0000-000000000000/fields/carrier/",
                data='{"value":"diagnostic"}', content_type="application/json",
                HTTP_ORIGIN=origin, HTTP_X_CSRFTOKEN=token,
            )
            self.assertEqual(response.status_code, 404, response.content)
        response = client.patch(
            "/api/v1/billing-records/00000000-0000-0000-0000-000000000000/fields/carrier/",
            data='{"value":"diagnostic"}', content_type="application/json",
            HTTP_ORIGIN="http://untrusted.example", HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 403)
