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
- Update cannot change name
- Update of tags requires the certificate arn returned to match arn:aws:something:<region>: in order to
  determine region to build ARN for tag_resource api.
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
  security_policy:
    description:
    - The Transport Layer Security (TLS) version + cipher suite
    choices: ['TLS_1_0', 'TLS_1_2']
    required: False
    default: None
  state:
    description:
    - Should domain_name exist or not
    choices: ['present', 'absent']
    default: 'present'
    required: False
  tags:
    description:
      - A hash/dictionary of tags to add to the new domain name or to add/remove from an existing one.
    type: dict
  purge_tags:
    description:
      - Delete any tags not specified in the task that are on the domain name.
        This means you have to specify all the desired tags on each task affecting a domain name.
    default: false
    type: bool
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
from ansible.module_utils.ec2 import (AWSRetry, camel_dict_to_snake_dict,
        compare_aws_tags, get_aws_connection_info)

import re

def main():
    argument_spec = dict(
        name=dict(required=True, aliases=['domain_name']),
        cert_arn=dict(required=False),
        cert_name=dict(required=False),
        security_policy=dict(required=False),
        state=dict(default='present', choices=['present', 'absent']),
        tags=dict(type='dict'),
        purge_tags=dict(type='bool', default=False),
    )

    mutually_exclusive = [['cert_arn', 'cert_name']]

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        mutually_exclusive=mutually_exclusive,
    )

    client = module.client('apigateway')

    state = module.params.get('state')

    try:
      if state == "present":
        result = ensure_domain_name_present(module, client)
      elif state == 'absent':
        result = ensure_domain_name_absent(module, client)
    except botocore.exceptions.ClientError as e:
      module.fail_json_aws(e)

    module.exit_json(**result)


@AWSRetry.exponential_backoff(delay=15, max_delay=120)
def backoff_create_domain_name(client, args):
  return client.create_domain_name(**args)

@AWSRetry.exponential_backoff()
def backoff_delete_domain_name(client, name):
  return client.delete_domain_name(domainName=name)

@AWSRetry.exponential_backoff()
def backoff_get_domain_name(client, name):
  return client.get_domain_name(domainName=name)

@AWSRetry.exponential_backoff()
def backoff_tag_resource(client, arn, tags):
  return client.tag_resource(resourceArn=arn, tags=tags)

def backoff_untag_resource(client, arn, tagKeys):
  return client.untag_resource(resourceArn=arn, tagKeys=tagKeys)

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
    return {
        'changed': True,
        'domain_name': camel_dict_to_snake_dict(domain)
    }
  except (botocore.exceptions.ClientError, botocore.exceptions.BotoCoreError) as e:
    module.fail_json_aws(e, msg="Couldn't delete domain name")

def ensure_domain_name_present(module, client):
  name = module.params.get('name')
  cert_arn = module.params.get('cert_arn')
  cert_name = module.params.get('cert_name')
  security_policy = module.params.get('security_policy')
  tags = module.params.get('tags')
  purge_tags = module.params.get('purge_tags')

  domain = retrieve_domain_name(module, client, name)
  changed = False

  if cert_arn is None and cert_name is None:
    module.fail_json(msg="Certificate ARN or name is required to create a domain name")
    return {'changed': False}

  if domain is None:
    args = dict(
      domainName=name
    )
    if cert_arn is None:
      args['certificateName'] = cert_name
    else:
      args['certificateArn'] = cert_arn
    if security_policy not in ['', None]:
      args['securityPolicy'] = security_policy
    if tags != None:
      args['tags'] = tags

    if not module.check_mode:
      domain = backoff_create_domain_name(client, args)
    changed = True
    # Domain will be None when check_mode is true
    if domain is None:
      return {
        'changed': changed,
        'domain_name': {}
      }

  if domain and tags is not None:
    region, ec2_url, aws_connect_kwargs = get_aws_connection_info(module, boto3=True)
    arn = 'arn:aws:apigateway:{0}::/domainnames/{1}'.format(region, name)
    old_tags = domain.get('tags') or {}
    to_tag, to_untag = compare_aws_tags(old_tags, tags, purge_tags=purge_tags)
    if to_tag:
      changed |= True
      if not module.check_mode:
        backoff_tag_resource(client, arn, to_tag)
    if to_untag:
      changed |= True
      if not module.check_mode:
        backoff_untag_resource(client, arn, to_untag)

    # need to get new tags
    if changed:
      domain = retrieve_domain_name(module, client, name)

  try:
    patches = []
    if cert_arn not in ['', None] and cert_arn != domain['certificateArn']:
      patches.append({'op': 'replace', 'path': '/certificateArn', 'value': cert_arn})
    if cert_name not in ['', None] and cert_name != domain['certificateName']:
      patches.append({'op': 'replace', 'path': '/certificateName', 'value': cert_name})
    if security_policy not in ['', None] and security_policy != domain.get('securityPolicy'):
      patches.append({'op': 'replace', 'path': '/securityPolicy', 'value': security_policy})

    if patches:
      changed = True

      if not module.check_mode:
        domain = backoff_update_domain_name(client, name, patches)
  except botocore.exceptions.BotoCoreError as e:
    module.fail_json(msg="Error when updating domain_name via boto3: {}".format(e))

  # Don't want response metadata. It's not documented as part of return, so not sure why it's here
  domain.pop('ResponseMetadata', None)

  return {
    'changed': changed,
    'domain_name': camel_dict_to_snake_dict(domain),
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
    if e.response['Error']['Code'] == 'NotFoundException':
      resp = None
    else:
      module.fail_json(msg="Error when getting domain_name from boto3: {}".format(e))
  except botocore.exceptions.BotoCoreError as e:
    module.fail_json(msg="Error when getting domain_name from boto3: {}".format(e))

  return resp


if __name__ == '__main__':
    main()
