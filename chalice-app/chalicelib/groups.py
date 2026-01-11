"""
Groups management - Load group definitions from S3
"""
from typing import List, Dict, Any, Optional
import boto3
import yaml
import io


class GroupsManager:
    """Manager for group definitions stored in S3"""

    def __init__(self, bucket_name: str, region: str = 'us-east-1'):
        """
        Initialize groups manager

        Args:
            bucket_name: S3 bucket containing group definitions
            region: AWS region
        """
        self.bucket_name = bucket_name
        self.region = region
        self.s3 = boto3.client('s3', region_name=region)
        self._groups_cache = None

    def get_all_groups(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Get all group definitions from S3

        Args:
            force_refresh: Force reload from S3 (ignore cache)

        Returns:
            List of group dictionaries
        """
        # Return cached groups if available
        if self._groups_cache and not force_refresh:
            return self._groups_cache

        groups = []

        try:
            # List all YAML files in groups/ prefix
            response = self.s3.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix='groups/'
            )

            if 'Contents' not in response:
                return []

            # Load each group YAML file
            for obj in response['Contents']:
                key = obj['Key']

                # Skip if not a YAML file
                if not key.endswith(('.yaml', '.yml')):
                    continue

                try:
                    # Download and parse YAML
                    obj_response = self.s3.get_object(
                        Bucket=self.bucket_name,
                        Key=key
                    )

                    yaml_content = obj_response['Body'].read().decode('utf-8')
                    group = yaml.safe_load(yaml_content)

                    if group:
                        # Extract group ID from filename
                        filename = key.split('/')[-1]
                        group_id = filename.replace('.yaml', '').replace('.yml', '')
                        group['id'] = group_id

                        groups.append(group)

                except Exception as e:
                    print(f"Error loading group from {key}: {e}")
                    continue

            # Cache the groups
            self._groups_cache = groups

            return groups

        except Exception as e:
            print(f"Error listing groups from S3: {e}")
            return []

    def get_group(self, group_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific group by ID

        Args:
            group_id: Group identifier

        Returns:
            Group dictionary or None if not found
        """
        groups = self.get_all_groups()

        for group in groups:
            if group.get('id') == group_id:
                return group

        return None

    def get_active_groups(self) -> List[Dict[str, Any]]:
        """
        Get only active groups

        Returns:
            List of active group dictionaries
        """
        all_groups = self.get_all_groups()
        return [g for g in all_groups if g.get('active', False)]

    def get_groups_with_ical(self) -> List[Dict[str, Any]]:
        """
        Get groups that have iCal feeds

        Returns:
            List of group dictionaries with iCal feeds
        """
        all_groups = self.get_all_groups()
        return [
            g for g in all_groups
            if g.get('active', False) and g.get('ical')
        ]
