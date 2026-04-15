"""
Urls for the P Platform
"""
from django.urls import path

from . import views


urlpatterns = [
   path('', views.LandingPage.as_view(), name='p-services-overview'),

   # -------------------------------------------------------------------------------
   # Service Provider views
   # -------------------------------------------------------------------------------

   path('services/', views.ServicesOverview.as_view(), name='p-services-manage'),
   path('services/list/', views.Services_ListJson.as_view(), name='p-services-list-json'),
   path('service/add/', views.ServiceAdd.as_view(), name='p-service-add'),
   path('service/<uuid:service_id>/edit/', views.ServiceEdit.as_view(), name='p-service-edit'),
   path('service/<uuid:service_id>/rm/', views.service_rm, name='p-service-rm'),
   path('enduser/add/', views.EndUserAdd.as_view(), name='p-enduser-add'),
   path('service/<uuid:service_id>/', views.service_page, name='p-service-view'),
   path('service/<uuid:service_id>/devices/', views.service_list_devices, name='p-service-devices-list-json'),
   path('service/<uuid:service_id>/token/list/', views.service_token, name='p-service-token'),
   path('service/<uuid:service_id>/send-consent/', views.send_consent_email, name='p-send-consent-email'),

   # -------------------------------------------------------------------------------
   # Device access within a service
   # -------------------------------------------------------------------------------

   path('device/<uuid:service_id>/<str:device_id>/recordings/list/', views.edge_recording_list, name='p-edgerecording-list-json'),
   path('device/<uuid:service_id>/<str:device_id>/recording/<str:disk_id>/<str:rec_id>/get/',
                                                                     views.edge_recording_get, name='p-edgerecording-get'),

   # -------------------------------------------------------------------------------
   # Combined (both Service Provider and Enduser) views
   # -------------------------------------------------------------------------------

   path('service/<uuid:service_id>/rm/', views.service_rm, name='p-service-rm'),
   path('service/<uuid:service_id>/revoke/', views.service_revoke, name='p-service-revoke'),

   # -------------------------------------------------------------------------------
   # Enduser views
   # -------------------------------------------------------------------------------

   path('my-services/', views.MyServicesOverview.as_view(), name='p-my-services-overview'),
   path('my-services/list/', views.MyServices_ListJson.as_view(), name='p-my-services-list-json'),
   path('my-service/add/', views.MyServiceAdd.as_view(), name='p-my-service-add'),
   path('my-service/<uuid:service_id>/edit/', views.MyServiceEdit.as_view(), name='p-my-service-edit'),

   # -------------------------------------------------------------------------------
   # Authorization related
   # -------------------------------------------------------------------------------

   path('consent/<uuid:consent_token>/', views.oauth_start, name='p-oauth-start'),
   path('oauth/callback/', views.oauth_callback, name='p-oauth-callback'),
]

# vim: set nowrap sw=3 sts=3 et fdm=marker:
