"""
Tests for the P (service platform) app.

   python3 manage.py test P
"""

import json

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

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

# vim: set nowrap sw=3 sts=3 et fdm=marker:
