"""
Models for the P Platform
"""
import uuid

from django.conf import settings
from django.db import models

from authlib.integrations.requests_client import OAuth2Session

from utilities.core.oauth2 import TokenError

from .oauth import get_credentials
from .utils import epoch_to_datetime, get_user_enduser_emails

class EndUser(models.Model):
   """
   Represents an end user who owns devices. May or may not have a portal account.

   The use of portal_account isn't well-defined in this demonstrator.
   """
   email = models.EmailField(unique=True)
   portal_account = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True,
                                         on_delete=models.SET_NULL, related_name="enduser_profile")

   def __str__(self):
      return self.email

   @classmethod
   def for_user(cls, user):
      """
      Class-method to get or create an EndUser matching user.email.

      Sets portal_account only on creation; falls back without it if the
      OneToOneField is already taken by another EndUser record. This detail can be
      ignored for now.
      """
      from django.db import IntegrityError, transaction
      try:
         with transaction.atomic():
            enduser, _ = cls.objects.get_or_create(
               email=user.email,
               defaults={'portal_account': user},
            )
      except IntegrityError:
         enduser, _ = cls.objects.get_or_create(email=user.email)
      return enduser

class Service(models.Model):
   """
   This model represents an agreed Service. It relates to a specific <end_user>,
   the consent request is sent to that e-mail address. The token that is
   received in return gets saved in <oauth_token>. That token determines which
   organisation it is that the access works on

   The use of the employee field isn´t well-defined in this demonstrator. All
   users with P.view_service permission are allowed to view all services. In
   the live demo this is done by assigning a user to a specific group with
   that permission.
   """
   id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
   employee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                on_delete=models.SET_NULL, related_name="services")
   end_user = models.ForeignKey(EndUser, on_delete=models.CASCADE, related_name="services")
   description = models.TextField(blank=True)
   created_at = models.DateTimeField(auto_now_add=True)

   oauth_token = models.OneToOneField("OAuthToken", null=True, blank=True, on_delete=models.SET_NULL, related_name="service")

   @property
   def needs_consent(self):
      if self.oauth_token is None:
         return True
      return self.oauth_token.revoked

   def __str__(self):
      return f"{self.employee} → {self.end_user} ({self.id})"

   def can_revoke(self, user):
      """
      Determines whether <user> is entitled to revoke consent on this service
      """
      if user.has_perm('P.change_service') or self.end_user.email in get_user_enduser_emails(user):
         return True
      # The employee marked at the service can also revoke
      return user.has_perm('P.view_service') and self.employee == user

   def can_delete(self, user):
      """
      Similar to can_revoke, bit stricter. The details are not so important for the
      demonstrator application
      """
      return user.has_perm('P.change_service') or self.end_user.email in get_user_enduser_emails(user)


class OAuthToken(models.Model):
   """
   Stored independently — Service points to it.
   No back-reference needed for the core flow.
   """
   access_token = models.TextField()
   refresh_token = models.TextField(blank=True)
   token_type = models.CharField(max_length=20, default="Bearer")
   expires_at = models.DateTimeField(null=True, blank=True)
   id_token = models.TextField(blank=True)
   extra_data = models.JSONField(default=dict, blank=True)
   revoked = models.BooleanField(default=False)
   updated_at = models.DateTimeField(auto_now=True)

   def is_expired(self):
      from django.utils import timezone
      if not self.expires_at:
         return False
      return timezone.now() >= self.expires_at

   def as_authlib_token(self):
      return {
         "access_token": self.access_token,
         "refresh_token": self.refresh_token,
         "token_type": self.token_type,
         "expires_at": self.expires_at.timestamp() if self.expires_at else None,
      }

   def mark_expired(self):
      """
      Force the token to appear expired so that get_token() will try obtain a
      fresh one
      """
      from django.utils import timezone
      self.expires_at = timezone.now()
      self.save(update_fields=["expires_at"])

   def get_token(self):
      """
      Returns the access_token or refreshes it first if needed.
      Mutates and saves the object in place.
      """
      if not self.is_expired() and not self.revoked:
         return self.access_token

      if not self.refresh_token:
         if not self.revoked:
            self.revoked = True
            self.save(update_fields = ['revoked'])
         raise TokenError('No refresh token')

      client_id, client_secret, token_endpoint = get_credentials()
      session = OAuth2Session(client_id, client_secret, token=self.as_authlib_token())
      try:
         new_token = session.refresh_token(token_endpoint, refresh_token=self.refresh_token)
      except Exception as e:
         self.revoked = True
         self.save(update_fields = ['revoked'])
         raise TokenError(f'Failed to refresh token: {e}') from e

      self.access_token = new_token['access_token']
      self.refresh_token = new_token.get('refresh_token', self.refresh_token)
      self.expires_at = epoch_to_datetime(new_token.get('expires_at'))
      self.revoked = False
      self.save()
      return self.access_token

class ConsentRequest(models.Model):
   """
   Tracks consent email state per service. Prevents duplicate emails, enables
   resend control.

   <token> here is the email link token, NOT the OAuth token. The link in the
   e-mail will first land the user on our website. It is confusing/feels
   suspicious when the e-mail links to axis directly or that our website
   immediately redirects.

   The end-user first lands on a page which confirms what is going to happen,
   there a button needs to be present to commence consent-process. See
   views.oauth_start()
   """
   service = models.OneToOneField(
       Service,
       on_delete=models.CASCADE,
       related_name="consent_request",
   )
   requested_at = models.DateTimeField(null=True, blank=True)
   token = models.UUIDField(default=uuid.uuid4, unique=True)

   def is_pending(self):
      return self.requested_at is not None and self.service.needs_consent

# vim: set nowrap sw=3 sts=3 et fdm=marker:
