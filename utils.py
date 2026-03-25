"""
Some utility functions for the P module
"""
from datetime import datetime, timezone as tz

from django.core.serializers.json import Serializer
from allauth.account.models import EmailAddress


def epoch_to_datetime(epoch):
   if epoch is None:
      return None
   return datetime.fromtimestamp(epoch, tz=tz.utc)

# -------------------------------------------------------------------------------
#
#   End-user helpers                                                        {{{1
#
# -------------------------------------------------------------------------------

def get_user_enduser_emails(user):
   """
   Return all email addresses linked to this user via allauth, plus user.email
   as a fallback for accounts created outside allauth.
   """
   emails = list(EmailAddress.objects.filter(user=user).values_list('email', flat=True))
   if user.email and user.email not in emails:
      emails.append(user.email)
   return emails


# -------------------------------------------------------------------------------
#
#   Serializers                                                             {{{1
#
# -------------------------------------------------------------------------------

def _get_consent_request_token(obj):
   if not obj.needs_consent:
      return None
   try:
      return str(obj.consent_request.token)
   except obj.__class__.consent_request.RelatedObjectDoesNotExist:
      return None


class ServiceSerializer(Serializer):
   def get_dump_object(self, obj):
      data = self._current or {}
      data.update({
         'id': str(obj.pk),
         'employee': '' if obj.employee is None else str(obj.employee),
         'employee_id': None if obj.employee is None else obj.employee.pk,
         'end_user': str(obj.end_user),
         'end_user_id': obj.end_user.pk,
         'description': obj.description,
         'created_at': obj.created_at.isoformat(),
         'consent': not obj.needs_consent,
         'consent_request_token': _get_consent_request_token(obj),
      })
      return data

# vim: set nowrap sw=3 sts=3 et fdm=marker:
