#!/usr/bin/env python

"""
Copyright (c) 2018 Keitaro AB

Use of this source code is governed by an MIT license
that can be found in the LICENSE file or at
https://opensource.org/licenses/MIT.
"""

"""
Executable module for checking github version updates for repositories from repositories.txt
and alerting the slack channel in case of new unrecorded one
"""

import urllib.request
import json
import os
import etcd3


def check_version(repositories):
    """
    For list of repositories, check their versions and recorded ones
    :param repositories:
    :return:
    """
    for repository in repositories:
        # user/repository
        name_path = get_name_path(repository)

        # github api url for requesting tag list
        url = get_api_url(name_path)

        # get the tag list
        tags = get_tags(url)

        check_records(name_path, tags[0])


def get_repositories():
    """
    Parse repository list from file
    :return:
    """
    repositories = []
    with open('/app/repositories.txt', 'r') as file:
        content = file.readlines()
        repositories = [row.strip() for row in content if row.strip()[0] != '#']

    return repositories


def alert_slack(repository, new_version):
    """
    Alerts the slack channel with formatting and content of message
    :param repository:
    :param new_version:
    :param slack_hook:
    :return:
    """

    slack_hook = os.environ.get('SLACK_HOOK')
    slack_channel = os.environ.get('SLACK_CHANNEL', '#random')

    request_dict = dict()
    request_dict['attachments'] = []

    attachment = dict()
    attachment['fallback'] = "New version ({}) found for {}!".format(new_version, repository)
    attachment['color'] = '#4286f4'
    attachment['title'] = "New version found for {}!".format(repository)
    attachment['fields'] = [
        {
            'title': "Repository: _*{}*_".format(repository),
            'value': "New version: `{}`".format(new_version)
        },
        {
            'value': "Url: https://github.com/{}/releases/tag/{}".format(repository, new_version)
        }
    ]

    request_dict['attachments'].append(attachment)

    request_dict['channel'] = slack_channel
    request_dict['link_names'] = 1
    request_dict['username'] = 'version-check-bot'
    request_dict['icon_emoji'] = ':arrow_up:'

    # convert dict to json, and encode it with utf-8
    request_data = json.dumps(request_dict).encode('utf-8')

    request = urllib.request.Request(slack_hook, request_data, {'Content-type': 'application/json'}, method="POST")
    response = urllib.request.urlopen(request)
    # TODO: parse response
    return response


def get_tags(url):
    """
    Function for obtaining tags from url
    :param url:
    :return tags:
    """

    reader = urllib.request.urlopen(url)
    json_raw = reader.read()
    reader.close()

    json_parsed = json.loads(json_raw)

    tags = []

    for tag_object in json_parsed:
        tag = tag_object['ref'].split('/')[-1]
        # skip beta and alpha tags, and the minio bad first old tag
        if 'beta' not in tag and 'alpha' not in tag and 'release-1434511043' not in tag:
            tags.append(tag)

    return sorted(tags, reverse=True)


def get_name_path(url):
    """
    Function for getting the repository name from given github url
    :param url:
    :return:
    """

    # remove trailing slash
    if url[-1] == '/':
        url = url[:-1]

    url_split = url.split('/')

    if len(url_split) > 2:
        return url_split[-1] + '/' + url_split[-2]

    # if only user/repo is given instead of full url
    return url


def get_api_url(for_repository):
    """
    Get the api url for GET request to obtain tags
    :param for_repository:
    :return:
    """
    api_url = 'https://api.github.com/repos/{}/git/refs/tags'.format(for_repository)
    return api_url


def etcd_client():
    """
    Creates an etcd client instance with connection
    :return: returns an etcd client instance
    """

    host = os.environ.get('ETCD_HOST')
    port = os.environ.get('ETCD_PORT')

    etcd = etcd3.client(host=host, port=port)
    return etcd


def check_records(repository, version):
    """
    Checks if there is a record for the repository with that version,
    if not, sends an alert
    :param repository:
    :param version:
    :return:
    """

    etcd = etcd_client()
    records = [(x[1].key.decode('utf-8'), x[0].decode('utf-8')) for x in etcd.get_prefix('/version-check')]

    etcd_key_path = '/version-check/{}'.format(repository)

    # get recorded version
    recorded_version_bytes = etcd.get(etcd_key_path)[0]

    # if none found, send alert and update records
    if recorded_version_bytes is None:
        alert_slack(repository, version)
        etcd.put(etcd_key_path, version)
        return True

    # decode the bytes
    recorded_version = recorded_version_bytes.decode('utf-8')

    # if the recorded version is different, update and send alert
    if recorded_version != version:
        alert_slack(repository, version)
        etcd.put(etcd_key_path, version)
        return True

    return False


if __name__ == '__main__':
    check_version(get_repositories())



