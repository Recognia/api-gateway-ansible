#!/usr/bin/python

# API Gateway Ansible Modules
#
# Modules in this project allow management of the AWS API Gateway service.
#
# Authors:
#  - Brian Felton <github: bjfelton>
#  - Malcolm Studd <github: mestudd>
#
# apigw_api_key
#    Manage creation, update, and removal of API Gateway ApiKey resources
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
module: apigw_api_key
author: Brian Felton (@bjfelton)
short_description: Add, update, or remove ApiKey resources
description:
  - Create if no ApiKey resource is found matching the provided name
  - Delete ApiKey resource matching the provided name
  - Updates I(enabled) and I(description)
version_added: "2.2"
options:
  id:
    description: The identifier of the api key on which to operate. Either C(name) or C(id) is required to identify the api key.
    type: string
    required: True
  name:
    description:
    - The domain name of the ApiKey resource on which to operate. Either C(name) or C(id) is required to identify the api key.
    type: string
    required: True
  value:
    description:
    - Value of the api key. Required for create.
    type: string
    default: None
    required: False
  description:
    description:
    - ApiKey description
    type: string
    default: None
    required: False
  enabled:
    description:
    - Can ApiKey be used by called
    type: bool
    default: False
    required: False
  generate_distinct_id:
    description:
    - Specifies whether key identifier is distinct from created apikey value
    type: bool
    default: False
    required: False
  state:
    description:
    - Should api_key exist or not
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
  - name: api key creation
    apigw_api_key:
      name: testkey5000
      description: 'this is an awesome test'
      enabled: True
      value: 'notthegreatestkeyintheworld:justatribute'
      state: present
    register: apikey

  - debug: var=apikey
'''

RETURN = '''
{
  "apikey": {
    "api_key": {
      "ResponseMetadata": {
        "HTTPHeaders": {
          "content-length": "216",
          "content-type": "application/json",
          "date": "Tue, 13 Dec 2016 03:45:35 GMT",
        },
        "HTTPStatusCode": 201,
        "RetryAttempts": 0
      },
      "createdDate": "2016-12-12T21:45:35-06:00",
      "description": "this is an awesome test",
      "enabled": true,
      "id": "24601abcde",
      "lastUpdatedDate": "2016-12-12T21:45:35-06:00",
      "name": "testkey5000",
      "stageKeys": [],
      "value": "notthegreatestkeyintheworld:justatribute"
    },
    "changed": true
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
        name=dict(required=False, type='str'),
        id=dict(required=False, type='str'),
        description=dict(required=False, type='str'),
        value=dict(required=False, type='str'),
        enabled=dict(required=False, type='bool', default=False),
        generate_distinct_id=dict(required=False, type='bool', default=False),
        state=dict(default='present', choices=['present', 'absent']),
    )

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    client = module.client('apigateway')

    state = module.params.get('state')

    try:
        if state == "present":
            result = ensure_api_key_present(module, client)
        elif state == 'absent':
            result = ensure_api_key_absent(module, client)
    except botocore.exceptions.ClientError as e:
        module.fail_json_aws(e)

    module.exit_json(**result)


@AWSRetry.exponential_backoff()
def backoff_create_api_key(client, name, description, enabled, generate_distinct_id, value):
    args= dict(
        name=name,
        enabled=enabled,
        generateDistinctId=generate_distinct_id,
    )
    if (description is not None):
        args['description'] = description
    if (value is not None):
        args['value'] = value

    return client.create_api_key(**args)


@AWSRetry.exponential_backoff()
def backoff_delete_api_key(client, api_key_id):
    return client.delete_api_key(apiKey=api_key_id)


@AWSRetry.exponential_backoff()
def backoff_get_api_key(client, api_key_id):
    return client.get_api_key(
        apiKey=api_key_id,
        includeValue=True
    )


@AWSRetry.exponential_backoff()
def backoff_get_api_keys(client, name):
    return client.get_api_keys(
        nameQuery=name,
        includeValues=True
    )


@AWSRetry.exponential_backoff()
def backoff_update_api_key(client, api_key_id, patches):
    return client.update_api_key(
        apiKey=api_key_id,
        patchOperations=patches
    )


def ensure_api_key_absent(module, client):
    api_key = find_api_key(module, client)

    if api_key is None:
        return {'changed': False}

    try:
        if not module.check_mode:
            backoff_delete_api_key(client, api_key['id'])
        return {'changed': True}
    except (botocore.exceptions.ClientError, botocore.exceptions.BotoCoreError) as e:
        module.fail_json_aws(e, msg="Couldn't delete api key")


def ensure_api_key_present(module, client):
    changed = False
    api_key_id           = module.params.get('id')
    name                 = module.params.get('name')
    description          = module.params.get('description', None)
    enabled              = module.params.get('enabled', False)
    generate_distinct_id = module.params.get('generate_distinct_id', False)
    value                = module.params.get('value', None)

    api_key = find_api_key(module, client)

    # Create new key
    if not api_key:
        if api_key_id:
            module.fail_json_aws(e, msg="Couldn't find api key for id")
        changed = True
        if not module.check_mode:
            api_key = backoff_create_api_key(client, name, description, enabled, generate_distinct_id, value)

    else:
        patches = []
        if name not in ['', None] and name != api_key['name']:
            patches.append({'op': 'replace', 'path': '/name', 'value': name})
        if description not in ['', None] and description != api_key['description']:
            patches.append({'op': 'replace', 'path': '/description', 'value': description})
        if enabled not in ['', None] and enabled != api_key['enabled']:
            patches.append({'op': 'replace', 'path': '/enabled', 'value': str(enabled)})
        if value not in ['', None] and value != api_key['value']:
            module.fail_json(msg="Cannot change value after creation")

        if patches:
            changed = True
            if not module.check_mode:
                api_key = backoff_update_api_key(client, api_key['id'], patches)

    # Don't want response metadata. It's not documented as part of return, so not sure why it's here
    api_key.pop('ResponseMetadata', None)

    return {
        'changed': changed,
        'api_key': camel_dict_to_snake_dict(api_key)
    }


def find_api_key(module, client):
    """
    Retrieve api key by provided name
    :return: Result matching the provided api key or None
    """
    resp = None
    name = module.params.get('name')
    api_key_id = module.params.get('id')

    try:
        if api_key_id:
            # lookup by id
            resp = backoff_get_api_key(client, api_key_id)
        else:
            # lookup by name
            if not name:
                module.fail_json(msg="Api key name or id is required")

            all_keys = backoff_get_api_keys(client, name)

            for l in all_keys.get('items'):
                if name == l.get('name'):
                    resp = l

    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == 'NotFoundException':
            resp = None
        else:
            module.fail_json(msg="Error when getting api keys from boto3: {}".format(e))
    except botocore.exceptions.BotoCoreError as e:
        module.fail_json(msg="Error when getting api keys from boto3: {}".format(e))

    return resp


if __name__ == '__main__':
    main()
