# Copyright (c) 2013 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import json
from urllib import urlencode

from storyboard.db.api import tasks
from storyboard.tests import base


class TestStories(base.FunctionalTest):
    def setUp(self):
        super(TestStories, self).setUp()
        self.resource = '/stories'

        self.story_01 = {
            'title': 'StoryBoard',
            'description': 'Awesome Task Tracker'
        }
        self.default_headers['Authorization'] = 'Bearer valid_superuser_token'

    def test_stories_endpoint(self):
        response = self.get_json(self.resource)
        self.assertEqual(5, len(response))

    def test_create(self):
        response = self.post_json(self.resource, self.story_01)
        story = json.loads(response.body)

        url = "%s/%d" % (self.resource, story['id'])
        story = self.get_json(url)

        self.assertIn('id', story)
        self.assertIn('created_at', story)
        self.assertEqual(story['title'], self.story_01['title'])
        self.assertEqual(story['description'], self.story_01['description'])

    def test_update(self):
        response = self.post_json(self.resource, self.story_01)
        original = json.loads(response.body)

        delta = {
            'id': original['id'],
            'title': 'new title',
            'description': 'new description'
        }

        url = "/stories/%d" % original['id']
        response = self.put_json(url, delta)
        updated = json.loads(response.body)

        self.assertEqual(updated['id'], original['id'])

        self.assertNotEqual(updated['title'], original['title'])
        self.assertNotEqual(updated['description'],
                            original['description'])


class TestStorySearch(base.FunctionalTest):
    def setUp(self):
        super(TestStorySearch, self).setUp()

    def build_search_url(self, params=None, raw=''):
        if params:
            raw = urlencode(params)
        return '/stories?%s' % raw

    def test_search(self):
        url = self.build_search_url({
        })

        results = self.get_json(url, expect_errors=True)
        self.assertEqual(5, len(results.json))
        self.assertEqual('5', results.headers['X-Total'])
        self.assertFalse('X-Marker' in results.headers)

    def test_search_by_title(self):
        url = self.build_search_url({
            'title': 'foo'
        })

        results = self.get_json(url, expect_errors=True)
        self.assertEqual(2, len(results.json))
        self.assertEqual('2', results.headers['X-Total'])
        self.assertFalse('X-Marker' in results.headers)

        result = results.json[0]
        self.assertEqual(1, result['id'])
        result = results.json[1]
        self.assertEqual(3, result['id'])

    def test_search_by_description(self):
        url = self.build_search_url({
            'description': 'foo'
        })

        results = self.get_json(url, expect_errors=True)
        self.assertEqual(2, len(results.json))
        self.assertEqual('2', results.headers['X-Total'])
        self.assertFalse('X-Marker' in results.headers)

        result = results.json[0]
        self.assertEqual(1, result['id'])
        result = results.json[1]
        self.assertEqual(3, result['id'])

    def test_search_by_status(self):
        url = self.build_search_url({
            'status': 'active'
        })

        results = self.get_json(url, expect_errors=True)
        self.assertEqual(1, len(results.json))
        self.assertEqual('1', results.headers['X-Total'])
        self.assertFalse('X-Marker' in results.headers)

        result = results.json[0]
        self.assertEqual(1, result['id'])

    def test_search_by_statuses(self):
        url = self.build_search_url(raw='status=active&status=merged')

        results = self.get_json(url, expect_errors=True)
        self.assertEqual(2, len(results.json))
        self.assertEqual('2', results.headers['X-Total'])
        self.assertFalse('X-Marker' in results.headers)

        result = results.json[0]
        self.assertEqual(1, result['id'])
        result = results.json[1]
        self.assertEqual(2, result['id'])

    def test_search_by_assignee_id(self):
        url = self.build_search_url({
            'assignee_id': 1
        })

        results = self.get_json(url, expect_errors=True)
        self.assertEqual(2, len(results.json))
        self.assertEqual('2', results.headers['X-Total'])
        self.assertFalse('X-Marker' in results.headers)

        result = results.json[0]
        self.assertEqual(1, result['id'])
        result = results.json[1]
        self.assertEqual(2, result['id'])

    def test_search_by_project_group_id(self):
        url = self.build_search_url({
            'project_group_id': 2
        })

        results = self.get_json(url, expect_errors=True)
        self.assertEqual(2, len(results.json))
        self.assertEqual('2', results.headers['X-Total'])
        self.assertFalse('X-Marker' in results.headers)

        result = results.json[0]
        self.assertEqual(1, result['id'])
        result = results.json[1]
        self.assertEqual(2, result['id'])

    def test_search_by_project_id(self):
        url = self.build_search_url({
            'project_id': 1
        })

        results = self.get_json(url, expect_errors=True)
        self.assertEqual(1, len(results.json))
        self.assertEqual('1', results.headers['X-Total'])
        self.assertFalse('X-Marker' in results.headers)

        result = results.json[0]
        self.assertEqual(1, result['id'])

    def test_search_empty_results(self):
        url = self.build_search_url({
            'title': 'grumpycat'
        })

        results = self.get_json(url, expect_errors=True)
        self.assertEqual(0, len(results.json))
        self.assertEqual('0', results.headers['X-Total'])
        self.assertFalse('X-Marker' in results.headers)

    def test_search_limit(self):
        url = self.build_search_url({
            'title': 'foo',
            'limit': 1
        })

        results = self.get_json(url, expect_errors=True)
        self.assertEqual(1, len(results.json))
        self.assertEqual('2', results.headers['X-Total'])
        self.assertEqual('1', results.headers['X-Limit'])
        self.assertFalse('X-Marker' in results.headers)

        result = results.json[0]
        self.assertEqual(1, result['id'])

    def test_search_marker(self):
        url = self.build_search_url({
            'title': 'foo',
            'marker': 1  # Last item in previous list.
        })

        results = self.get_json(url, expect_errors=True)
        self.assertEqual(1, len(results.json))
        self.assertEqual('2', results.headers['X-Total'])
        self.assertEqual('1', results.headers['X-Marker'])

        result = results.json[0]
        self.assertEqual(3, result['id'])

    def test_search_direction(self):
        url = self.build_search_url({
            'sort_field': 'title',
            'sort_dir': 'asc'
        })

        results = self.get_json(url, expect_errors=True)
        self.assertEqual(5, len(results.json))
        self.assertEqual('5', results.headers['X-Total'])
        self.assertFalse('X-Marker' in results.headers)

        result = results.json[0]
        self.assertEqual(5, result['id'])
        result = results.json[1]
        self.assertEqual(4, result['id'])
        result = results.json[2]
        self.assertEqual(3, result['id'])
        result = results.json[3]
        self.assertEqual(2, result['id'])
        result = results.json[4]
        self.assertEqual(1, result['id'])

    def test_search_direction_desc(self):
        url = self.build_search_url({
            'sort_field': 'title',
            'sort_dir': 'desc'
        })

        results = self.get_json(url, expect_errors=True)
        self.assertEqual(5, len(results.json))
        self.assertEqual('5', results.headers['X-Total'])
        self.assertFalse('X-Marker' in results.headers)

        result = results.json[0]
        self.assertEqual(1, result['id'])
        result = results.json[1]
        self.assertEqual(2, result['id'])
        result = results.json[2]
        self.assertEqual(3, result['id'])
        result = results.json[3]
        self.assertEqual(4, result['id'])
        result = results.json[4]
        self.assertEqual(5, result['id'])

    def test_filter_paged_status(self):
        url = self.build_search_url({
            'limit': '2',
            'sort_field': 'id',
            'status': 'invalid'
        })

        results = self.get_json(url)
        self.assertEqual(2, len(results))
        result = results[0]
        self.assertEqual(3, result['id'])
        result = results[1]
        self.assertEqual(4, result['id'])


class TestStoryStatuses(base.FunctionalTest):
    def setUp(self):
        super(TestStoryStatuses, self).setUp()
        self.resource = '/stories'
        self.individual_resource = '/stories/1'

        self.default_headers['Authorization'] = 'Bearer valid_superuser_token'
        self.task_statuses = tasks.task_get_statuses().keys()

    # check if all stories are returning all statuses
    def test_stories_statuses(self):
        response = self.get_json(self.resource)

        all_statuses = True
        for story in response:
            current_statuses = story.get('task_statuses', [])
            final_statuses = []
            for status in current_statuses:
                final_statuses.append(status['key'])
            if set(final_statuses) != set(self.task_statuses):
                all_statuses = False
                break
        self.assertTrue(all_statuses)

    # verify that the returned count is real
    def test_story_count(self):
        response = self.get_json(self.individual_resource)
        task_statuses = response.get('task_statuses', [])
        all_tasks = tasks.task_get_all(story_id=response.get('id', None))

        # get count of all statuses
        statuses_count = {}
        for task in all_tasks:
            current_status = task.status
            status_count = statuses_count.get(current_status, 0)
            statuses_count[current_status] = status_count + 1

        count_matches = True
        for status in task_statuses:
            status_count = statuses_count.get(status['key'], 0)
            if status_count != status['count']:
                count_matches = False
                break
        self.assertTrue(count_matches)
