#!/usr/bin/python

# Copyright: (c) 2018, Terry Jones <terry.jones@example.org>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = r'''
---
module: my_test

short_description: This is my test module

# If this is part of a collection, you need to use semantic versioning,
# i.e. the version is of the form "2.5.0" and not "2.4".
version_added: "1.0.0"

description: This is my longer description explaining my test module.

options:
    name:
        description: This is the message to send to the test module.
        required: true
        type: str
    new:
        description:
            - Control to demo if the result of this module is changed or not.
            - Parameter description can be a list as well.
        required: false
        type: bool
# Specify this value according to your collection
# in format of namespace.collection.doc_fragment_name
extends_documentation_fragment:
    - my_namespace.my_collection.my_doc_fragment_name

author:
    - Your Name (@yourGitHubHandle)
'''

EXAMPLES = r'''
# Pass in a message
- name: Test with a message
  my_namespace.my_collection.my_test:
    name: hello world

# pass in a message and have changed true
- name: Test with a message and changed output
  my_namespace.my_collection.my_test:
    name: hello world
    new: true

# fail the module
- name: Test failure of the module
  my_namespace.my_collection.my_test:
    name: fail me
'''

RETURN = r'''
# These are examples of possible return values, and in general should use other names for return values.
original_message:
    description: The original name param that was passed in.
    type: str
    returned: always
    sample: 'hello world'
message:
    description: The output message that the test module generates.
    type: str
    returned: always
    sample: 'goodbye'
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.utils.display import Display
from atlassian import Confluence, confluence

display = Display()

def create_confluence_instance(url, username, password):
    global confluence_module
    
    if ".atlassian.net" in url:
        confluence_module = Confluence(url=url, username=username, password=password, cloud=True)
    else:
        confluence_module = Confluence(url=url, username=username, password=password, cloud=False)

def _page_exists(space_key, title):
    return confluence_module.page_exists(space=space_key, title=title)

def _handle_present(module, space_key, title, body, parent_id=None):
    space_has_page = _page_exists(space_key, title)
    confluence_response = None

    # If page with title already return the page instead of creating it
    # User should use update state instead if they would like that functionality.
    if space_has_page:
        content = confluence_module.get_page_by_title(space_key, title)
        module.exit_json(changed=False, msg='Page not created since it already exists', results=content)
    
    confluence_response = confluence_module.create_page(space=space_key, title=title, body=body, type="page", representation="wiki", parent_id=parent_id)

    if confluence_response is not None:
        module.exit_json(changed=True, msg='Page created', results=confluence_response)

def _handle_absent(module, space_key, title, page_id):
    pass

def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        url=dict(type='str', required=True),
        username=dict(type='str', required=True),
        password=dict(type='str', required=True, no_log=True),
        state=dict(type='str', required=True, choices=('present', 'absent', 'update')),
        space_key=dict(type='str', required=True),
        title=dict(type='str', required=True),
        body=dict(type='str'),
        parent_id=dict(type='int'),
        page_id=dict(type='int')
    )

    # seed the result dict in the object
    # we primarily care about changed and state
    # changed is if this module effectively modified the target
    # state will include any data that you want your module to pass back
    # for consumption, for example, in a subsequent task
    result = dict(
        changed=False,
        message=''
    )

    # the AnsibleModule object will be our abstraction working with Ansible
    # this includes instantiation, a couple of common attr would be the
    # args/params passed to the execution, as well as if the module
    # supports check mode
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=False
    )
    
    params = module.params

    url = params['url']
    username = params['username']
    password = params['password']
    state = params['state']
    space_key = params['space_key']
    title = params['title']
    body = params['body']
    parent_id = params['parent_id']
    page_id = params['page_id']

    
    create_confluence_instance(url, username, password)
    
    if state in ['present']:
        _handle_present(module, space_key, title, body, parent_id)
    elif state in ['absent']:
        _handle_absent(module, space_key, title, page_id)

    # if the user is working with this module in only check mode we do not
    # want to make any changes to the environment, just return the current
    # state with no modifications
    # if module.check_mode:
    #     module.exit_json(**result)

    # manipulate or modify the state as needed (this is going to be the
    # part where your module will do what it needs to do)
    # result['original_message'] = module.params['name']
    # result['message'] = 'goodbye'

    # use whatever logic you need to determine whether or not this module
    # made any modifications to your target
    # if module.params['new']:
    #     result['changed'] = True

    # during the execution of the module, if there is an exception or a
    # conditional state that effectively causes a failure, run
    # AnsibleModule.fail_json() to pass in the message and the result
    # if module.params['name'] == 'fail me':
    #     module.fail_json(msg='You requested this to fail', **result)

    # in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    # module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()