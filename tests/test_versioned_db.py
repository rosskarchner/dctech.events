"""
Tests for versioned_db.py — wiki-style change tracking layer.

Uses moto to mock DynamoDB locally.
"""

import os
import time
import unittest
from unittest.mock import patch
from decimal import Decimal

import boto3
from moto import mock_aws

# Set env before importing module under test
os.environ['CONFIG_TABLE_NAME'] = 'test-dctech-events'
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
os.environ['AWS_SECURITY_TOKEN'] = 'testing'
os.environ['AWS_SESSION_TOKEN'] = 'testing'

import versioned_db


def _create_test_table():
    """Create the DynamoDB table used by versioned_db in the moto mock."""
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.create_table(
        TableName='test-dctech-events',
        KeySchema=[
            {'AttributeName': 'PK', 'KeyType': 'HASH'},
            {'AttributeName': 'SK', 'KeyType': 'RANGE'},
        ],
        AttributeDefinitions=[
            {'AttributeName': 'PK', 'AttributeType': 'S'},
            {'AttributeName': 'SK', 'AttributeType': 'S'},
        ],
        BillingMode='PAY_PER_REQUEST',
    )
    table.wait_until_exists()
    return table


@mock_aws
class TestVersionedPut(unittest.TestCase):
    def setUp(self):
        versioned_db.reset_clients()
        self.table = _create_test_table()

    def test_first_put_creates_item_no_history(self):
        """First write to a new PK should not create a history entry."""
        versioned_db.versioned_put(
            pk='EVENT#aaa',
            item={'title': 'Test Event', 'date': '2026-03-01'},
            editor='admin@test.com',
            reason='Initial creation',
        )

        # Item should exist
        resp = self.table.get_item(Key={'PK': 'EVENT#aaa', 'SK': 'META'})
        item = resp['Item']
        self.assertEqual(item['title'], 'Test Event')
        self.assertEqual(item['date'], '2026-03-01')

        # No history entries
        history = versioned_db.get_history('EVENT#aaa')
        self.assertEqual(len(history), 0)

    def test_second_put_creates_history_entry(self):
        """Updating an existing item should snapshot the previous state."""
        # First write
        versioned_db.versioned_put(
            pk='EVENT#bbb',
            item={'title': 'Original Title', 'date': '2026-03-01'},
            editor='admin@test.com',
            reason='Initial',
        )

        # Second write (update)
        versioned_db.versioned_put(
            pk='EVENT#bbb',
            item={'title': 'Updated Title', 'date': '2026-03-01'},
            editor='editor@test.com',
            reason='Fixed title',
        )

        # Current item should have new title
        resp = self.table.get_item(Key={'PK': 'EVENT#bbb', 'SK': 'META'})
        self.assertEqual(resp['Item']['title'], 'Updated Title')

        # Should have 1 history entry with old state
        history = versioned_db.get_history('EVENT#bbb')
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['snapshot']['title'], 'Original Title')
        self.assertEqual(history[0]['editor'], 'editor@test.com')
        self.assertEqual(history[0]['reason'], 'Fixed title')

    def test_multiple_updates_create_ordered_history(self):
        """Multiple updates should create ordered history entries."""
        versioned_db.versioned_put(
            pk='EVENT#ccc',
            item={'title': 'V1'},
            editor='a@test.com',
            reason='v1',
        )
        time.sleep(0.01)  # Ensure distinct timestamps

        versioned_db.versioned_put(
            pk='EVENT#ccc',
            item={'title': 'V2'},
            editor='b@test.com',
            reason='v2',
        )
        time.sleep(0.01)

        versioned_db.versioned_put(
            pk='EVENT#ccc',
            item={'title': 'V3'},
            editor='c@test.com',
            reason='v3',
        )

        history = versioned_db.get_history('EVENT#ccc')
        self.assertEqual(len(history), 2)
        # Newest first
        self.assertEqual(history[0]['snapshot']['title'], 'V2')
        self.assertEqual(history[1]['snapshot']['title'], 'V1')

    def test_put_with_ttl(self):
        """History entry should include TTL when specified."""
        versioned_db.versioned_put(
            pk='EVENT#ddd',
            item={'title': 'First'},
            editor='a@test.com',
            reason='init',
        )
        versioned_db.versioned_put(
            pk='EVENT#ddd',
            item={'title': 'Second'},
            editor='a@test.com',
            reason='update',
            ttl=1700000000,
        )

        history = versioned_db.get_history('EVENT#ddd')
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['ttl'], 1700000000)

    def test_put_preserves_pk_sk_on_item(self):
        """PK and SK should be set automatically on the written item."""
        versioned_db.versioned_put(
            pk='GROUP#test-group',
            item={'name': 'Test Group', 'active': True},
            editor='admin@test.com',
            reason='Created group',
        )

        resp = self.table.get_item(Key={'PK': 'GROUP#test-group', 'SK': 'META'})
        item = resp['Item']
        self.assertEqual(item['PK'], 'GROUP#test-group')
        self.assertEqual(item['SK'], 'META')
        self.assertEqual(item['name'], 'Test Group')


@mock_aws
class TestVersionedDelete(unittest.TestCase):
    def setUp(self):
        versioned_db.reset_clients()
        self.table = _create_test_table()

    def test_delete_existing_item(self):
        """Deleting an existing item should soft-delete and create history."""
        # Create item
        versioned_db.versioned_put(
            pk='EVENT#del1',
            item={'title': 'To Delete', 'date': '2026-04-01'},
            editor='admin@test.com',
            reason='Created',
        )

        # Delete it
        versioned_db.versioned_delete(
            pk='EVENT#del1',
            editor='admin@test.com',
            reason='No longer needed',
        )

        # Item should be soft-deleted
        resp = self.table.get_item(Key={'PK': 'EVENT#del1', 'SK': 'META'})
        item = resp['Item']
        self.assertEqual(item['status'], 'DELETED')
        self.assertEqual(item['deleted_by'], 'admin@test.com')
        self.assertIn('deleted_at', item)

        # Should have history entry with previous state
        history = versioned_db.get_history('EVENT#del1')
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['snapshot']['title'], 'To Delete')

    def test_delete_nonexistent_item_is_noop(self):
        """Deleting a nonexistent item should do nothing."""
        versioned_db.versioned_delete(
            pk='EVENT#nonexistent',
            editor='admin@test.com',
            reason='Cleanup',
        )
        # No error raised, no items created
        resp = self.table.get_item(Key={'PK': 'EVENT#nonexistent', 'SK': 'META'})
        self.assertNotIn('Item', resp)


@mock_aws
class TestGetHistory(unittest.TestCase):
    def setUp(self):
        versioned_db.reset_clients()
        self.table = _create_test_table()

    def test_empty_history(self):
        """Entity with no updates should return empty history."""
        history = versioned_db.get_history('EVENT#nohistory')
        self.assertEqual(history, [])

    def test_history_respects_limit(self):
        """get_history should respect the limit parameter."""
        # Create item and update it 5 times
        versioned_db.versioned_put(
            pk='EVENT#lim',
            item={'title': 'V0'},
            editor='a@test.com',
            reason='init',
        )
        for i in range(1, 6):
            time.sleep(0.01)
            versioned_db.versioned_put(
                pk='EVENT#lim',
                item={'title': f'V{i}'},
                editor='a@test.com',
                reason=f'update {i}',
            )

        # Should have 5 history entries total
        all_history = versioned_db.get_history('EVENT#lim')
        self.assertEqual(len(all_history), 5)

        # Limit to 2
        limited = versioned_db.get_history('EVENT#lim', limit=2)
        self.assertEqual(len(limited), 2)
        # Should be the 2 newest
        self.assertEqual(limited[0]['snapshot']['title'], 'V4')
        self.assertEqual(limited[1]['snapshot']['title'], 'V3')


@mock_aws
class TestRollback(unittest.TestCase):
    def setUp(self):
        versioned_db.reset_clients()
        self.table = _create_test_table()

    def test_rollback_restores_previous_version(self):
        """Rolling back should restore the snapshot from a history entry."""
        # Create and update
        versioned_db.versioned_put(
            pk='EVENT#rb1',
            item={'title': 'Original', 'date': '2026-05-01'},
            editor='admin@test.com',
            reason='Created',
        )
        time.sleep(0.01)
        versioned_db.versioned_put(
            pk='EVENT#rb1',
            item={'title': 'Changed', 'date': '2026-05-01'},
            editor='editor@test.com',
            reason='Updated title',
        )

        # Get the history entry timestamp
        history = versioned_db.get_history('EVENT#rb1')
        self.assertEqual(len(history), 1)
        version_ts = history[0]['timestamp']

        # Rollback
        versioned_db.rollback(
            pk='EVENT#rb1',
            version_ts=version_ts,
            editor='admin@test.com',
        )

        # Current item should have original title
        resp = self.table.get_item(Key={'PK': 'EVENT#rb1', 'SK': 'META'})
        self.assertEqual(resp['Item']['title'], 'Original')

        # Should now have 2 history entries (the original change + the rollback)
        history_after = versioned_db.get_history('EVENT#rb1')
        self.assertEqual(len(history_after), 2)
        # Newest should be the rollback (snapshot of 'Changed')
        self.assertEqual(history_after[0]['snapshot']['title'], 'Changed')
        self.assertIn('Rollback', history_after[0]['reason'])

    def test_rollback_nonexistent_version_raises(self):
        """Rolling back to a nonexistent version should raise ValueError."""
        versioned_db.versioned_put(
            pk='EVENT#rb2',
            item={'title': 'Test'},
            editor='admin@test.com',
            reason='Created',
        )

        with self.assertRaises(ValueError):
            versioned_db.rollback(
                pk='EVENT#rb2',
                version_ts='2020-01-01T00:00:00.000000Z',
                editor='admin@test.com',
            )

    def test_rollback_after_delete(self):
        """Rolling back a soft-deleted item should restore it."""
        versioned_db.versioned_put(
            pk='EVENT#rb3',
            item={'title': 'Alive', 'date': '2026-06-01'},
            editor='admin@test.com',
            reason='Created',
        )
        time.sleep(0.01)
        versioned_db.versioned_delete(
            pk='EVENT#rb3',
            editor='admin@test.com',
            reason='Deleted',
        )

        # Get version before delete
        history = versioned_db.get_history('EVENT#rb3')
        version_ts = history[0]['timestamp']

        # Rollback the deletion
        versioned_db.rollback(
            pk='EVENT#rb3',
            version_ts=version_ts,
            editor='admin@test.com',
        )

        # Item should be restored
        resp = self.table.get_item(Key={'PK': 'EVENT#rb3', 'SK': 'META'})
        item = resp['Item']
        self.assertEqual(item['title'], 'Alive')
        self.assertNotIn('status', item)  # DELETED status gone


if __name__ == '__main__':
    unittest.main()
