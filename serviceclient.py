"""
serviceclient.py
================
Various operations on the Axis Cloud Connect portal
"""

import json

import requests

from utilities.core.authenticator import Authenticator
from utilities.core.logger import Logger

DEFAULT_TIMEOUT = 30.0

# -------------------------------------------------------------------------------
#
#  GraphQL queries                                                           {{{1
#
# -------------------------------------------------------------------------------

GET_VERSION = """
query version {
  version {
 version
  }
}
"""

LIST_ORGANIZATIONS = """
query organizations {
   organizations {
     organizations {
        arn
        name
        description
        createdAt
     }
   }
}
"""

ORGANIZATION_DETAILS = """
query organization_details($organisationArn: Arn!) {
   organization(organizationArn: $organisationArn) {
     arn
     name
     description
     allDevices {
        devices {
          arn
          serial
        }
     }
     children {
        children {
           arn
        }
     }
   }
}
"""

CREATE_RESOURCE_GROUP = """
mutation createResourceGroup($parentArn: Arn!, $name: String!, $description: String!) {
   createResourceGroup(input: {
       parentArn: $parentArn
       name: $name
       description: $description
   }) {
       resourceGroupArn
   }
}
"""

REGISTER_AXIS_DEVICE = """
mutation registerAxisDevice($oak: String!, $serial: String!, $resourceGroupArn: Arn!) {
    registerAxisDevice(input: {
        oak: $oak
        serial: $serial
        resourceGroupArn: $resourceGroupArn
    }) {
        deviceArn
    }
}
"""

REMOVE_AXIS_DEVICE = """
mutation removeAxisDevice($deviceArn: Arn!) {
    removeAxisDevice(input: {
        deviceArn: $deviceArn
    }) {
        deviceArn
    }
}
"""

LIST_RESOURCEGROUPS = """
query getResourceGroups($arns: [Arn!]!) {
  resourceGroups(arns: $arns) {
    arn
    name
    description
  }
}
"""

LIST_DEVICES = """
query listDevices($resourceGroupArns: [Arn!]!) {
  resourceGroups(arns: $resourceGroupArns) {
    arn
    devices {
      devices {
        ...on AxisCamera {
          arn
          serial
          createdAt
          onboarding {
            state
            error
          }
        }
      }
    }
  }
}
"""

LIST_DEVICES2 = """
query devices {
    devices {
      devices {
        ...on AxisCamera {
          arn
          serial
          createdAt
          onboarding {
            state
            error
          }
        }
      }
  }
}
"""

# From acc-integration-reference-tool

LIST_DEVICES3 = """
query getAllDevices($arn: Arn!, $skip: Int, $take: Int) {
   organization(organizationArn: $arn) {
       allDevices(page: {skip: $skip, take: $take}) {
           devices {
               ... on AxisCamera {
                   arn
                   serial
                   model {
                       name
                   }
                   firmware {
                       information {
                           id
                           track
                           version
                       }
                   }
               }
           }
       }
   }
}
"""

GET_DEVICE_FIRMWARE = """
query device($deviceArn: [Arn!]!) {
  devices(deviceArn: $deviceArn) {
    arn
    firmware {
      information {
        version
      }
    }
  }
}
"""

CREATE_EVENT_SUBSCRIPTION = """
mutation createWebhookEventSubscription($arn: Arn!, $url: Url!, $signing_key: EventSigningKey!) {
  createWebhookEventSubscription(input: {
    eventTypes: ["com.axis.*"]
    resourceArn: $arn
    url: $url
    signingKey: $signing_key
  }) {
    subscription {
      subscriptionArn
      eventTypes
      resourceArn
      url
    }
  }
}
"""

DELETE_EVENT_SUBSCRIPTION = """
mutation deleteEventSubscription($arn: Arn!) {
  deleteEventSubscription(input: {
    arn: $arn
  }) {
    arn
  }
}
"""

LIST_WEBHOOKS = """
query listOrgWebhooks($organizationArn: Arn!) {
  organization(organizationArn: $organizationArn) {
    eventSubscriptions {
       webhooks {
          subscriptionArn
          resourceArn
          eventTypes
          url
       }
    }
  }
}
"""

SET_IDD = """
mutation set_idd($organizationArn: Arn!, $enable: Boolean!) {
  updateSettings(input: {
    organization: $organizationArn
    idd: {enabled: $enable}
  }) {
    idd {
      enabled
    }
  }
}
"""

LIST_ORG_ACCESSES = """
query listOrgAccesses($organizationArn: Arn!) {
  organization(organizationArn: $organizationArn) {
    access {
      access {
        arn
        name
        description
        assignedPrincipals {
           arn
        }
      }
    }
  }
}
"""

INTROSPECT = """
query Introspect {
  __schema {
    types {
      name
      kind
      fields {
        name
        args {
          name
          type {
            name
            kind
          }
        }
        type {
          name
          kind
        }
      }
    }
  }
}
"""

# csr             - String! The CSR encoded in Base64 format.
# organizationArn - Arn! 	ARN of the organization to create the Service Principal in.
# isOwner         - Boolean Indicates if the created Service Principal will be an owner of the Organization it belongs to.

CREATE_SERVICE_PRINCIPAL = """
mutation createServicePrincipal($csr: String!, $organizationArn: Arn!, $isOwner: Boolean!) {
   createServicePrincipal(input: {
       csr: $csr
       organizationArn: $organizationArn
       isOwner: $isOwner
   }) {
         servicePrincipalArn
         servicePrincipalCert
   }
}
"""

SET_PRINCIPAL_PROPERTIES = """
mutation setPrincipalProperties($principalArn: Arn!, $isOwner: Boolean!, $isPrincipalAdmin: Boolean!, $isAccessAdmin: Boolean!) {
  setPrincipalProperties(input: {
    principalArn: $principalArn
    properties: {
      isOwner: $isOwner
      isPrincipalAdmin: $isPrincipalAdmin
      isAccessAdmin: $isAccessAdmin
    }
  }) {
    principalArn
    properties {
      isOwner
      isPrincipalAdmin
      isAccessAdmin
    }
  }
}
"""

CREATE_DEVICE_MANAGEMENT_ACCESS = """
mutation createAccess($organizationArn: Arn!, $principalArn: Arn!, $description: String!) {
  createAccess(input: {
     principalArns: [ $principalArn ]
     targetArn: $organizationArn
     role: DEVICE_MANAGEMENT,
     description: $description
  }) {
     accessArn
  }
}
"""

CREATE_DEVICE_ONBOARDING_ACCESS = """
mutation createAccess($organizationArn: Arn!, $principalArn: Arn!, $description: String!) {
  createAccess(input: {
     principalArns: [ $principalArn ]
     targetArn: $organizationArn
     role: DEVICE_ONBOARDING,
     description: $description
  }) {
     accessArn
  }
}
"""

CREATE_STREAM_VIDEO_ACCESS = """
mutation createAccess($organizationArn: Arn!, $principalArn: Arn!, $description: String!) {
  createAccess(input: {
     principalArns: [ $principalArn ]
     targetArn: $organizationArn
     role: STREAM_VIDEO,
     description: $description
  }) {
     accessArn
  }
}
"""

CREATE_EVENT_SUBSCRIPTION_MANAGEMENT_ACCESS = """
mutation createAccess($organizationArn: Arn!, $principalArn: Arn!, $description: String!) {
  createAccess(input: {
     principalArns: [ $principalArn ]
     targetArn: $organizationArn
     role: EVENT_SUBSCRIPTION_MANAGEMENT,
     description: $description
  }) {
     accessArn
  }
}
"""

# -------------------------------------------------------------------------------
#
#  Exceptions                                                                {{{1
#
# -------------------------------------------------------------------------------

class ServiceClientError(Exception):
   pass

class DirectoryNotFound(ServiceClientError):
   """
   A path, local to this server, wasn't found
   """

class ServerError(ServiceClientError):
   """
   Something unspecified happened
   """

class ServerErrorTimeout(ServerError):
   """
   ACX Server not responding in time
   """

class ServerErrorResponse(ServerError):
   """
   ACX Server returned an error message
   """

   def __init__(self, status_code, response):
      super().__init__(response)
      self.status_code = status_code
      self.response = response

   def __repr__(self):
      return f'({self.status_code}) {self.response}'

class ServerErrorJsonResponse(ServerError):
   """
   Like above, JSON type of data
   """

   def __init__(self, status_code, json_data):
      super().__init__()
      self.status_code = status_code
      self.json = json_data

   def __repr__(self):
      return f'({self.status_code}) {json.dumps(self.json)}'

# -------------------------------------------------------------------------------
#
#  Partner Service Principal cert                                            {{{1
#
# -------------------------------------------------------------------------------


# -------------------------------------------------------------------------------
#
#  ServiceClients                                                            {{{1
#
# -------------------------------------------------------------------------------

def organization_arn_to_id(arn: str) -> str:
   """
   arn: 'arn:organization:<organisation_id>'
   """
   return arn.split(':')[2]

class ServiceClient:

   def __init__(self, authenticator: Authenticator, logger: Logger):
      self.authenticator = authenticator
      self.logger = logger
      self.headers = {
         'Content-Type': 'application/json'
      }

# -------------------------------------------------------------------------------
#  OrganizationClient                                                        {{{2
# -------------------------------------------------------------------------------

class OrganizationClient(ServiceClient):

   def __init__(self, authenticator: Authenticator, api_key: str, org_arn: str, org_label: str, logger: Logger):
      super().__init__(authenticator, logger)
      self.org_arn = org_arn
      self.org_label = org_label
      self.api_key = api_key

   def run_query(self, query: str) -> dict:
      """
      Run a GraphQL query
      """
      self.headers['Authorization'] = f'Bearer {self.authenticator.token()}'

      try:
         r = requests.post(
            f'https://eu.cs.connect.axis.com/graphql?acx-client-key={self.api_key}',
            timeout = DEFAULT_TIMEOUT,
            data = json.dumps(query),
            headers = self.headers
         )
         r.raise_for_status()
         j = r.json()
      except requests.Timeout as e:
         raise ServerErrorTimeout('GraphQL timeout') from e
      except requests.HTTPError as e:
         raise ServerErrorResponse(r.status_code, r.text) from e
      return j

   def get_vapix_client(self):
      return VapixClient(organization_arn_to_id(self.org_arn), self.authenticator, self.logger)

   def get_service_version(self):
      j = self.run_query({'query': GET_VERSION})
      return j['data']['version']['version']

   def create_resource_group(self, name, description):
      """
      Create a resource group
      """
      # with open(os.path.join(self.cert_base, 'arn.txt'), 'r') as f:
      #   arn = f.read().strip()

      query = {
         'query': CREATE_RESOURCE_GROUP,
         'variables': {
            'name': name,
            'description': description,
            'parentArn': self.org_arn
         }
      }
      return self.run_query(query), json.dumps(query)

   def register_axis_device(self, oak, serial, resource_group_arn):
      """
      """
      query = {
         'query': REGISTER_AXIS_DEVICE,
         'variables': {
            'oak': oak,
            'serial': serial,
            'resourceGroupArn': resource_group_arn
         }
      }
      j = self.run_query(query)

      if (errors := j.get('errors', None)) is not None:
         return False, errors[0]['message']
      else:
         return True, j['data']['registerAxisDevice']['deviceArn']

   def remove_axis_device(self, device_arn):
      """
      Remove an Axis device
      """
      query = {
         'query': REMOVE_AXIS_DEVICE,
         'variables': {
            'deviceArn': device_arn
         }
      }
      return self.run_query(query), json.dumps(query)

   def list_devices(self, organisation_arn):
      """
      """
      query = {
         'query': LIST_DEVICES3,
         'variables': {
            'arn': organisation_arn
         }
      }
      return self.run_query(query)

   def list_devices2(self):
      """
      """
      query = {
         'query': LIST_DEVICES2
      }
      return self.run_query(query)

   def list_resourcegroups(self, organization_arn):
      query = {
         'query': LIST_RESOURCEGROUPS,
         'variables': {
            'arns': [organization_arn]
         }
      }
      return self.run_query(query)

   def list_organizations(self):
      return self.run_query({'query': LIST_ORGANIZATIONS})

   def organization_details(self, organization_arn):
      query = {
         'query': ORGANIZATION_DETAILS,
         'variables': {
            'organisationArn': organization_arn
         }
      }
      return self.run_query(query)

   def get_device_firmware(self, device_arn):
      """
      """
      query = {
         'query': GET_DEVICE_FIRMWARE,
         'variables': {
            'deviceArn': device_arn
         }
      }
      return self.run_query(query)

   def create_event_subscription(self, arn, url, signing_key = None):
      """
      """
      query = {
         'query': CREATE_EVENT_SUBSCRIPTION,
         'variables': {
            'arn': arn,
            'url': url,
            'signing_key': signing_key
         }
      }
      # Temporary code
      return self.run_query(query), json.dumps(query)

   def remove_event_subscription(self, arn):
      """
      """
      query = {
         'query': DELETE_EVENT_SUBSCRIPTION,
         'variables': {
            'arn': arn,
         }
      }
      # Temporary code
      return self.run_query(query), json.dumps(query)

   def list_webhooks(self):
      """
      List all the webhooks for this organization
      """
      query = {
         'query': LIST_WEBHOOKS,
         'variables': {
            'organizationArn': self.org_arn
         }
      }
      return self.run_query(query)

   def set_idd(self, enable = True):
      """
      Enable or disable IDD (Internal Device Diagnostics) on this organization
      """
      query = {
         'query': SET_IDD,
         'variables': {
            'organizationArn': self.org_arn,
            'enable': enable
         }
      }
      return self.run_query(query)

   def list_accesses(self):
      """
      List all Accesses in an organisation
      """
      query = {
         'query': LIST_ORG_ACCESSES,
         'variables': {
            'organizationArn': self.org_arn,
         }
      }
      return self.run_query(query)

   def introspect(self):
      """
      Introspect the GraphQL interface
      """
      query = {
         'query': INTROSPECT,
      }
      return self.run_query(query)

   def create_service_principal(self, csr_data):
      """
      Create a new service principal for the current organisation
      For this to work, create the OrganizationClient with principal_mode =
      True
      """
      query = {
         'query': CREATE_SERVICE_PRINCIPAL,
         'variables': {
            'csr': csr_data,
            'organizationArn': self.org_arn,
            'isOwner': True
         }
      }
      return self.run_query(query)

   def set_principal_properties(self, owner: bool, principal_admin: bool, access_admin: bool) -> dict:
      """
      Set principal properties. Need to execute this with the Partner Service
      Principal cert for authentication?
      """
      query = {
         'query': SET_PRINCIPAL_PROPERTIES,
         'variables': {
            'principalArn': self.authenticator.get_principal_arn(),
            'isOwner': owner,
            'isPrincipalAdmin': principal_admin,
            'isAccessAdmin': access_admin
         }
      }
      return self.run_query(query)

   def _set_access(self, graphql: str, description: str):
      """
      Base function for setting the accesses
      """
      query = {
         'query': graphql,
         'variables': {
            'principalArn': self.authenticator.get_principal_arn(),
            'organizationArn': self.org_arn,
            'description': description
         }
      }
      return self.run_query(query)

   def set_device_management_access(self):
      return self._set_access(CREATE_DEVICE_MANAGEMENT_ACCESS, f'Device management on {self.org_label}')

   def set_device_onboarding_access(self):
      return self._set_access(CREATE_DEVICE_ONBOARDING_ACCESS, f'Device onboarding on {self.org_label}')

   def set_video_streaming_access(self):
      return self._set_access(CREATE_STREAM_VIDEO_ACCESS, f'Video streaming {self.org_label}')

   def set_event_subscription_management_access(self):
      return self._set_access(CREATE_EVENT_SUBSCRIPTION_MANAGEMENT_ACCESS, f'Event subscription management on {self.org_label}')

# -------------------------------------------------------------------------------
#  VapixClient                                                               {{{2
# -------------------------------------------------------------------------------

class VapixClient(ServiceClient):

   def __init__(self, org_id, authenticator, logger):
      super().__init__(authenticator, logger)
      self.org_id = org_id

   def _response(self, r: requests.Response):
      if r.headers['Content-Type'] == 'application/json':
         j = r.json()
         if r.status_code >= 300:
            raise ServerErrorResponse(r.status_code, j['message'])
         return j
      else:
         if r.status_code >= 300:
            raise ServerErrorResponse(r.status_code, r.text)
      return r.content

   def get(self, device_id, vapix_call):
      """
      Run a VAPIX get
      """
      self.headers['Authorization'] = f'Bearer {self.authenticator.token()}'
      url = f'https://api.edgelink.connect.axis.com/organizations/{self.org_id}/targets/{device_id}/vapix{vapix_call}'
      try:
         return self._response(requests.get(url, timeout = DEFAULT_TIMEOUT, headers = self.headers))
      except requests.Timeout as e:
         raise ServerErrorTimeout('Edgelink timeout') from e

   def post(self, device_id, vapix_call, data):
      """
      Run a VAPIX POST
      """
      self.headers['Authorization'] = f'Bearer {self.authenticator.token()}'
      url = f'https://api.edgelink.connect.axis.com/organizations/{self.org_id}/targets/{device_id}/vapix{vapix_call}'
      try:
         return self._response(requests.post(url, timeout = DEFAULT_TIMEOUT, data = data, headers = self.headers))
      except requests.Timeout as e:
         raise ServerErrorTimeout('Edgelink timeout') from e

# vim: set nowrap sw=3 sts=3 et fdm=marker:
