"""
Forms for the P Platform
"""
from django import forms
from django.forms import ModelForm
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _, get_language_from_request
from django.utils import formats

from utilities.web.helpers import jquery_datepicker_format
from .models import Service, EndUser

User = get_user_model()

# -------------------------------------------------------------------------------
#
#   Search form                                                             {{{1
#
# -------------------------------------------------------------------------------

class ServiceSearchForm(forms.Form):
   """
   Standalone form to filter services on description content and date range.
   Constructor accepts (request, data=None) so it works with
   SearchableListView.get_form().
   """
   description = forms.CharField(
      required = False,
      label = _('Description'),
      help_text = _('Filter by description content'),
   )
   created_after = forms.DateField(
      required = False,
      label = _('Created after'),
   )
   created_before = forms.DateField(
      required = False,
      label = _('Created before'),
   )

   def __init__(self, request, data = None, **kwargs):
      super().__init__(data, **kwargs)
      date_formats = formats.get_format('DATE_INPUT_FORMATS', lang = get_language_from_request(request))
      for field_name in ('created_after', 'created_before'):
         self.fields[field_name].widget.format = date_formats[0]
         self.fields[field_name].input_formats = date_formats
         self.fields[field_name].widget.attrs['class'] = 'datepicker'
         self.fields[field_name].widget.attrs['data-dateformat'] = jquery_datepicker_format(date_formats[0])

# -------------------------------------------------------------------------------
#
#   Model forms                                                             {{{1
#
# -------------------------------------------------------------------------------

class ServiceForm(ModelForm):
   """
   Form for adding and editing Service instances.
   Employee defaults to the current user but may be left blank.
   """
   class Meta:
      model = Service
      fields = ['employee', 'end_user', 'description']
      widgets = {
         'description': forms.Textarea(attrs={'rows': 3})
      }

   def __init__(self, *args, **kwargs):
      super().__init__(*args, **kwargs)
      self.fields['employee'].required = False
      self.fields['employee'].queryset = User.objects.all().order_by('last_name', 'first_name')
      self.fields['end_user'].queryset = EndUser.objects.all().order_by('email')


class MyServiceForm(ModelForm):
   """
   Restricted form for end-users managing their own services.
   Only exposes description; end_user and employee are set by the view.
   """
   class Meta:
      model = Service
      fields = ['description']
      widgets = {
         'description': forms.Textarea(attrs={'rows': 3})
      }


class EndUserForm(ModelForm):
   """
   Form for adding an EndUser.
   portal_account is not set here and stays null.
   """
   class Meta:
      model = EndUser
      fields = ['email']

# vim: set nowrap sw=3 sts=3 et fdm=marker:
