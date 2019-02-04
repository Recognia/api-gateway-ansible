#!/usr/bin/python

# apigw_vpc_link
#    Manage creation, update, and removal of API Gateway VPC link resources


DOCUMENTATION='''
---
module: apigw_vpc_link
author: Malcolm Studd
short_description: Add, update, or remove VPC link resources
description:
- Uses name for identifying resources for CRUD operations
version_added: "2.2"
options:
  description:
    description:
    - Description of the VPC link resource
    type: string
    required: false
  name:
    description:
    - The name of the VPC link resource on which to operate. Either name or vpc_link_id is required to identify the VPC link
    type: string
    required: false
  state:
    description:
    - Should vpc link exist or not
    choices: ['present', 'absent']
    default: 'present'
    required: false
  target_arns:
    description:
    - A list of ARNs of the network load balancers to link. AWS only supports a single ARN.
    type: string
    required: false
  vpc_link_id:
    description: The ID of the VPC link. Either name or vpc_link_id is required to identify the VPC link
    type: string
    required: false
requirements:
    - python = 2.7
    - boto
    - boto3
extends_documentation_fragment:
    - aws
    - ec2
'''

EXAMPLES = '''
---
- hosts: localhost
  gather_facts: False
  tasks:
  - name: Link network load balancer with api gateway
    apigw_vpc_link:
      state: present
      name: link-nlb
      description: Link to my VPC
      target_arns:
        - arn:aws:elasticloadbalancing:us-east-1:12345:loadbalancer/net/my-nlb
    register: vpc_link

  - debug: var=vpc_link

  - name: Update vpc link (identifying by id)
    apigw_vpc_link:
      vpc_link_id: "{{ vpc_link.vpc_link_id }}"
      name: new-nlb-link-name
    register: vpc_link

  - name: Delete vpc link (identifying by name)
    apigw_vpc_link:
      state: absent
      name: new-nlb-link-name
    register: vpc_link
'''

RETURN = '''
---
vpc_link:
  description: dictionary representing the vpc link
  returned: success
  type: dict
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
        name=dict(required=True, type='str'),
        description=dict(required=False),
        target_arns=dict(type='list',
            elements='str'
        ),
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
        result = ensure_vpc_link_present(module, client)
      elif state == 'absent':
        result = ensure_vpc_link_absent(module, client)
    except botocore.exceptions.ClientError as e:
        module.fail_json_aws(e)

    module.exit_json(**result)


@AWSRetry.exponential_backoff()
def backoff_create_vpc_link(client, name, description, target_arns):
    return client.create_vpc_link(
        name=name,
        description=description,
        targetArns=target_arns
    )

@AWSRetry.exponential_backoff()
def backoff_delete_vpc_link(client, vpc_link_id):
    return client.delete_vpc_link(vpcLinkId=vpc_link_id)


@AWSRetry.exponential_backoff()
def backoff_get_vpc_link(client, vpc_link_id):
    return client.get_vpc_link(vpcLinkId=vpc_link_id)


@AWSRetry.jittered_backoff()
def backoff_get_vpc_links(client):
    # no pagination as AWS has 5 link limit
    return client.get_vpc_links()


@AWSRetry.exponential_backoff()
def backoff_update_vpc_link(client, vpc_link_id, patches):
    pass
    return client.update_vpc_link(
        vpcLinkId=vpc_link_id,
        patchOperations=patches
    )


def ensure_vpc_link_absent(module, client):
    vpc_link = find_vpc_link(module, client)

    if vpc_link is None:
        return {'changed': False}

    try:
        if not module.check_mode:
            backoff_delete_vpc_link(client, vpc_link.vpc_link_id)
        return {'changed': True}
    except (botocore.exceptions.ClientError, botocore.exceptions.BotoCoreError) as e:
        module.fail_json_aws(e, msg="Couldn't delete vpc link")


def ensure_vpc_link_present(module, client):
    changed = False
    name = module.params.get('name')
    vpc_link_id = module.params.get('vpc_link_id')
    description = module.params.get('description')
    target_arns = module.params.get('target_arns')

    vpc_link = find_vpc_link(module, client)

    # Create new link
    if not vpc_link:
        if vpc_link_id:
            module.fail_json_aws(e, msg="Couldn't find vpc link for id")
        changed = True
        if not module.check_mode:
            vpc_link = backoff_create_vpc_link(client, name, description, target_arns)

    else:
        patches = []
        if name not in ['', None] and name != vpc_link['name']:
            patches.append({'op': 'replace', 'path': '/name', 'value': name})
        if description not in ['', None] and description != vpc_link.get('description'):
            patches.append({'op': 'replace', 'path': '/description', 'value': description})
        if target_arns not in [[], None] and target_arns != vpc_link['targetArns']:
            module.fail_json(msg="Cannot change target ARNs after creation")

        if patches:
            changed = True
            if not module.check_mode:
                vpc_link = backoff_update_vpc_link(client, vpc_link['id'], patches)

    # Don't want response metadata. It's not documented as part of return, so not sure why it's here
    vpc_link.pop('ResponseMetadata', None)

    if vpc_link['status'] in ['DELETING', 'FAILED']:
        module.fail_json(msg="VPC linnk in bad state", vpc_link=camel_dict_to_snake_dict(vpc_link))

    return {
        'changed': changed,
        'vpc_link': camel_dict_to_snake_dict(vpc_link)
    }


def find_vpc_link(module, client):
    """
    Retrieve vpc link by provided name
    :return: Result matching the provided vpc link or an empty hash
    """
    resp = None
    name = module.params.get('name')
    vpc_link_id = module.params.get('vpc_link_id')

    try:
        if vpc_link_id:
            # lookup by id
            resp = backoff_get_vpc_link(client, vpc_link_id)
        else:
            # lookup by name
            if not name:
                module.fail_json(msg="VPC link name or id is required")

            all_links = backoff_get_vpc_links(client)

            for l in all_links.get('items'):
                if name == l.get('name'):
                    resp = l

    except botocore.exceptions.ClientError as e:
        if 'NotFoundException' in e.message:
            resp = None
        else:
            module.fail_json(msg="Error when getting vpc links from boto3: {}".format(e))
    except botocore.exceptions.BotoCoreError as e:
        module.fail_json(msg="Error when getting vpc links from boto3: {}".format(e))

    return resp


if __name__ == '__main__':
    main()
