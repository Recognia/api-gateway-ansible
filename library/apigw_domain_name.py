#!/usr/bin/python

# API Gateway Ansible Modules
#
# Modules in this project allow management of the AWS API Gateway service.
#
# Authors:
#  - Brian Felton <github: bjfelton>
#  - Malcolm Studd <github: mestudd>
#
# apigw_domain_name
#    Manage creation, update, and removal of API Gateway DomainName resources
#

# MIT License
#
# Copyright (c) 2016 Brian Felton, Emerson
# Copyright (c) 2018 Malcolm studd
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


DOCUMENTATION='''
---
module: apigw_domain_name
author: Brian Felton (@bjfelton)
short_description: Add, update, or remove DomainName resources
description:
- Uses domain name for identifying resources for CRUD operations
- Update only covers certificate name
version_added: "2.2"
options:
  name:
    description:
    - The name of the DomainName resource on which to operate
    type: string
    required: True
    aliases: domain_name
  cert_arn:
    description:
    - ARN of the associated certificate. Either C(cert_arn) or C(cert_name) is required when C(state) is 'present'.
  cert_name:
    description:
    - Name of the associated certificate. Either C(cert_arn) or C(cert_name) is required when C(state) is 'present'.
    type: string
    required: False
    default: None
  state:
    description:
    - Should domain_name exist or not
    choices: ['present', 'absent']
    default: 'present'
    required: False
requirements:
    - python = 2.7
    - boto
    - boto3
notes:
    - This module requires that you have boto and boto3 installed and that your credentials are created or stored in a way that is compatible (see U(https://boto3.readthedocs.io/en/latest/guide/quickstart.html#configuration)).
extends_documentation_fragment:
    - aws
    - ec2
'''

EXAMPLES = '''
---
- hosts: localhost
  gather_facts: False
  tasks:
  - name: Create domain name with ACM certificate
    apigw_domain_name:
      name: testdomain.io.edu.mil
      cert_arn: 'arn:aws:acm:us-east-1:1234:certificate/abcd'
      state: "{{ state | default('present') }}"
    register: dn

  - debug: var=dn
'''

RETURN = '''
---
domain_name:
  description: dictionary representing the domain name
  returned: success
  type: dict
changed:
  description: standard boolean indicating if something changed
  returned: always
  type: boolean
'''

__version__ = '${version}'


try:
    import botocore
except ImportError:
    # HAS_BOTOCORE taken care of in AnsibleAWSModule
    pass

from ansible.module_utils.aws.core import AnsibleAWSModule
from ansible.module_utils.ec2 import (AWSRetry, camel_dict_to_snake_dict)

def main():
    argument_spec = dict(
        name=dict(required=True, aliases=['domain_name']),
        cert_arn=dict(required=False),
        cert_name=dict(required=False),
        state=dict(default='present', choices=['present', 'absent']),
    )

    mutually_exclusive = [['cert_arn', 'cert_name']]

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        supports_check_mode=False,
        mutually_exclusive=mutually_exclusive,
    )

    client = module.client('apigateway')

    state = module.params.get('state')

    changed = True

    try:
      if state == "present":
        result = ensure_domain_name_present(module, client)
      elif state == 'absent':
        result = ensure_domain_name_absent(module, client)
    except botocore.exceptions.ClientError as e:
      module.fail_json_aws(e)

    module.exit_json(**result)


@AWSRetry.exponential_backoff()
def backoff_create_domain_name(client, name, cert_arn, cert_name):
  if cert_arn is None:
    return client.create_domain_name(
      domainName=name,
      certificateName=cert_name
    )
  else:
    return client.create_domain_name(
      domainName=name,
      certificateArn=cert_arn
    )

@AWSRetry.exponential_backoff()
def backoff_delete_domain_name(client, name):
  return client.delete_domain_name(domainName=name)


@AWSRetry.exponential_backoff()
def backoff_get_domain_name(client, name):
  return client.get_domain_name(domainName=name)


@AWSRetry.exponential_backoff()
def backoff_update_domain_name(client, name, patches):
  return client.update_domain_name(
    domainName=name,
    patchOperations=patches
  )


def ensure_domain_name_absent(module, client):
  name = module.params.get('name')

  domain = retrieve_domain_name(module, client, name)
  if domain is None:
    return {'changed': False}

  try:
    if not module.check_mode:
      backoff_delete_domain_name(client, name)
    return {'changed': True}
  except (botocore.exceptions.ClientError, botocore.exceptions.BotoCoreError) as e:
    module.fail_json_aws(e, msg="Couldn't delete domain name")

def ensure_domain_name_present(module, client):
  name = module.params.get('name')
  cert_arn = module.params.get('cert_arn')
  cert_name = module.params.get('cert_name')

  domain = retrieve_domain_name(module, client, name)
  changed = False

  if cert_arn is None and cert_name is None:
    module.fail_json(msg="Certificate ARN or name is required to create a domain name")
    return {'changed': False}

  if domain is None:
    if not module.check_mode:
      domain = backoff_create_domain_name(client, name, cert_arn, cert_name)
    changed = True
    # Domain will be None when check_mode is true
    if domain is None:
      return {
        'changed': changed,
        'domain_name': {}
      }

  try:
    patches = []
    if cert_arn not in ['', None] and cert_arn != domain['certificateArn']:
      patches.append({'op': 'replace', 'path': '/certificateArn', 'value': cert_arn})
    if cert_name not in ['', None] and cert_name != self.me['certificateName']:
      patches.append({'op': 'replace', 'path': '/certificateName', 'value': cert_name})

    if patches:
      changed = True

      if not self.module.check_mode:
        backoff_update_domain_name(client, name, patches)
        domain_name = retrieve_domain_name(module, client, name)
  except BotoCoreError as e:
    self.module.fail_json(msg="Error when updating domain_name via boto3: {}".format(e))

  return {
    'changed': changed,
    'domain_name': domain
  }


def retrieve_domain_name(module, client, name):
  """
  Retrieve domain name by provided name
  :return: Result matching the provided domain name or an empty hash
  """
  resp = None
  try:
    resp = backoff_get_domain_name(client, name)

  except botocore.exceptions.ClientError as e:
    if 'NotFoundException' in e.message:
      resp = None
    else:
      module.fail_json(msg="Error when getting domain_name from boto3: {}".format(e))
  except BotoCoreError as e:
    module.fail_json(msg="Error when getting domain_name from boto3: {}".format(e))

  return resp


if __name__ == '__main__':
    main()
