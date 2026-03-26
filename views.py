import json
from typing import Union, Tuple

from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth import get_user_model
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView
from django.db.models import Q
from authlib.integrations.django_client import OAuthError

from utilities.core.logger import LOG_INFO
from utilities.core.authenticator import Authenticator
from utilities.core.signuporlogin import add_signuporlogin_context
from utilities.core.oauth2 import TokenError
from utilities.web.forms import make_timezone_aware
from utilities.web.views import MyAddView, MyEditView, SearchableListView
from utilities.core.env import require_env
from usercontent.views import embedded_section_view
from tenants.settings import tenant

from .forms import EndUserForm, MyServiceForm, ServiceForm, ServiceSearchForm
from .models import ConsentRequest, EndUser, OAuthToken, Service
from .oauth import get_client, revoke_token
from .utils import ServiceSerializer, epoch_to_datetime, get_user_enduser_emails
from .serviceclient import OrganizationClient, ServerError

User = get_user_model()

ACC_GRAPHQL_API_KEY = require_env('ACC_GRAPHQL_API_KEY')

# -------------------------------------------------------------------------------
#
#   Permission mixin                                                        {{{1
#
# -------------------------------------------------------------------------------

class ServiceAdminRequired(PermissionRequiredMixin):
   """
   For permission check in the Service Provider-related class-based views
   """
   permission_required = 'P.view_service'

# -------------------------------------------------------------------------------
#
#   Utilities                                                                {{{1
#
# -------------------------------------------------------------------------------

def Log(class_, request, string):
   tenant.LOGGER.logr(class_, request, string)

class P_OAuth2Authenticator(Authenticator):
   """
   OAuth2-based authenticator that builds on the OAuthToken model of this
   module
   """

   def __init__(self, token_instance: OAuthToken):
      self.token_instance = token_instance

   def token(self):
      """
      Reuse or recreate the session
      """
      return self.token_instance.get_token()

def list_devices(service: Union[Service, str]) -> dict:
   """
   Determine organisation arn of the Service and run GraphQL query to obtain
   the devices.
   """
   if not isinstance(service, Service):
      service = get_object_or_404(Service.objects.select_related('oauth_token'), id = service)

   org_arn = service.oauth_token.extra_data['axis:organization']
   conn = OrganizationClient(
      authenticator = P_OAuth2Authenticator(service.oauth_token),
      api_key = ACC_GRAPHQL_API_KEY,
      org_arn = org_arn,
      org_label = 'unknown',
      logger = tenant.LOGGER
   )
   return conn.list_devices(org_arn)

def do_revoke(service: Service, user: User) -> Tuple[bool, str]:
   """
   Signal to the identity provider that a certain token is not required
   anymore.

   Returns result + message_if_result_false
   """
   if (token := service.oauth_token):
      try:
         if not revoke_token(token.refresh_token or token.access_token):
            return False, _('Could not revoke consent')
      except Exception as e:
         return False, str(e)

      try:
         cr = service.consent_request
         cr.requested_at = None
         cr.save(update_fields = ['requested_at'])
      except ConsentRequest.DoesNotExist:
         pass

      service.oauth_token = None
      service.save(update_fields = ['oauth_token'])
      token.delete()
   return True, ''

# -------------------------------------------------------------------------------
#
#   Services management views                                               {{{1
#
# -------------------------------------------------------------------------------

SERVICES_OVERVIEW_TRANSLATIONS = {
   'Open': _('Open'),
   'Properties': _('Properties'),
   'Delete': _('Delete'),
   'DeleteService': _('Delete service'),
   'SureToDelete': _('Are you sure you want to delete service <b>{0}</b>?'),
   'ServiceDeleted': _('Service has been deleted'),
   'AddService': _('Add service'),
   'AddEndUser': _('Add end user'),
   'ErrorSearching': _('Error during search'),
   'Yes': _('Yes'),
   'No': _('No'),
   'Processing': _('Processing...'),
   'Pause': _('Pause'),
   'PauseService': _('Pause Service'),
   'SureToPause': _('Are you sure you want to revoke consent for service <b>{0}</b>?'),
   'ServicePaused': _('Service is paused'),
}


class ServicesOverview(ServiceAdminRequired, TemplateView):
   template_name = 'P/services_overview.html'

   def get_context_data(self, **kwargs):
      context = super().get_context_data(**kwargs)
      context['form'] = ServiceSearchForm(self.request)
      context['form_id'] = 'search_form'
      context['form_submit'] = _('Search')
      context['form_grid'] = 'pure-u-md-1-3'
      context['form_fieldclass'] = 'pure-u-23-24'
      context['translations'] = SERVICES_OVERVIEW_TRANSLATIONS
      return context


