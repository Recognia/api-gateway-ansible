#!/usr/bin/python

# API Gateway Ansible Modules
#
# Modules in this project allow management of the AWS API Gateway service.
#
# Authors:
#  - Brian Felton <github: bjfelton>
#  - Malcolm Studd <github: mestudd>
#
# apigw_rest_api
#    Manage creation, update, and removal of API Gateway REST APIs
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
module: apigw_rest_api
author: Brian Felton (@bjfelton)
short_description: Add, update, or remove REST API resources
description:
  - An Ansible module to add, update, or remove REST API resources for AWS API Gateway.
version_added: "2.2"
options:
  id:
    description: The id of the rest api on which to operate. Either C(name) or C(id) is required.
    required: False
  name:
    description: The name of the rest api on which to operate. Either C(name) or C(id) is required.
    required: False
  api_key_source:
    description: The source of the API key for metering requests according to a usage plan.
    choices: ['HEADER', 'AUTHORIZER']
    required: False
  binary_media_types:
    description: The list of binary media types supported by the RestApi.
    required: False
  clone_from:
    description: The name or id of a rest api to clone from (only if rest api is created).
    required: False
  description:
    description:
      - A description for the rest api
    required: False
  endpoint_configuration:
    description: The endpoint configuration of this RestApi showing the endpoint types of the API.
    type: complex:
    contains:
      types:
        description: The list of endpoint types.
        choices: [ 'EDGE', 'REGIONAL', 'PRIVATE' ]
  minimum_compression_size:
    description: Enable compression with a payload size larger than this value.
    required: False
  policy:
    description: A stringified JSON policy document that applies to this RestApi regardless of the caller and Method configuration.
    required: False
  version:
    description: A version identifier for the API.
    required: False
  state:
    description:
      - Determine whether to assert if api should exist or not
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
- name: Add rest api to Api Gateway
  hosts: localhost
  gather_facts: False
  connection: local
  tasks:
    - name: Create rest api
      apigw_rest_api:
        name: 'docs.example.io'
        description: 'stolen straight from the docs'
        state: present
      register: api

    - name: debug
      debug: var=api

- name: Rest api from Api Gateway
  hosts: localhost
  gather_facts: False
  connection: local
  tasks:
    - name: Create rest api
      apigw_rest_api:
        name: 'docs.example.io'
        state: absent
      register: api

    - name: debug
      debug: var=api
