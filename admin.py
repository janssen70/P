from django.contrib import admin
from django.shortcuts import render
from django.contrib import messages

from allauth.socialaccount.models import SocialApp, SocialAccount, SocialToken

from .models import EndUser, Service, OAuthToken, ConsentRequest


def populate_oauth_token_from_allauth(modeladmin, request, queryset):
   """
   Admin action: populate OAuthToken for selected Services from an existing
   allauth SocialAccount/SocialToken. Useful when the OAuth callback URL is
   not yet registered at the Authentication Server (AS) but allauth login
   against the same AS works.

   Shows an intermediate page to pick the SocialApp (provider) first.
   """
   if 'social_app_id' not in request.POST:
      # Step 1: show the intermediate page to pick a SocialApp
      social_apps = SocialApp.objects.all()
      return render(request, 'P/admin_pick_socialapp.html', {
          'social_apps': social_apps,
          'queryset': queryset,
          'action': 'populate_oauth_token_from_allauth',
          'opts': modeladmin.model._meta,
      })

   # Step 2: process with the chosen SocialApp
   social_app = SocialApp.objects.get(pk=request.POST['social_app_id'])
   provider = social_app.provider_id

   ok = []
   skipped = []

   for service in queryset:
      email = service.end_user.email

      if not (accounts := SocialAccount.objects.filter(provider = provider, extra_data__email = email)):
         if not (accounts := SocialAccount.objects.filter(provider = provider, user__email = email)):
            skipped.append(f'{email}: no SocialAccount found for provider {provider}')
            continue

      if accounts.count() > 1:
         skipped.append(f'{email} (multiple SocialAccounts, ambiguous)')
         continue

      account = accounts.get()

      try:
         social_token = SocialToken.objects.get(account=account)
      except SocialToken.DoesNotExist:
         skipped.append(f"{email} (no SocialToken found)")
         continue

      token_fields = {
          'access_token': social_token.token,
          'refresh_token': social_token.token_secret or '',
          'token_type': 'Bearer',
          'expires_at': social_token.expires_at,
          'id_token': '',
          'extra_data': account.extra_data or {},
          'revoked': False,
      }

      if service.oauth_token_id:
         OAuthToken.objects.filter(pk=service.oauth_token_id).update(**token_fields)
      else:
         token = OAuthToken.objects.create(**token_fields)
         service.oauth_token = token
         service.save(update_fields=['oauth_token'])

      ok.append(email)

   if ok:
      messages.success(request, f"Populated token for: {', '.join(ok)}")
   if skipped:
      messages.warning(request, f"Skipped: {'; '.join(skipped)}")


populate_oauth_token_from_allauth.short_description = "Populate OAuth token from allauth"


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
   list_display = ('id', 'employee', 'end_user', 'needs_consent', 'created_at')
   list_select_related = ('employee', 'end_user', 'oauth_token')
   actions = [populate_oauth_token_from_allauth]


@admin.register(EndUser)
class EndUserAdmin(admin.ModelAdmin):
   list_display = ('email', 'portal_account')


@admin.register(OAuthToken)
class OAuthTokenAdmin(admin.ModelAdmin):
   list_display = ('id', 'token_type', 'expires_at', 'revoked', 'updated_at')
   readonly_fields = ('updated_at',)


@admin.register(ConsentRequest)
class ConsentRequestAdmin(admin.ModelAdmin):
   list_display = ('service', 'requested_at', 'token')

# vim: set nowrap sw=3 sts=3 et fdm=marker:
