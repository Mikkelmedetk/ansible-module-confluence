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

from atlassian import Confluence
import logging

# Atlassian rest module is using logging module and writes out to stdout. According to developer guidelines for Ansible Modules this shouldn't be done
log = logging.getLogger(__name__)
logging.disable()

def create_confluence_instance(url, username, password):
    global confluence_module
    
    if ".atlassian.net" in url:
        confluence_module = Confluence(url=url, username=username, password=password, cloud=True)
    else:
        confluence_module = Confluence(url=url, username=username, password=password, cloud=False)

def _page_exists(space_key, title):
    is_page_existing = False
    try:
        is_page_existing = confluence_module.page_exists(space=space_key, title=title)
    except:
        pass

    return is_page_existing

def _get_page_id(space, title):
    page_id = None

    try: 
        page = confluence_module.get_page_by_title(space, title)
        page_id = page['id']
    except:
        pass

    return page_id


def _handle_present(module, space_key, title, body, overwrite, labels, parent_page_title=None):
    
    #Seed module return
    result = dict(changed=False)
    space_has_page = _page_exists(space_key, title)
    confluence_response = None
    has_labels = (labels is not None) and len(labels) > 0
    parent_id = None

    if parent_page_title:
        parent_id = _get_page_id(space_key, parent_page_title)

    # If page with title already exists return the page instead of try to create it
    if space_has_page == True and not overwrite:
        try:
            confluence_response = confluence_module.get_page_by_title(space_key, title)
        except Exception as e:
            module.fail_json(msg='Something went wrong', exception=str(e))
        result['changed'] = False
        result['msg'] = 'Page already exists, if you want to overwrite this behaviour please set overwrite module param to true'
        result['response'] = confluence_response

    # Update page if page exist and overwrite flag is set to true
    if space_has_page and overwrite:
        page_id = _get_page_id(space_key, title)

        try: 
            confluence_response = confluence_module.update_page(page_id, title, body, parent_id, type="page", representation="wiki")
        except Exception as e:
            module.fail_json(msg='Something went wrong', exception=str(e))

        result['changed'] = True
        result['msg'] = 'Page have been updated'
        result['response'] = confluence_response
            
    # If page doesn't exist create it
    if not space_has_page:
        try: 
            confluence_response = confluence_module.create_page(space=space_key, title=title, body=body, type="page", representation="wiki", parent_id=parent_id)
        except Exception as e:
            module.fail_json(msg='Something went wrong', exception=str(e))
        result['changed'] = True
        result['msg'] = 'Page have been created'
        result['response'] = confluence_response

    if has_labels and result['changed'] == True:
        _handle_add_labels(module, space_key, title, labels)        

    if confluence_response is not None:
        module.exit_json(**result)
    else:
        module.fail_json(changed=False, msg=f'Something went wrong creating or updating the page')

def _handle_absent(module, space_key, title, recursive=False):
    space_has_page = _page_exists(space_key, title)
    
    # If page with title already return the page instead of creating it
    # User should use update state instead if they would like that functionality.
    if not space_has_page:
        module.exit_json(changed=False, msg='Page does not exist, no action was taken.')

    page_id = _get_page_id(space_key, title)

    try:
        confluence_module.remove_page(page_id, status=None, recursive=recursive)
    except Exception as e:
        module.exit_json(changed=False, msg='Something went wrong deleting content', exception=str(e))

    module.exit_json(changed=True, msg='Page deleted')

def _handle_move(module, space_key, target_title, title):
    result = dict(
        changed = False
    )

    space_has_page = _page_exists(space_key, title)
    space_has_target_page = _page_exists(space_key, target_title)

    if not space_has_page or not space_has_target_page:
        result['msg'] = 'Page have not been moved, title or taget page doesn\`t exist'
        module.fail_json(**result)
    
    page_to_move = _get_page_id(space_key, title)
    page_to_target = _get_page_id(space_key, target_title)

    try:
        confluence_response = confluence_module.move_page(space_key, page_to_move, page_to_target, position="append")
        result['changed'] = True
        result['msg'] = 'Page have been moved'
        result['response'] = confluence_response
    except Exception as e:
        module.exit_json(changed=False, msg='Something went wrong deleting content', exception=str(e))


    module.exit_json(**result)

def _add_labels(space_key, title,  labels):

    result = dict(changed=False)
    space_has_page = _page_exists(space_key, title)
    added_labels = False

    if not space_has_page:
        result['msg'] = "Page does not exist so no labels were added"
        return added_labels
    
    page_id = _get_page_id(space_key, title)

    for l in labels:
        try:
            confluence_module.set_page_label(page_id, l)
            added_labels = True
        except:
            pass

    return added_labels
    

def _handle_add_labels(module, space_key, title,  labels):

    result = dict(changed=False)
    space_has_page = _page_exists(space_key, title)

    if not space_has_page:
        result['msg'] = "Page does not exist so no labels were added"
        module.exit_json(**result)
    
    page_id = _get_page_id(space_key, title)

    for l in labels:
        try:
            confluence_module.set_page_label(page_id, l)
        except Exception as e:
            module.exit_json(changed=False, msg='Something went wrong deleting content', exception=str(e))
    
    result['changed'] = True
    result['msg'] = 'Labels were added'

    module.exit_json(**result)

def _check_if_label_exists(page_id, label):
    confluence_response = None
    try:
        confluence_response = confluence_module.get_page_labels(page_id)
    except Exception as e:
        pass

    labels_arr = confluence_response['results']
    found = False

    for l_obj in labels_arr:
        l = l_obj['name']
        
        if l == label:
            found = True
            break
    
    return found


def _handle_remove_labels(module, space_key, title,  labels):

    result = dict(changed=False)
    space_has_page = _page_exists(space_key, title)
    list_of_labels_removed = []

    if not space_has_page:
        result['msg'] = "Page does not exist so no labels were added"
        module.exit_json(**result)
    
    page_id = _get_page_id(space_key, title)

    for l in labels:
        if _check_if_label_exists(page_id, l):
            try:
                confluence_module.remove_page_label(page_id, l)
                list_of_labels_removed.append(l)
            except Exception as e:
                module.exit_json(changed=False, msg='Something went wrong deleting content', exception=str(e))
    
    if len(list_of_labels_removed) > 0:
        result['changed'] = True
        result['msg'] = 'Labels were removed'
        result['response'] = list_of_labels_removed
    else:
        result['msg'] = 'No labels were removed'

    module.exit_json(**result)

def _handle_append_page(module, space_key, title, body, parent_page_title):
    #Seed module return
    result = dict(changed=False)

    space_has_page = _page_exists(space_key, title)
    confluence_response = None
    page_id = _get_page_id(space_key, title)
    parent_id = None

    if parent_page_title:
        parent_id = _get_page_id(space_key, parent_page_title)
         
    # If page doesn't exist create it
    if space_has_page:
        try:
            confluence_response = confluence_module.append_page(page_id, title=title, append_body=body, parent_id=parent_id, type="page", representation="wiki", minor_edit=False)
            result['changed'] = True
            result['msg'] = 'Page have been appended'
            result['response'] = confluence_response
        except Exception as e:
            module.exit_json(changed=False, msg='Something went wrong deleting content', exception=str(e))

    if confluence_response is not None:
        module.exit_json(**result)
    else:
        module.fail_json(changed=False, msg=f'Something went wrong creating or updating the page')

def _handle_prepend_page(module, space_key, title, body, parent_page_title):
    #Seed module return
    result = dict(changed=False)

    space_has_page = _page_exists(space_key, title)
    confluence_response = None
    page_id = _get_page_id(space_key, title)
    parent_id = None

    if parent_page_title:
        parent_id = _get_page_id(space_key, parent_page_title)
         
    # If page doesn't exist create it
    if space_has_page:
        try:
            confluence_response = confluence_module.prepend_page(page_id, title=title, prepend_body=body, parent_id=parent_id, type="page", representation="wiki", minor_edit=False)
            result['changed'] = True
            result['msg'] = 'Page have been prepended'
            result['response'] = confluence_response
        except Exception as e:
            module.exit_json(changed=False, msg='Something went wrong deleting content', exception=str(e))

    if confluence_response is not None:
        module.exit_json(**result)
    else:
        module.fail_json(changed=False, msg=f'Something went wrong creating or updating the page')

def _handle_get_page(module, space, title):
    result = dict(changed=False)

    space_has_page = _page_exists(space, title)
    
    if not space_has_page:
        result['msg'] = 'Page not found'
        module.exit_json(**result)
    
    try:
        confluence_response = confluence_module.get_page_by_title(space, title)
        result['response'] = confluence_response
    except Exception as e:
        module.exit_json(changed=False, msg='Something went wrong deleting content', exception=str(e))

    module.exit_json(**result)

def _handle_get_page_cql(module, cql, start=0, limit=None, expand=None, include_archived_spaces=None, excerpt=None):
    result = dict(changed=False)
    
    try:
        confluence_response = confluence_module.cql(cql, start=0, limit=None, expand=None, include_archived_spaces=None, excerpt=None)
        result['response'] = confluence_response
    except Exception as e:
        module.exit_json(changed=False, msg='Something went wrong deleting content', exception=str(e))

    module.exit_json(**result)


def run_module():
    module_args = dict(
        url=dict(type='str'),
        username=dict(type='str'),
        password=dict(type='str', no_log=True),
        state=dict(type='str', choices=('present', 'absent', 'move', 'add_labels', 'remove_labels', 'append_page', 'prepend_page', 'page', 'cql')),
        space_key=dict(type='str'),
        title=dict(type='str'),
        body=dict(type='str'),
        parent_page_title=dict(type='str'),
        recursive=dict(type='str'),
        overwrite=dict(type='bool', default=False),
        labels=dict(type='list'),
        cql=dict(type='str')
    )

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
    parent_page_title = params['parent_page_title']
    recursive = params['recursive']
    overwrite = params['overwrite']
    labels = params['labels']
    cql = params['cql']

    create_confluence_instance(url, username, password)
        
    if state in ['present']:
        _handle_present(module, space_key, title, body, overwrite, labels, parent_page_title)
    elif state in ['absent']:
        _handle_absent(module, space_key, title, recursive)
    elif state in ['move']:
        _handle_move(module, space_key, parent_page_title, title)
    elif state in ['add_labels']:
        _handle_add_labels(module, space_key, title, labels)
    elif state in ['remove_labels']:
        _handle_remove_labels(module, space_key, title, labels)
    elif state in ['append_page']:
        _handle_append_page(module, space_key, title, body, parent_page_title)
    elif state in ['prepend_page']:
        _handle_prepend_page(module, space_key, title, body, parent_page_title)
    elif state in ['page']:
        _handle_get_page(module, space_key, title)
    elif state in ['cql']:
        _handle_get_page_cql(module, cql, start=0, limit=None, expand=None, include_archived_spaces=None, excerpt=None)
    

def main():
    run_module()


if __name__ == '__main__':
    main()
