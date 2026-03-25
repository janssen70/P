"""
Management command to initialize the P module for a tenant
"""
import os

from django.utils.translation import gettext_lazy as _

from tenants.settings import tenant
from tenants.command import TenantCommand

from usercontent.utils import create_initial_sections


class Command(TenantCommand):
   """
   This command checks that all required setup for the P module is in place.
   It takes care of:

   - presence of a number of usercontent pages.

   When making changes, take care it can be run on an existing installation
   without destructing data.
   """
   help = 'Initialize P module for current tenant'

   def tenant_handle(self, *args, **options):
      """
      """
      if (num_created := create_initial_sections('embedded',
                                                 ['p_landing_page', 'p_enduser_page', 'p-awaiting-consent', 'p-consent-sent', 'p-consent-success', 'p-consent-start'],
                                                 _('P Service platform default text'))
          ):
         self.stdout.write(f'Created {num_created} embedded webpages')

      self.stdout.write('P module initialization complete')

# vim: set nowrap sw=3 sts=3 et fdm=marker:
