"""
DynamoDB operations for DC Tech Events
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import boto3
from boto3.dynamodb.conditions import Key, Attr
from decimal import Decimal


class EventsDatabase:
    """DynamoDB interface for events table"""

    def __init__(self, table_name: str, region: str = 'us-east-1'):
        """
        Initialize DynamoDB client

        Args:
            table_name: Name of the DynamoDB events table
            region: AWS region
        """
        self.table_name = table_name
        self.region = region
        self.dynamodb = boto3.resource('dynamodb', region_name=region)
        self.table = self.dynamodb.Table(table_name)

    def _deserialize_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Convert DynamoDB Decimal types to native Python types"""
        for key, value in item.items():
            if isinstance(value, Decimal):
                item[key] = int(value) if value % 1 == 0 else float(value)
            elif isinstance(value, dict):
                item[key] = self._deserialize_item(value)
            elif isinstance(value, list):
                item[key] = [
                    self._deserialize_item(v) if isinstance(v, dict) else v
                    for v in value
                ]
        return item

    def get_events_by_state(
        self,
        state: str,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """
        Get events by state and date range using DateIndex GSI

        Args:
            state: State code (DC, MD, VA, or ALL for all states)
            start_date: Start date in ISO format (YYYY-MM-DD)
            end_date: End date in ISO format (YYYY-MM-DD)

        Returns:
            List of event dictionaries
        """
        try:
            response = self.table.query(
                IndexName='DateIndex',
                KeyConditionExpression=Key('state').eq(state) &
                                       Key('start_datetime').between(start_date, end_date),
                FilterExpression=Attr('ttl').gte(int(datetime.now().timestamp()))
            )

            events = response.get('Items', [])

            # Handle pagination
            while 'LastEvaluatedKey' in response:
                response = self.table.query(
                    IndexName='DateIndex',
                    KeyConditionExpression=Key('state').eq(state) &
                                           Key('start_datetime').between(start_date, end_date),
                    FilterExpression=Attr('ttl').gte(int(datetime.now().timestamp())),
                    ExclusiveStartKey=response['LastEvaluatedKey']
                )
                events.extend(response.get('Items', []))

            # Deserialize Decimal types
            events = [self._deserialize_item(event) for event in events]

            return events

        except Exception as e:
            print(f"Error querying events by state: {e}")
            return []

    def get_events_by_group(
        self,
        group_id: str,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """
        Get events by group and date range using GroupIndex GSI

        Args:
            group_id: Group identifier
            start_date: Start date in ISO format
            end_date: End date in ISO format

        Returns:
            List of event dictionaries
        """
        try:
            response = self.table.query(
                IndexName='GroupIndex',
                KeyConditionExpression=Key('group_id').eq(group_id) &
                                       Key('start_datetime').between(start_date, end_date),
                FilterExpression=Attr('ttl').gte(int(datetime.now().timestamp()))
            )

            events = response.get('Items', [])

            # Handle pagination
            while 'LastEvaluatedKey' in response:
                response = self.table.query(
                    IndexName='GroupIndex',
                    KeyConditionExpression=Key('group_id').eq(group_id) &
                                           Key('start_datetime').between(start_date, end_date),
                    FilterExpression=Attr('ttl').gte(int(datetime.now().timestamp())),
                    ExclusiveStartKey=response['LastEvaluatedKey']
                )
                events.extend(response.get('Items', []))

            events = [self._deserialize_item(event) for event in events]

            return events

        except Exception as e:
            print(f"Error querying events by group: {e}")
            return []

    def get_events_by_location_type(
        self,
        location_type: str,
        start_date: str,
        end_date: str
    ) -> List[Dict[str, Any]]:
        """
        Get events by location type using LocationTypeIndex GSI

        Args:
            location_type: 'virtual' or 'in_person'
            start_date: Start date in ISO format
            end_date: End date in ISO format

        Returns:
            List of event dictionaries
        """
        try:
            response = self.table.query(
                IndexName='LocationTypeIndex',
                KeyConditionExpression=Key('location_type').eq(location_type) &
                                       Key('start_datetime').between(start_date, end_date),
                FilterExpression=Attr('ttl').gte(int(datetime.now().timestamp()))
            )

            events = response.get('Items', [])

            # Handle pagination
            while 'LastEvaluatedKey' in response:
                response = self.table.query(
                    IndexName='LocationTypeIndex',
                    KeyConditionExpression=Key('location_type').eq(location_type) &
                                           Key('start_datetime').between(start_date, end_date),
                    FilterExpression=Attr('ttl').gte(int(datetime.now().timestamp())),
                    ExclusiveStartKey=response['LastEvaluatedKey']
                )
                events.extend(response.get('Items', []))

            events = [self._deserialize_item(event) for event in events]

            return events

        except Exception as e:
            print(f"Error querying events by location type: {e}")
            return []

    def get_event(self, event_id: str, start_datetime: str) -> Optional[Dict[str, Any]]:
        """
        Get a single event by ID

        Args:
            event_id: Event identifier
            start_datetime: Event start datetime in ISO format

        Returns:
            Event dictionary or None if not found
        """
        try:
            response = self.table.get_item(
                Key={
                    'event_id': event_id,
                    'start_datetime': start_datetime
                }
            )

            item = response.get('Item')
            if item:
                return self._deserialize_item(item)
            return None

        except Exception as e:
            print(f"Error getting event: {e}")
            return None

    def put_event(self, event: Dict[str, Any]) -> bool:
        """
        Create or update an event

        Args:
            event: Event dictionary with all required fields

        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert float/int to Decimal for DynamoDB
            def serialize_value(value):
                if isinstance(value, float):
                    return Decimal(str(value))
                elif isinstance(value, dict):
                    return {k: serialize_value(v) for k, v in value.items()}
                elif isinstance(value, list):
                    return [serialize_value(v) for v in value]
                return value

            serialized_event = {k: serialize_value(v) for k, v in event.items()}

            self.table.put_item(Item=serialized_event)
            return True

        except Exception as e:
            print(f"Error putting event: {e}")
            return False

    def delete_event(self, event_id: str, start_datetime: str) -> bool:
        """
        Delete an event

        Args:
            event_id: Event identifier
            start_datetime: Event start datetime in ISO format

        Returns:
            True if successful, False otherwise
        """
        try:
            self.table.delete_item(
                Key={
                    'event_id': event_id,
                    'start_datetime': start_datetime
                }
            )
            return True

        except Exception as e:
            print(f"Error deleting event: {e}")
            return False

    def batch_write_events(self, events: List[Dict[str, Any]]) -> bool:
        """
        Batch write multiple events

        Args:
            events: List of event dictionaries

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.table.batch_writer() as batch:
                for event in events:
                    # Serialize for DynamoDB
                    def serialize_value(value):
                        if isinstance(value, float):
                            return Decimal(str(value))
                        elif isinstance(value, dict):
                            return {k: serialize_value(v) for k, v in value.items()}
                        elif isinstance(value, list):
                            return [serialize_value(v) for v in value]
                        return value

                    serialized_event = {k: serialize_value(v) for k, v in event.items()}
                    batch.put_item(Item=serialized_event)

            return True

        except Exception as e:
            print(f"Error batch writing events: {e}")
            return False
