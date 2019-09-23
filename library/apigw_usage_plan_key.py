#!/usr/bin/python

# API Gateway Ansible Modules
#
# Modules in this project allow management of the AWS API Gateway service.
#
# Authors:
#  - Brian Felton <github: bjfelton>
#  - Malcolm Studd <github: mestudd>
#
# apigw_usage_plan_key
#    Manage creation and removal of API Gateway UsagePlanKey resources
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
module: apigw_usage_plan_key
author: Brian Felton (@bjfelton)
short_description: Add or remove UsagePlanKey resources
description:
- Create or remove Usage Plan Key resources
version_added: "2.2"
options:
  usage_plan:
    description:
    - Name of the UsagePlan resource to which a key will be associated. Either C(usage_plan) or C(usage_plan_id) is required.
    type: string
    required: False
  usage_plan_id:
    description:
    - Id of the UsagePlan resource to which a key will be associated. Either C(usage_plan) or C(usage_plan_id) is required.
    type: string
    required: False
  api_key:
    description:
    - Name of the api key resource to which a key will be associated. Either C(api_key) or C(api_key_id) is required.
    type: string
    required: False
  api_key_id:
    description:
    - Id of the api key resource to which a key will be associated. Either C(api_key) or C(api_key_id) is required.
    type: string
    required: False
  key_type:
    description:
    - Type of the api key.  You can choose any value you like, so long as you choose 'API_KEY'.
    type: string
    default: 'API_KEY'
    required: False
    choices: ['API_KEY']
  state:
    description:
    - Should usage_plan_key exist or not
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
  - name: usage plan creation
    apigw_usage_plan_key:
      usage_plan_id: 12345abcde
      api_key_id: zyxw9876
      key_type: API_KEY
      state: present
    register: plankey

  - debug: var=plankey
'''

RETURN = '''
{
  "plankey": {
    "changed": true,
    "usage_plan_key": {
      "ResponseMetadata": {
        "HTTPHeaders": {
          "content-length": "58",
          "content-type": "application/json",
          "date": "Thu, 15 Dec 2016 18:03:22 GMT",
        },
        "HTTPStatusCode": 201,
        "RetryAttempts": 0
      },
      "id": "abcdefghhi",
      "name": "testkey5000",
      "type": "API_KEY"
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

def main():
    argument_spec = dict(
        api_key_id=dict(required=False),
        api_key=dict(required=False),
        usage_plan_id=dict(required=False),
        usage_plan=dict(required=False),
        key_type=dict(required=False, default='API_KEY', choices=['API_KEY']),
        state=dict(default='present', choices=['present', 'absent']),
    )

    mutually_exclusive = [['api_key', 'api_key_id'], ['usage_plan', 'usage_plan_id']]

    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        mutually_exclusive=mutually_exclusive,
        supports_check_mode=True,
    )

    client = module.client('apigateway')

    state = module.params.get('state')

    api_key_id = module.params.get('api_key_id')
    if api_key_id in ['', None]:
        api_key_id = find_api_key(module, client)

    usage_plan_id = module.params.get('usage_plan_id')
    if usage_plan_id in ['', None]:
        usage_plan_id = find_usage_plan(module, client)

    try:
        if state == "present":
            result = ensure_usage_plan_key_present(module, client, api_key_id, usage_plan_id)
        elif state == 'absent':
            result = ensure_usage_plan_key_absent(module, client, api_key_id, usage_plan_id)
    except botocore.exceptions.ClientError as e:
        module.fail_json_aws(e)

    module.exit_json(**result)


@AWSRetry.exponential_backoff()
def backoff_create_usage_plan_key(client, api_key_id, usage_plan_id, key_type):
    return client.create_usage_plan_key(
        keyId=api_key_id,
        usagePlanId=usage_plan_id,
        keyType=key_type,
    )


@AWSRetry.exponential_backoff()
def backoff_delete_usage_plan_key(client, api_key_id, usage_plan_id):
    return client.delete_usage_plan_key(
        keyId=api_key_id,
        usagePlanId=usage_plan_id,
    )


@AWSRetry.exponential_backoff()
def backoff_get_api_keys(client, name):
    return client.get_api_keys(nameQuery=name)


@AWSRetry.exponential_backoff()
def backoff_get_usage_plans(client):
    return client.get_usage_plans(limit=500)


@AWSRetry.exponential_backoff()
def backoff_get_usage_plan_key(client, api_key_id, usage_plan_id):
    try:
        return client.get_usage_plan_key(
            keyId=api_key_id,
            usagePlanId=usage_plan_id,
        )
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == 'NotFoundException':
            return None
        else:
            module.fail_json_aws(e, msg="Error when getting usage plan key from boto3")
    except botocore.exceptions.BotoCoreError as e:
        module.fail_json_aws(e, msg="Error when getting usage plan key from boto3")


def ensure_usage_plan_key_absent(module, client, api_key_id, usage_plan_id):
    usage_plan_key = backoff_get_usage_plan_key(client, api_key_id, usage_plan_id)

    if usage_plan_key is None:
        return {'changed': False}

    try:
        if not module.check_mode:
            backoff_delete_usage_plan_key(client, api_key_id, usage_plan_id)
        return {'changed': True}
    except (botocore.exceptions.ClientError, botocore.exceptions.BotoCoreError) as e:
        module.fail_json_aws(e, msg="Couldn't delete usage plan key")


def ensure_usage_plan_key_present(module, client, api_key_id, usage_plan_id):
    changed = False

    usage_plan_key = backoff_get_usage_plan_key(client, api_key_id, usage_plan_id)
    key_type = module.params.get('key_type')

    if usage_plan_key is None:
        try:
            changed = True
            if not module.check_mode:
                usage_plan_key = backoff_create_usage_plan_key(client, api_key_id, usage_plan_id, key_type)
        except (botocore.exceptions.ClientError, botocore.exceptions.BotoCoreError) as e:
            module.fail_json_aws(e, msg="Couldn't add usage plan key")

    # Don't want response metadata. It's not documented as part of return, so not sure why it's here
    usage_plan_key.pop('ResponseMetadata', None)

    return {
        'changed': changed,
        'usage_plan_key': camel_dict_to_snake_dict(usage_plan_key),
    }


def find_api_key(module, client):
    resp = None
    name = module.params.get('api_key')

    if not name:
        module.fail_json(msg="Api key name or id is required")

    all_keys = backoff_get_api_keys(client, name)

    for l in all_keys.get('items'):
        if name == l.get('name'):
            resp = l.get('id')

    return resp


def find_usage_plan(module, client):
    resp = None
    name = module.params.get('usage_plan')

    if not name:
        module.fail_json(msg="Usage plan name or id is required")

    all_plans = backoff_get_usage_plans(client)

    for l in all_plans.get('items'):
        if name == l.get('name'):
            resp = l.get('id')

    return resp


if __name__ == '__main__':
    main()
