#!/usr/bin/python

# API Gateway Ansible Modules
#
# Modules in this project allow management of the AWS API Gateway service.
#
# Authors:
#  - Brian Felton <github: bjfelton>
#  - Malcolm Studd <github: mestudd>
#
# apigw_usage_plan
#    Manage creation, update, and removal of API Gateway UsagePlan resources
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
module: apigw_usage_plan
author: Brian Felton (@bjfelton)
short_description: Add, update, or remove UsagePlan and UsagePlanKey resources
description:
- Basic CRUD operations on Usage Plan Key resources
- Does not support updating name (see Notes)
version_added: "2.2"
options:
  id:
    description: The identifier of the usage plan on which to operate. Either C(name) or C(id) is required to identify the usage plan.
    type: string
    required: False
  name:
    description:
    - The name of the UsagePlan resource on which to operate. Required for create. Either C(name) or C(id) is required to identify the usage plan.
    type: string
    required: False
  description:
    description:
    - UsagePlan description
    type: string
    default: None
    required: False
  api_stages:
    description:
    - List of associated api stages
    type: list
    default: []
    required: False
    options:
      rest_api_id:
        description:
        - ID of the associated API stage in the usage plan
        type: string
        required: True
      stage:
        description:
        - API stage name of the associated API stage in the usage plan
        type: string
        required: True
  purge_api_stages:
    description: If yes, existing api stages will be purged from the usage plan to match exactly what is defined by C(api_stages) parameter. If the C(api_stages) parameter is not set then api stages will not be modified.
    type: bool
    default: True
    required: False
  throttle_burst_limit:
    description:
    - API request burst limit
    type: int
    default: -1
    required: False
  throttle_rate_limit:
    description:
    - API request steady-state limit
    type: double
    default: -1.0
    required: False
  purge_throttle:
    description: If yes, throttling will be purged from the usage plan if the C(throttle_burst_limit) and C(throttle_rate_limit) parameters are not set.
    type: bool
    default: True
    required: False
  quota_limit:
    description:
    - Maxiumum number of requests that can be made in a given time period
    type: integer
    default: -1
    required: False
  quota_offset:
    description:
    - Number of requests subtracted from the given limit in the initial time period
    type: integer
    default: -1
    required: False
  quota_period:
    description:
    - The time period in which the limit applies
    type: string
    default: ''
    choices: ['', 'DAY', 'WEEK', 'MONTH']
    required: False
  purge_quota:
    description: If yes, quota will be purged from the usage plan if the C(quota_limit), C(quota_offset) and C(quota_period) parameters are not set.
    type: bool
    default: True
    required: False
  state:
    description:
    - Should usage_plan exist or not
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
    apigw_usage_plan:
      name: testplan
      description: 'this is an awesome test'
      api_stages:
        - rest_api_id: abcde12345
          stage: live
      throttle_burst_limit: 111
      throttle_rate_limit: 222.0
      quota_limit: 333
      quota_offset: 0
      quota_period: WEEK
      state: "{{ state | default('present') }}"
    register: plan

  - debug: var=plan
'''

RETURN = '''
{
  "plan": {
    "changed": true,
    "usage_plan": {
      "ResponseMetadata": {
        "HTTPHeaders": {
          "content-length": "223",
          "content-type": "application/json",
          "date": "Thu, 15 Dec 2016 15:49:47 GMT",
        },
        "HTTPStatusCode": 201,
        "RetryAttempts": 0
      },
      "apiStages": [
        {
          "apiId": "abcde12345",
          "stage": "live"
        }
      ],
      "description": "this is an awesome test",
      "id": "abc123",
      "name": "testplan",
      "quota": {
        "limit": 333,
        "offset": 0,
        "period": "WEEK"
      },
      "throttle": {
        "burstLimit": 111,
        "rateLimit": 222.0
      }
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
    'throttle_burst_limit': 'throttle/burstLimit',
    'throttle_rate_limit': 'throttle/rateLimit',
    'quota_offset': 'quota/offset',
    'quota_limit': 'quota/limit',
    'quota_period': 'quota/period',
}

argument_spec = dict(
    name=dict(required=True),
    description=dict(required=False, default=''),
    api_stages=dict(
        type='list',
        required=False,
        default=[],
        rest_api_id=dict(required=True),
        stage=dict(required=True)
    ),
    purge_api_stages=dict(required=False, type='bool', default=True),
    throttle_burst_limit=dict(required=False, default=-1, type='int'),
    throttle_rate_limit=dict(required=False, default=-1.0, type='float'),
    purge_throttle=dict(required=False, type='bool', default=True),
    quota_limit=dict(required=False, default=-1, type='int'),
    quota_offset=dict(required=False, default=-1, type='int'),
    quota_period=dict(required=False, default='', choices=['', 'DAY','WEEK','MONTH']),
    purge_quota=dict(required=False, type='bool', default=True),
    state=dict(default='present', choices=['present', 'absent']),
)

def main():
    module = AnsibleAWSModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    client = module.client('apigateway')

    state = module.params.get('state')

    try:
        if state == "present":
            result = ensure_usage_plan_present(module, client)
        elif state == 'absent':
            result = ensure_usage_plan_absent(module, client)
    except botocore.exceptions.ClientError as e:
        module.fail_json_aws(e)

    module.exit_json(**result)


@AWSRetry.exponential_backoff()
def backoff_create_usage_plan(client, args):
    return client.create_usage_plan(**args)


@AWSRetry.exponential_backoff()
def backoff_delete_usage_plan(client, usage_plan_id):
    return client.delete_usage_plan(usagePlanId=usage_plan_id)


@AWSRetry.exponential_backoff()
def backoff_get_usage_plan(client, usage_plan_id):
    return client.get_usage_plan(
        usagePlanId=usage_plan_id,
    )


@AWSRetry.exponential_backoff()
def backoff_get_usage_plans(client):
    return client.get_usage_plans(limit=500)


@AWSRetry.exponential_backoff(delay=10)
def backoff_update_usage_plan(client, usage_plan_id, patches):
    return client.update_usage_plan(
        usagePlanId=usage_plan_id,
        patchOperations=patches
    )


def create_api_stages_remove_patches(old, leave):
    patches = []
    for stage in old:
        if stage not in leave:
            patches.append({'op': 'remove', 'path': '/apiStages', 'value': stage})

    return patches

def create_patches(module, usage_plan):
    patches = []

    def all_defaults(params_list):
        is_default = False
        for p in params_list:
            is_default = is_default or is_default_value(p, module.params.get(p, None))

        return is_default

    def get_value(key):
        entry = usage_plan
        for k in key.split('/'):
            entry = entry.get(k)
            if entry is None:
                break
        return entry

    def patch_field(f):
        new = module.params.get(f, None)
        key = param_map.get(f, f)
        old = get_value(key)
        if not is_default_value(f, new):
            if old is None:
                patches.append({'op': 'add', 'path': "/{}".format(key), 'value': str(new)})
            elif old != new:
                patches.append({'op': 'replace', 'path': "/{}".format(key), 'value': str(new)})

    old_api_stages = [ "{0}:{1}".format(s['apiId'], s['stage'])
            for s in usage_plan.get('apiStages', [])]
    new_api_stages = [ "{0}:{1}".format(s['rest_api_id'], s['stage'])
            for s in module.params.get('api_stages', [])]

    # remove api stages first, in case they have throttling
    if 'apiStages' in usage_plan and module.params.get('purge_api_stages'):
        # FIXME: want to only remove un-listed api stages
        patches.extend(create_api_stages_remove_patches(old_api_stages, new_api_stages))

    # clear throttling and quota if they should be removed
    if 'throttle' in usage_plan and module.params.get('purge_throttle'):
        if all_defaults(['throttle_rate_limit', 'throttle_burst_limit']):
            patches.append({'op': 'remove', 'path': "/throttle"})
    if 'quota' in usage_plan and module.params.get('purge_quota'):
        if all_defaults(['quota_limit', 'quota_offset', 'quota_period']):
            patches.append({'op': 'remove', 'path': "/quota"})

    # patch any new values
    patch_field('description')

    patch_field('quota_limit')
    patch_field('quota_period')
    patch_field('quota_offset')

    patch_field('throttle_burst_limit')
    patch_field('throttle_rate_limit')

    # add new api stages
    for stage in new_api_stages:
        if stage not in old_api_stages:
            patches.append({'op': 'add', 'path': '/apiStages', 'value': stage})

    return patches


def create_usage_plan(module, client):
    args = dict(
        name=module.params['name'],
        apiStages=[],
    )

    for f in ['description','throttle_burst_limit','throttle_rate_limit','quota_limit','quota_period','quota_offset']:
        if not is_default_value(f, module.params.get(f, None)):
            boto_param = param_map.get(f, f)
            if '/' in boto_param:
                (p1, p2) = boto_param.split('/')
                if p1 not in args:
                    args[p1] = {}
                args[p1].update({p2: module.params[f]})
            else:
                args[boto_param] = module.params[f]

    for stage in module.params.get('api_stages', []):
        args['apiStages'].append({'apiId': stage.get('rest_api_id'), 'stage': stage.get('stage')})
    #print args

    return backoff_create_usage_plan(client, args)


def ensure_usage_plan_absent(module, client):
    usage_plan = find_usage_plan(module, client)

    if usage_plan is None:
        return {'changed': False}

    try:
        if not module.check_mode:
            # AWS requires removing all api stages prior to deleting
            if 'apiStages' in usage_plan:
                old_api_stages = [ "{0}:{1}".format(s['apiId'], s['stage'])
                        for s in usage_plan.get('apiStages', [])]
                patches = create_api_stages_remove_patches(old_api_stages, [])
                if patches:
                    backoff_update_usage_plan(client, usage_plan['id'], patches)
            backoff_delete_usage_plan(client, usage_plan['id'])
        return {'changed': True}
    except (botocore.exceptions.ClientError, botocore.exceptions.BotoCoreError) as e:
        module.fail_json_aws(e, msg="Couldn't delete usage plan")


def ensure_usage_plan_present(module, client):
    changed = False
    usage_plan_id = module.params.get('id')

    usage_plan = find_usage_plan(module, client)

    # Create new key
    if not usage_plan:
        if usage_plan_id:
            module.fail_json_aws(e, msg="Couldn't find api key for id")
        changed = True
        if not module.check_mode:
            usage_plan = create_usage_plan(module, client)

    else:
        patches = create_patches(module, usage_plan)
        if patches:
            changed = True
            if not module.check_mode:
                usage_plan = backoff_update_usage_plan(client, usage_plan['id'], patches)

    # Don't want response metadata. It's not documented as part of return, so not sure why it's here
    usage_plan.pop('ResponseMetadata', None)

    return {
        'changed': changed,
        'usage_plan': camel_dict_to_snake_dict(usage_plan)
    }


def find_usage_plan(module, client):
    """
    Retrieve usage plan by provided name
    :return: Result matching the provided usage plan or None
    """
    resp = None
    name = module.params.get('name')
    usage_plan_id = module.params.get('id')

    try:
        if usage_plan_id:
            # lookup by id
            resp = backoff_get_usage_plan(client, usage_plan_id)
        else:
            # lookup by name
            if not name:
                module.fail_json(msg="Usage plan name or id is required")

            all_plans = backoff_get_usage_plans(client)

            for l in all_plans.get('items'):
                if name == l.get('name'):
                    resp = l

    except botocore.exceptions.ClientError as e:
        if 'NotFoundException' in e.message:
            resp = None
        else:
            module.fail_json(msg="Error when getting usage plans from boto3: {}".format(e))
    except botocore.exceptions.BotoCoreError as e:
        module.fail_json(msg="Error when getting usage plans from boto3: {}".format(e))

    return resp


def is_default_value(param_name, param_value):
    if argument_spec[param_name].get('type', 'string') in ['int', 'float']:
        return param_value < 0
    else:
        return param_value in [None, '']


if __name__ == '__main__':
    main()
