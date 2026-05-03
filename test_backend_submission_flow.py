#!/usr/bin/env python3
import json
import os
import sys
import unittest
from unittest.mock import Mock, patch


BACKEND_DIR = os.path.join(os.path.dirname(__file__), 'backend')
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import db  # noqa: E402
import handler  # noqa: E402
from routes import admin, public, submit  # noqa: E402


class TestBackendSubmissionFlow(unittest.TestCase):
    def test_get_queue_queries_pending_status(self):
        jinja_env = Mock()
        template = Mock()
        template.render.return_value = '<div>queue</div>'
        jinja_env.get_template.return_value = template

        with patch.object(admin, '_admin_check', return_value=({'email': 'admin@dctech.events'}, None)), \
             patch.object(admin, 'get_drafts_by_status', return_value=[] ) as get_drafts_by_status:
            response = admin.get_queue({}, jinja_env)

        get_drafts_by_status.assert_called_once_with('pending')
        self.assertEqual(response['statusCode'], 200)
        self.assertEqual(response['body'], '<div>queue</div>')

    def test_update_draft_status_normalizes_status(self):
        table = Mock()

        with patch.object(db, '_get_table', return_value=table):
            db.update_draft_status('abc12345', 'APPROVED', 'admin@dctech.events')

        table.update_item.assert_called_once()
        kwargs = table.update_item.call_args.kwargs
        self.assertEqual(kwargs['ExpressionAttributeValues'][':status'], 'approved')
        self.assertEqual(kwargs['ExpressionAttributeValues'][':gsi1pk'], 'STATUS#approved')

    def test_create_draft_stores_pending_status_lowercase(self):
        table = Mock()

        with patch.object(db, '_get_table', return_value=table), \
             patch('db.uuid.uuid4') as mock_uuid, \
             patch('db.time.strftime', return_value='2026-04-18T00:00:00Z'):
            mock_uuid.return_value = '12345678-aaaa-bbbb-cccc-1234567890ab'
            draft_id = db.create_draft('event', {'title': 'Test'}, 'user@example.com', 'user-123')

        self.assertEqual(draft_id, '12345678')
        table.put_item.assert_called_once()
        item = table.put_item.call_args.kwargs['Item']
        self.assertEqual(item['status'], 'pending')
        self.assertEqual(item['GSI1PK'], 'STATUS#pending')

    def test_get_categories_returns_json(self):
        with patch.object(public, 'get_all_categories', return_value={'ai': {'slug': 'ai', 'name': 'AI'}}):
            response = public.get_categories({}, None)

        self.assertEqual(response['statusCode'], 200)
        self.assertEqual(response['headers']['Content-Type'], 'application/json')
        self.assertEqual(json.loads(response['body']), {'ai': {'slug': 'ai', 'name': 'AI'}})

    def test_handler_routes_api_categories(self):
        with patch.object(handler.public, 'get_categories', return_value={'statusCode': 200, 'headers': {}, 'body': '{}'}) as get_categories:
            response = handler.lambda_handler({'httpMethod': 'GET', 'path': '/api/categories', 'headers': {}}, None)

        get_categories.assert_called_once()
        self.assertEqual(response['statusCode'], 200)
        self.assertEqual(response['body'], '{}')

    def test_get_approve_form_renders_category_labels(self):
        event = {
            'headers': {},
            'requestContext': {
                'authorizer': {
                    'claims': {
                        'sub': 'admin-user',
                        'email': 'admin@dctech.events',
                        'cognito:groups': ['admins'],
                    }
                }
            }
        }

        with patch.object(admin, 'db_get_draft', return_value={
            'id': 'draft1234',
            'title': 'Refraction AI Exchange',
            'submitter_email': 'mary@refraction.one',
            'categories': ['ai'],
        }), patch.object(admin, 'get_all_categories', return_value={
            'ai': {'slug': 'ai', 'name': 'AI & Machine Learning'},
            'cloud': {'slug': 'cloud', 'name': 'Cloud Computing'},
        }):
            response = admin.get_approve_form(event, handler.jinja_env, 'draft1234')

        self.assertEqual(response['statusCode'], 200)
        self.assertIn('AI &amp; Machine Learning', response['body'])
        self.assertIn('Cloud Computing', response['body'])
        self.assertIn('value="ai"', response['body'])
        self.assertIn('checked', response['body'])

    def test_submit_event_json_accepts_form_encoded_submission(self):
        event = {
            'headers': {
                'Content-Type': 'application/x-www-form-urlencoded',
                'origin': 'https://dctech.events',
            },
            'body': 'type=event&title=Test+Event&date=2026-05-01&url=https%3A%2F%2Fexample.com&city=Washington&state=DC&categories=ai&categories=cloud',
        }

        with patch.object(submit, 'get_user_from_event', return_value=({'email': 'user@example.com', 'sub': 'user-123'}, None)), \
             patch.object(submit, 'create_draft', return_value='draft1234') as create_draft:
            response = submit.submit_event_json(event, handler.jinja_env)

        self.assertEqual(response['statusCode'], 201)
        self.assertEqual(json.loads(response['body']), {'draft_id': 'draft1234', 'draft_type': 'event'})
        create_draft.assert_called_once_with('event', {
            'title': 'Test Event',
            'date': '2026-05-01',
            'time': None,
            'url': 'https://example.com',
            'city': 'Washington',
            'state': 'DC',
            'cost': '',
            'end_date': '',
            'all_day': False,
            'description': '',
            'location': '',
            'categories': ['ai', 'cloud'],
            'site': 'dctech',
        }, 'user@example.com', 'user-123')

    def test_my_submissions_json_returns_drafts(self):
        event = {
            'headers': {
                'origin': 'https://dctech.events',
            },
        }

        with patch.object(submit, 'get_user_from_event', return_value=({'email': 'user@example.com', 'sub': 'user-123'}, None)), \
             patch.object(submit, 'get_drafts_by_submitter', return_value=[{'id': 'draft1234', 'status': 'pending'}]) as get_drafts:
            response = submit.my_submissions_json(event, handler.jinja_env)

        self.assertEqual(response['statusCode'], 200)
        self.assertEqual(json.loads(response['body']), {'submissions': [{'id': 'draft1234', 'status': 'pending'}]})
        get_drafts.assert_called_once_with('user-123')

    def test_get_queue_json_queries_pending_status(self):
        with patch.object(admin, '_admin_check', return_value=({'email': 'admin@dctech.events'}, None)), \
             patch.object(admin, 'get_drafts_by_status', return_value=[{'id': 'draft1234'}]) as get_drafts_by_status:
            response = admin.get_queue_json({}, handler.jinja_env)

        self.assertEqual(response['statusCode'], 200)
        self.assertEqual(json.loads(response['body']), {'drafts': [{'id': 'draft1234'}]})
        get_drafts_by_status.assert_called_once_with('pending')

    def test_handler_routes_api_my_submissions(self):
        with patch.object(handler.submit, 'my_submissions_json', return_value={'statusCode': 200, 'headers': {}, 'body': '{"submissions": []}'}) as my_submissions_json:
            response = handler.lambda_handler({'httpMethod': 'GET', 'path': '/api/my-submissions', 'headers': {}}, None)

        my_submissions_json.assert_called_once()
        self.assertEqual(response['statusCode'], 200)
        self.assertEqual(response['body'], '{"submissions": []}')


if __name__ == '__main__':
    unittest.main()
