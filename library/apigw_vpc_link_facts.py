#!/usr/bin/python

# apigw_vpc_link_facts
#    Find API Gateway VPC link resources


DOCUMENTATION='''
---
module: apigw_vpc_link
author: Malcolm Studd
short_description: Get VPC link resources
description: Get VPC link resources
version_added: "2.2"
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
    apigw_vpc_link_facts: ~
    register: vpc_link

  - debug: var=vpc_link
'''

RETURN = '''
---
vpc_links:
  description: list of dictionaries representing the vpc links
  returned: success
  type: dict
'''

try:
    import botocore
except ImportError:
    # HAS_BOTOCORE taken care of in AnsibleAWSModule
    pass

from ansible.module_utils.aws.core import AnsibleAWSModule
from ansible.module_utils.ec2 import (AWSRetry, camel_dict_to_snake_dict)

def main():
    argument_spec = dict()

    module = AnsibleAWSModule(
        argument_spec=dict()
    )

    client = module.client('apigateway')

    vpc_links = backoff_get_vpc_links(client)

    result = camel_dict_to_snake_dict({
        'changed': False,
        'vpc_links': vpc_links.get('items')
    })

    module.exit_json(**result)


@AWSRetry.jittered_backoff()
def backoff_get_vpc_links(client):
    # no pagination as AWS has 5 link limit
    return client.get_vpc_links()


if __name__ == '__main__':
    main()