'''

RETURN = '''
### Sample create response
{
    "api": {
        "ResponseMetadata": {
            "HTTPHeaders": {
                "content-length": "79",
                "content-type": "application/json",
                "date": "Thu, 27 Oct 2016 11:55:05 GMT",
                "x-amzn-requestid": "<request id here>"
            },
            "HTTPStatusCode": 201,
            "RequestId": "<request id here>"
            "RetryAttempts": 0
        },
        "createdDate": "2016-10-27T06:55:05-05:00",
        "description": "example description",
        "id": "c8888abcde",
        "name": "example-api"
    },
    "changed": true,
    "invocation": {
        "module_args": {
            "description": "examble description",
            "name": "example-api",
            "state": "present"
        }
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

param_map = {
    'api_key_source': 'apiKeySource',
    'endpoint_configuration': 'endpointConfiguration',
    'binary_media_types': 'binaryMediaTypes',
    'minimum_compression_size': 'minimumCompressionSize',
}

def main():
    argument_spec = dict(
        name=dict(required=False),
        id=dict(required=False),
        description=dict(required=False),
        api_key_source=dict(required=False, choices=['HEADER', 'AUTHORIZER']),
        binary_media_types=dict(
            required=False,
            type='list',
            elements='str'
        ),
        clone_from=dict(required=False),
        endpoint_configuration=dict(
            required=False,
            type='dict',
            options=dict(
                types=dict(
                    required=True,
                    type='list',
                    choices=['REGIONAL', 'EDGE', 'PRIVATE']
                ),
            ),
        ),
        minimum_compression_size=dict(required=False, type='int'),
        policy=dict(required=False),
        version=dict(required=False),
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
            result = ensure_rest_api_present(module, client)
        elif state == 'absent':
            result = ensure_rest_api_absent(module, client)
    except botocore.exceptions.ClientError as e:
        module.fail_json_aws(e)

    module.exit_json(**result)


@AWSRetry.exponential_backoff()
def backoff_create_rest_api(client, args):
    return client.create_rest_api(**args)


@AWSRetry.exponential_backoff()
def backoff_delete_rest_api(client, rest_api_id):
    return client.delete_rest_api(restApiId=rest_api_id)


@AWSRetry.exponential_backoff()
def backoff_get_rest_api(client, rest_api_id):
    return client.get_rest_api(restApiId=rest_api_id)


@AWSRetry.exponential_backoff()
def backoff_get_rest_apis(client):
    return client.get_rest_apis(
        limit=500
    )


@AWSRetry.exponential_backoff()
def backoff_update_rest_api(client, rest_api_id, patches):
    return client.update_rest_api(
        restApiId=rest_api_id,
        patchOperations=patches
    )


def create_patches(module, rest_api):
    patches = []

    new = module.params.get('endpoint_configuration')
    old = rest_api['endpointConfiguration']['types'][0]
    if new is not None and new['types'][0] != old:
        patches.append({'op': 'replace', 'path': "/endpointConfiguration/types/{}".format(old), 'value': str(new['types'][0])})

    for f in [ 'binary_media_types' ]:
        new = module.params.get(f)
        key = param_map.get(f, f)
        old = rest_api.get(key)
        if new is not None and new != old:
            module.fail_json(msg="This module does not yet support updating "+ f)

    for f in [ 'name', 'description', 'api_key_source', 'minimum_compression_size', 'policy', 'version' ]:
        new = module.params.get(f)
        key = param_map.get(f, f)
        old = rest_api.get(key)
        if new is not None and new != old:
            if old is None:
                patches.append({'op': 'add', 'path': "/{}".format(key), 'value': str(new)})
            elif old != new:
                patches.append({'op': 'replace', 'path': "/{}".format(key), 'value': str(new)})

    return patches


def create_rest_api(module, client):
    args = dict(
        name=module.params['name'],
    )

    clone_from = module.params.get('clone_from')
    if clone_from:
        orig = find_rest_api(module, client, clone_from)
        if not orig:
            module.fail_json(msg="Could not find clone_from api")
        args['cloneFrom'] = orig.get('id')

    for f in [ 'name', 'description', 'api_key_source', 'binary_media_types', 'endpoint_configuration', 'minimum_compression_size', 'policy', 'version' ]:
        v = module.params.get(f)
        if v is not None:
            boto_param = param_map.get(f, f)
            args[boto_param] = module.params[f]

    return backoff_create_rest_api(client, args)


def ensure_rest_api_absent(module, client):
  rest_api = find_rest_api(module, client)

  if rest_api is None:
    return {'changed': False}

  try:
    if not module.check_mode:
      backoff_delete_rest_api(client, rest_api['id'])
    return {
        'changed': True,
        'api': camel_dict_to_snake_dict(rest_api)
    }
  except (botocore.exceptions.ClientError, botocore.exceptions.BotoCoreError) as e:
    module.fail_json_aws(e, msg="Couldn't delete rest api")


def ensure_rest_api_present(module, client):
    changed = False

    rest_api_id = module.params.get('id')

    rest_api = find_rest_api(module, client)

    # Create new key
    if not rest_api:
        if rest_api_id:
            module.fail_json_aws(e, msg="Couldn't find rest api for id")
        changed = True
        if not module.check_mode:
            rest_api = create_rest_api(module, client)

    else:
        patches = create_patches(module, rest_api)
        if patches:
            changed = True
            if not module.check_mode:
                rest_api = backoff_update_rest_api(client, rest_api['id'], patches)

    # Don't want response metadata. It's not documented as part of return, so not sure why it's here
    rest_api.pop('ResponseMetadata', None)

    return {
        'changed': changed,
        'api': camel_dict_to_snake_dict(rest_api)
    }


def find_rest_api(module, client, other=None):
    resp = None
    name = module.params.get('name')
    rest_api_id = module.params.get('id')

    try:
        if other:
            all_apis = backoff_get_rest_apis(client)

            for l in all_apis.get('items'):
                if other in [ l.get('name'), l.get('id') ]:
                    resp = l
        elif rest_api_id:
            # lookup by id
            resp = backoff_get_rest_api(client, rest_api_id)
        else:
            # lookup by name
            if not name:
                module.fail_json(msg="Rest api name or id is required")

            all_apis = backoff_get_rest_apis(client)

            for l in all_apis.get('items'):
                if name == l.get('name'):
                    resp = l

    except botocore.exceptions.ClientError as e:
        if 'NotFoundException' in e.message:
            resp = None
        else:
            module.fail_json(msg="Error when getting rest api from boto3: {}".format(e))
    except botocore.exceptions.BotoCoreError as e:
        module.fail_json(msg="Error when getting api rest api boto3: {}".format(e))

    return resp


if __name__ == '__main__':
    main()
