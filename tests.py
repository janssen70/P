"""
Tests for the P (service platform) app.

   python3 manage.py test P
"""

import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils import timezone

from utilities.core.oauth2 import TokenError
from utilities.testing.base import MyTestCaseBase

from .models import EndUser, OAuthToken, Service

class ServicesAccessibleJsonTests(MyTestCaseBase):

   def setUp(self):
      self.user = self.new_user('1')
      self.admin = self.new_user('2')
      perm = Permission.objects.get(
         content_type = ContentType.objects.get_for_model(Service),
         codename = 'view_service')
      self.admin.user_permissions.add(perm)

      self.end_user = EndUser.objects.create(email = 'enduser@test.nl')
      consented_token = OAuthToken.objects.create(access_token = 'tok1', revoked = False)
      revoked_token = OAuthToken.objects.create(access_token = 'tok2', revoked = True)

      self.consented_service = Service.objects.create(
         end_user = self.end_user, description = 'Consented', oauth_token = consented_token)
      self.revoked_service = Service.objects.create(
         end_user = self.end_user, description = 'Revoked', oauth_token = revoked_token)
      self.unconsented_service = Service.objects.create(end_user = self.end_user)

      self.url = reverse('p-services-accessible-json')

   def test_requires_login(self):
      self.validate_get_302(self.url)

   def test_requires_view_service_permission(self):
      self.do_site_login(self.user.username, 'pass')
      self.validate_get_403(self.url)

   def test_returns_only_consented_services(self):
      self.do_site_login(self.admin.username, 'pass')
      content = self.validate_get_okay(self.url)
      data = json.loads(content)
      self.assertEqual(len(data), 1)
      self.assertEqual(data[0]['id'], str(self.consented_service.pk))
      self.assertEqual(data[0]['label'], 'enduser@test.nl — Consented')

   def test_label_falls_back_when_no_description(self):
      self.consented_service.description = ''
      self.consented_service.save()
      self.do_site_login(self.admin.username, 'pass')
      data = json.loads(self.validate_get_okay(self.url))
      self.assertEqual(data[0]['label'], 'enduser@test.nl')

   def test_empty_list_when_none_consented(self):
      self.consented_service.delete()
      self.do_site_login(self.admin.username, 'pass')
      self.assertEqual(json.loads(self.validate_get_okay(self.url)), [])


class OAuthTokenGetTokenLockingTests(MyTestCaseBase):
   """
   Covers the Redis-lock path added to OAuthToken.get_token() to serialize
   concurrent refreshes of the same token.
   """

   def setUp(self):
      self.token = OAuthToken.objects.create(
         access_token = 'stale',
         refresh_token = 'refresh-1',
         expires_at = timezone.now() - timedelta(minutes = 1),
      )

   def _mock_redis_client(self, acquired):
      lock = MagicMock()
      lock.acquire.return_value = acquired
      client = MagicMock()
      client.lock.return_value = lock
      return client, lock

   def test_skips_refresh_if_already_refreshed_while_waiting_for_lock(self):
      # Simulate a concurrent request that wins the race and writes a fresh
      # token while this call is waiting to acquire the lock.
      def acquire_side_effect(*args, **kwargs):
         OAuthToken.objects.filter(pk = self.token.pk).update(
            access_token = 'fresh', expires_at = timezone.now() + timedelta(hours = 1)
         )
         return True

      client, lock = self._mock_redis_client(acquired = True)
      lock.acquire.side_effect = acquire_side_effect
      with patch('P.models._redis_client', client), \
           patch('P.models.get_credentials') as mock_get_credentials:
         self.assertEqual(self.token.get_token(), 'fresh')
         mock_get_credentials.assert_not_called()
         lock.release.assert_called_once()

   def test_raises_if_lock_not_acquired(self):
      client, lock = self._mock_redis_client(acquired = False)
      with patch('P.models._redis_client', client):
         with self.assertRaises(TokenError):
            self.token.get_token()
      lock.release.assert_not_called()

# vim: set nowrap sw=3 sts=3 et fdm=marker:
