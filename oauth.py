"""
OAuth helper functions or the P module. authlib is used as second OAuth
implementation because django-allauth isn't useable for obtaining consent from
someone who is not a user of the platform. Still, authlib is initialised based
on the client data from the allauth administration, so that there is only a
single source for this information
"""
import requests

from authlib.integrations.requests_client import OAuth2Session
from authlib.integrations.django_client import OAuth
from django.conf import settings

from constance import config

oauth = OAuth()
_initialized = False

def _ensure_registered():
   """
   Lazily register the authlib client using credentials
   from allauth's SocialApp table.

   Called at first-use rather than import time,
   because the DB isn't available during module loading.
   """
   global _initialized
   if _initialized:
      return

   from allauth.socialaccount.models import SocialApp

   app_name = config.MANUFACTURER_SOCIALAPP_NAME
   try:
      social_app = SocialApp.objects.get(name = app_name)
   except SocialApp.DoesNotExist as e:
      raise RuntimeError(
          f'SocialApp \'{app_name}\' not found. '
          f'Create it in Django admin under Social Applications.'
      ) from e

   if not social_app.settings.get('token_endpoint'):
      metadata_url = social_app.settings.get('server_url').rstrip('/') + '/.well-known/openid-configuration'
      resp = requests.get(metadata_url, timeout=10)
      resp.raise_for_status()
      metadata = resp.json()
      social_app.settings['token_endpoint'] = metadata['token_endpoint']
      if 'revocation_endpoint' in metadata:
         social_app.settings['revocation_endpoint'] = metadata['revocation_endpoint']
      social_app.save()

   oauth.register(
       name = 'manufacturer',
       client_id = social_app.client_id,
       client_secret = social_app.secret,
       server_metadata_url = social_app.settings.get('server_url').rstrip('/') + '/.well-known/openid-configuration',
       client_kwargs = {
           'scope': ' '.join(social_app.settings.get('scope'))
       },
   )
   _initialized = True


def get_client():
   _ensure_registered()
   return oauth.manufacturer

def get_credentials():
   """
   Return (client_id, client_secret, token_endpoint) for use in standalone
   OAuth2Session instances (e.g., API calls with token refresh).
   Calls _ensure_registered() to guarantee token_endpoint is populated.
   """
   _ensure_registered()
   from allauth.socialaccount.models import SocialApp

   social_app = SocialApp.objects.get(name = config.MANUFACTURER_SOCIALAPP_NAME)
   return social_app.client_id, social_app.secret, social_app.settings['token_endpoint']


def revoke_token(token_value):
   """
   Attempt RFC 7009 token revocation at the manufacturer's revocation endpoint.
   No-op if the endpoint wasn't advertised in the discovery document initially.
   Raises on HTTP error — caller should decide whether to swallow it.
   """
   _ensure_registered()
   from allauth.socialaccount.models import SocialApp

   social_app = SocialApp.objects.get(name = config.MANUFACTURER_SOCIALAPP_NAME)
   endpoint = social_app.settings.get('revocation_endpoint')
   if not endpoint:
      return False

   session = OAuth2Session(*get_credentials())
   resp = session.revoke_token(
      endpoint,
      token = token_value,
      token_type_hint = "refresh_token",
   )
   resp.raise_for_status()
   return True