class Services_ListJson(ServiceAdminRequired, SearchableListView):
   """
   Following a pattern from other code. Search functionality isn't very
   uisefull with just a handfull of items in the list
   """

   def get_form(self):
      return ServiceSearchForm(self.request, self.request.GET)

   def get_filters_from_form(self, f):
      q = Q()
      description = f.cleaned_data.get('description')
      if description:
         q &= Q(description__icontains = description)
      created_after = f.cleaned_data.get('created_after')
      if created_after:
         q &= Q(created_at__gte = make_timezone_aware(created_after))
      created_before = f.cleaned_data.get('created_before')
      if created_before:
         q &= Q(created_at__lte = make_timezone_aware(created_before))
      return q

   def get_queryset(self):
      return Service.objects.select_related('employee', 'end_user', 'oauth_token').all().order_by('created_at')

   def serialize(self, query):
      return ServiceSerializer().serialize(query, fields = ())


class ServiceAdd(ServiceAdminRequired, MyAddView):
   form_class = ServiceForm
   form_name = 'serviceform'
   form_submit = _('Add')

   def my_init(self):
      self.initial = {'employee': self.request.user.pk}

   def return_value(self, obj):
      data = json.loads(ServiceSerializer().serialize([obj], fields = ()))
      return JsonResponse({'data': data})


class ServiceEdit(ServiceAdminRequired, MyEditView):
   form_class = ServiceForm
   form_name = 'serviceform'
   form_submit = _('Save')

   def get_object(self):
      return get_object_or_404(Service, pk = self.kwargs['service_id'])

   def return_value(self, obj):
      data = json.loads(ServiceSerializer().serialize([obj], fields = ()))
      return JsonResponse({'data': data})


class EndUserAdd(ServiceAdminRequired, MyAddView):
   form_class = EndUserForm
   form_name = 'enduserform'
   form_submit = _('Add')

   def return_value(self, obj):
      return JsonResponse({'id': obj.pk, 'email': obj.email})


# ------------------------------------------------------------------------------
#
#    End-user-facing views (no login required)                              {{{1
#
# ------------------------------------------------------------------------------


class LandingPage(TemplateView):
   template_name = 'P/landing_page.html'

   def get_context_data(self, **kwargs):
      context = embedded_section_view(self.request, 'embedded', 'p_landing_page')
      return context

def oauth_start(request, consent_token):
   """
   The consent-email to an Enduser contains a link to this view. It shows a
   page with some explanation and a button that will started the oath
   process.

   The page serves two purposes:

   - Set the 'oauth_consent_token' session state. Once done, we might redirect
     as well directly to axis.com, but:
   - By pausing on this page the enduser can visually confirm it's
     really the expected service provider he is dealing with.
   """
   consent_req = get_object_or_404(ConsentRequest.objects.select_related('service'), token = consent_token)

   if not consent_req.requested_at:
      return HttpResponseForbidden('This link is not active.')

   client = get_client()
   callback_url = request.build_absolute_uri(reverse('p-oauth-callback'))
   request.session['oauth_consent_token'] = str(consent_req.token)

   # Obtain the url and save the state in the session. (authorize_redirect()
   # normally takes care of that, here we don't want to immediately redirect
   # but show a page instead.
   rv = client.create_authorization_url(callback_url)
   client.save_authorize_data(request, redirect_uri=callback_url, **rv)

   context = embedded_section_view(request, 'embedded', 'p-consent-start')
   context.update({
       'description': consent_req.service.description,
       'redirect_url': rv['url']
   })
   r = render(request, 'P/consent_start.html', context)
   r['Cache-Control'] = 'no-store, must-revalidate'
   r['Pragma'] = 'no-cache'
   r['Expires'] = '0'
   return r


def oauth_callback(request):
   """
   Manufacturer redirects back here after end user consents.
   Exchange code for token, store against the service record.
   """
   if not (consent_token := request.session.pop('oauth_consent_token', None)):
      return HttpResponseBadRequest('Missing or already expired session state.')

   consent_req = get_object_or_404(ConsentRequest, token = consent_token)
   service = consent_req.service

   client = get_client()
   try:
      token_data = client.authorize_access_token(request)

      token_fields = {
          'access_token': token_data['access_token'],
          'refresh_token': token_data.get('refresh_token', ''),
          'token_type': token_data.get('token_type', 'Bearer'),
          'expires_at': epoch_to_datetime(token_data.get('expires_at')),
          'id_token': token_data.get('id_token', ''),
          'extra_data': token_data.get('userinfo', {}),
          'revoked': False,
      }
      if service.oauth_token_id:
         OAuthToken.objects.filter(pk = service.oauth_token_id).update(**token_fields)
      else:
         token = OAuthToken.objects.create(**token_fields)
         service.oauth_token = token
         service.save(update_fields = ['oauth_token'])

      consent_req.delete()
      context = embedded_section_view(request, 'embedded', 'p-consent-success')
      context.update({
          'service': service,
          'debug_data': token_data['userinfo']
      })

      return render(request, 'P/consent_success.html', context)

   except OAuthError as e:
      context = embedded_section_view(request, 'embedded', 'p-error')
      context['error'] = str(e)
      return render(request, 'P/error.html', context)

# ------------------------------------------------------------------------------
#
#    Employee views (providing the service)                                 {{{1
#
# ------------------------------------------------------------------------------

@permission_required('P.view_service')
def service_page(request, service_id):
   """
   View a single service

   An Employee gets into this view by clicking a Service item in the overview
   page (ServicesOverview).

   If consent has been provided: load the video functionality
   If consent is missing: show warning + send/resend button
   """

   def consent_page(service: Service, msg: str = None):
      consent_req, _ = ConsentRequest.objects.get_or_create(service = service)
      context = embedded_section_view(request, 'embedded', 'p-awaiting-consent')
      context.update({
         'service': service,
         'consent_request': consent_req,
         'message': msg
      })
      r = render(request, 'P/awaiting_consent.html', context)
      r['Cache-Control'] = 'no-store, must-revalidate'
      r['Pragma'] = 'no-cache'
      r['Expires'] = '0'
      return r

   # service = get_object_or_404(Service.objects.select_related('oauth_token'), id = service_id, employee = request.user)
   service = get_object_or_404(Service.objects.select_related('oauth_token'), id = service_id)
   if service.needs_consent:
      return consent_page(service)

   error = None
   try:
      devices = list_devices(service)['data']['organization']['allDevices']['devices']

   except TokenError as e:
      service.oauth_token.revoked = True
      service.oauth_token.save()
      return consent_page(service, msg = _('Consent has expired. Please request new consent.'))
   except Exception as e:
      error = str(e)

   context = embedded_section_view(request, 'embedded', 'p-service-page')
   context.update({
      'error': error,
      'service': service,
      'devices': devices,
      'org_id':
      service.oauth_token.extra_data['axis:organization'].split(':')[2]
   })

   return render(request, 'P/service_page.html', context)

@permission_required('P.view_service')
def service_list_devices(request, service_id):
   """
   List the devices associated with <service_id>
   """
   return JsonResponse({'data': list_devices(service_id)})

@permission_required('P.view_service')
def service_token(request, service_id):
   """
   Get a token, used by clientside logic to initiate webrtc in the browser
   """
   service = get_object_or_404(Service.objects.select_related('oauth_token'), id = service_id)
   authenticator = P_OAuth2Authenticator(service.oauth_token)
   return HttpResponse(content = authenticator.token(), status = 200)

@permission_required('P.view_service')
def send_consent_email(request, service_id):
   """
   Employee clicks 'Send/Resend consent request'.
   """
   service = get_object_or_404(Service.objects.select_related('end_user'), id = service_id)
   consent_req, __ = ConsentRequest.objects.get_or_create(service = service)

   mail_context = {
      'subject': _('Consent needed'),
      'name': service.end_user.email,
      'service': service.description,
      'link': request.build_absolute_uri(reverse('p-oauth-start', kwargs={'consent_token': consent_req.token}))
   }

   Log(LOG_INFO, request, 'Sending e-mail')
   tenant.MAILER.send_system_email('serviceplatform_awaiting_consent', mail_context,
                                   to_ = service.end_user.email, always_bcc = [tenant.ORGANISATION_EMAIL])
   Log(LOG_INFO, request, 'Done sending e-mail')

   consent_req.requested_at = timezone.now()
   consent_req.save()

   context = embedded_section_view(request, 'embedded', 'p-consent-sent')
   context['service'] = service
   context['consent_request'] = consent_req
   return render(request, 'P/consent_sent.html', context)

# ------------------------------------------------------------------------------
#
#    End-user self-management views                                         {{{1
#
# ------------------------------------------------------------------------------

MY_SERVICES_OVERVIEW_TRANSLATIONS = {
   'Properties': _('Properties...'),
   'Delete': _('Delete...'),
   'DeleteService': _('Delete service'),
   'SureToDelete': _('Are you sure you want to delete service <b>{0}</b>?'),
   'DeleteButton': _('Delete'),
   'Processing': _('Processing...'),
   'ServiceDeleted': _('Service has been deleted'),
   'AddService': _('Add service'),
   'ErrorSearching': _('Error during search'),
   'Yes': _('Yes'),
   'No': _('No'),
   'Consent': _('Consent'),
   'Revoke': _('Revoke consent'),
   'SureToRevoke': _('Are you sure you want to revoke consent for service <b>{0}</b>?'),
   'RevokeButton': _('Revoke'),
   'ConsentRevoked': _('Consent has been revoked'),
   'ErrorRevoking': _('Error revoking consent'),
}

class MyServicesOverview(LoginRequiredMixin, TemplateView):
   """
   A page where the enduser can have a look at his services and consent
   status, and revoke consent.
   """

   def get_template_names(self):
      if self.request.user.is_authenticated:
         return ['P/my_services_overview.html']
      else:
         return ['usercontent/signuporlogin.html']

   def get_context_data(self, **kwargs):
      context = embedded_section_view(self.request, 'embedded', 'p_enduser_page')
      if not self.request.user.is_authenticated:
         add_signuporlogin_context(context, self.request.get_full_path())
      else:
         context['form'] = ServiceSearchForm(self.request)
         context['form_id'] = 'search_form'
         context['form_submit'] = _('Search')
         context['form_grid'] = 'pure-u-md-1-3'
         context['form_fieldclass'] = 'pure-u-23-24'
         context['translations'] = MY_SERVICES_OVERVIEW_TRANSLATIONS
      return context

class MyServices_ListJson(LoginRequiredMixin, SearchableListView):
   """
   See Services_ListJson, the AI wasn't clever enough to share code
   TODO: Share code with the other function
   """

   def get_form(self):
      return ServiceSearchForm(self.request, self.request.GET)

   def get_filters_from_form(self, f):
      q = Q()
      description = f.cleaned_data.get('description')
      if description:
         q &= Q(description__icontains=description)
      created_after = f.cleaned_data.get('created_after')
      if created_after:
         q &= Q(created_at__gte=make_timezone_aware(created_after))
      created_before = f.cleaned_data.get('created_before')
      if created_before:
         q &= Q(created_at__lte=make_timezone_aware(created_before))
      return q

   def get_queryset(self):
      emails = get_user_enduser_emails(self.request.user)
      return Service.objects.select_related('employee', 'end_user', 'oauth_token').filter(
         end_user__email__in=emails,
      ).order_by('created_at')

   def serialize(self, query):
      return ServiceSerializer().serialize(query, fields=())


class MyServiceAdd(LoginRequiredMixin, MyAddView):
   form_class = MyServiceForm
   form_name = 'serviceform'
   form_submit = _('Add')

   def post_form_apply(self, obj, form):
      obj.end_user = EndUser.for_user(self.request.user)
      obj.employee = None
      return True

   def return_value(self, obj):
      data = json.loads(ServiceSerializer().serialize([obj], fields=()))
      return JsonResponse({'data': data})


class MyServiceEdit(LoginRequiredMixin, MyEditView):
   form_class = MyServiceForm
   form_name = 'serviceform'
   form_submit = _('Save')

   def get_object(self):
      return get_object_or_404(Service, pk=self.kwargs['service_id'])

   def is_authorized(self, user):
      return self.the_object.end_user.email in get_user_enduser_emails(user)

   def return_value(self, obj):
      data = json.loads(ServiceSerializer().serialize([obj], fields=()))
      return JsonResponse({'data': data})


@login_required
def service_rm(request, service_id):
   """
   Service removal involves revoking the consent and removing the service from
   our administration

   Both enduser and entitled service employees can do this
   """
   if request.method != 'POST':
      return HttpResponseNotAllowed(['POST'])

   service = get_object_or_404(
      Service.objects.select_related('employee', 'end_user', 'oauth_token', 'consent_request'),
      pk = service_id,
   )

   if not service.can_delete(request.user):
      return HttpResponseForbidden(_('You do not have permission to remove this service'))

   result, msg = do_revoke(service, request.user)
   if result:
      try:
         service.delete()
         return HttpResponse(content='', status=204)
      except Exception:
         msg = _('Could not delete service')
   return HttpResponse(content = msg, status = 500)

@login_required
def service_revoke(request, service_id):
   """
   Revoke consent from a Service. This effectively pauses the service because
   no interaction is possible anymore

   Both enduser and entitled service employees can do this
   """
   if request.method != 'POST':
      return HttpResponseNotAllowed(['POST'])

   service = get_object_or_404(
      Service.objects.select_related('employee', 'end_user', 'oauth_token', 'consent_request'),
      pk = service_id,
   )

   if not service.can_revoke(request.user):
      return HttpResponseForbidden(_('You do not have permission to revoke consent'))

   result, msg = do_revoke(service, request.user)
   if result:
      return HttpResponse(ServiceSerializer().serialize([service], fields=()), content_type='application/json')
   else:
      return HttpResponse(content = msg, status = 500)

# vim: set nowrap sw=3 sts=3 et fdm=marker:
