#!/usr/bin/python

# API Gateway Ansible Modules
#
# Modules in this project allow management of the AWS API Gateway service.
#
# Authors:
#  - Brian Felton <github: bjfelton>
#  - Malcolm Studd <github: mestudd>
#
# apigw_base_path_mapping
#    Manage creation, update, and removal of API Gateway Base Path Mapping resources
#

# MIT License
#
# Copyright (c) 2016 Brian Felton, Emerson
# Copyright (c) 2019 Malcolm Studd
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
module: apigw_base_path_mapping
author: Brian Felton (@bjfelton)
short_description: Add, update, or remove Base Path Mapping resources
description:
- Basic CRUD operations for Base Path Mapping resources
version_added: "2.2"
options:
  name:
    description:
    - The domain name of the Base Path Mapping resource on which to operate
    required: True
    aliases: ['domain_name']
  rest_api_id:
    description:
    - The id of the Rest API to which this BasePathMapping belongs.  Required to create a base path mapping.
    default: None
    required: False
  base_path:
    description:
    - The base path name that callers of the api must provide.  Required when updating or deleting the mapping.
    default: (none)
    required: False
  stage:
    description:
    - The name of the api's stage to which to apply this mapping.  Required to create the base path mapping.
    default: None
    required: False
  state:
    description:
    - Should base_path_mapping exist or not
    choices: ['present', 'absent']
    default: 'present'
    required: False
requirements:
    - python = 2.7
    - boto
    - boto3
notes:
    - This module requires that you have boto and boto3 installed and that your credentials are created or stored in a way that is compatible (see U(https://boto3.readthedocs.io/en/latest/guide/quickstart.html#configuration)).
'''

EXAMPLES = '''
---
- hosts: localhost
  gather_facts: False
  tasks:
  - name: do base path stuff
    apigw_base_path_mapping:
      name: dev.example.com
      rest_api_id: abcd1234
      stage: live
      state: present
    register: bpm

  - debug: var=bpm
'''

RETURN = '''
{
  "bpm": {
    "base_path_mapping": {
      "basePath": "(none)",
      "restApiId": "41pz250gl3",
      "stage": "live"
    },
    "changed": false
  }
}
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
        rest_api_id=dict(required=False),
        rest_api=dict(required=False),
        base_path=dict(required=False, default='(none)'),
        stage=dict(required=False),
        state=dict(default='present', choices=['present', 'absent']),
    )

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    client = module.client('apigateway')

    state = module.params.get('state')
    name = module.params.get('name')
    path = module.params.get('base_path')

    base_path_mapping = backoff_get_base_path_mapping(client, name, path)

    try:
        if state == "present":
            rest_api_id = module.params.get('rest_api_id')
            if rest_api_id in ['', None]:
                rest_api_id = find_rest_api(module, client)
            result = ensure_base_path_mapping_present(module, client, base_path_mapping, name, rest_api_id)

        elif state == 'absent':
            result = ensure_base_path_mapping_absent(module, client, base_path_mapping, name)
    except botocore.exceptions.ClientError as e:
        module.fail_json_aws(e)

    module.exit_json(**result)


@AWSRetry.exponential_backoff()
def backoff_create_base_path_mapping(client, name, path):
    return client.create_base_path_mapping(
        domainName=name,
        basePath=path,
    )


@AWSRetry.exponential_backoff()
def backoff_delete_base_path_mapping(client, name, path):
    return client.delete_base_path_mapping(
        domainName=name,
        basePath=path,
    )


@AWSRetry.exponential_backoff()
def backoff_get_base_path_mapping(client, name, path):
    return client.get_base_path_mapping(
        domainName=name,
        basePath=path,
    )


@AWSRetry.exponential_backoff()
def backoff_update_base_path_mapping(client, name, path, patches):
    return client.update_base_path_mapping(
        domainName=name,
        basePath=path,
        patchOperations=patches
    )


def ensure_base_path_mapping_absent(module, client, base_path_mapping, name):
    if base_path_mapping is None:
        return {'changed': False}

    try:
        if not module.check_mode:
            backoff_delete_usage_plan_key(client, name, base_path_mapping['basePath'])
        return {'changed': True}
    except (botocore.exceptions.ClientError, botocore.exceptions.BotoCoreError) as e:
        module.fail_json_aws(e, msg="Couldn't delete usage plan key")


def ensure_base_path_mapping_present(module, client, base_path_mapping, name, rest_api_id):
    changed = False
    path = module.params.get('base_path', '(none)')
    stage = module.params.get('stage', None)

    if not base_path_mapping:
        raise ValueError('creating!')
        changed = True
        args = dict(
            domainName = name,
            restApiId = rest_api_id,
            basePath = path,
        )
        if stage is not None and stage != '':
            args['stage'] = stage

        if not module.check_mode:
            base_path_mapping = backoff_create_base_path_mapping(client, args)

    else:
        patches = []
        if rest_api_id not in [ '', None ] and rest_api_id != base_path_mapping['restApiId']:
            # Yay for consistency. Thanks, amazon!
            patches.append({'op': 'replace', 'path': '/restapiId', 'value': rest_api_id})
        if stage != '' and stage is not None and stage != base_path_mapping['stage']:
            patches.append({'op': 'replace', 'path': '/stage', 'value': stage})

        if patches:
            changed = True
            if not module.check_mode:
                base_path_mapping = backoff_update_base_path_mapping(client, name, path, patches)

    # Don't want response metadata. It's not documented as part of return, so not sure why it's here
    base_path_mapping.pop('ResponseMetadata', None)

    return {
        'changed': changed,
        'base_path_mapping': camel_dict_to_snake_dict(base_path_mapping),
    }


def find_rest_api(module, client):
    resp = None
    name = module.params.get('rest_api')

    if not name:
        module.fail_json(msg="Rest api name or id is required")

    all_apis = backoff_get_rest_apis(client)

    for l in all_apis.get('items'):
        if name == l.get('name'):
            resp = l.get('id')

    return resp


if __name__ == '__main__':
    main()
