#!/bin/bash

# Get new newsletter subscriptions from the last two weeks

# Calculate the timestamp from 2 weeks ago (14 days)
TWO_WEEKS_AGO=$(date -d '14 days ago' --iso-8601=seconds)

echo "Fetching newsletter subscriptions since $TWO_WEEKS_AGO..."
echo ""

# Fetch contacts and filter for those created in the last two weeks
aws sesv2 list-contacts --contact-list-name newsletters --output json | \
  jq --arg cutoff "$TWO_WEEKS_AGO" '
    .Contacts
    | map(select(.CreatedTimestamp >= $cutoff))
    | sort_by(.CreatedTimestamp)
    | reverse
    | .[]
    | {
        email: .EmailAddress,
        subscribed: .CreatedTimestamp,
        topic_preferences: .TopicPreferences
      }
  '

# Also output a count
COUNT=$(aws sesv2 list-contacts --contact-list-name newsletters --output json | \
  jq --arg cutoff "$TWO_WEEKS_AGO" '[.Contacts | map(select(.CreatedTimestamp >= $cutoff))] | .[0] | length')

echo ""
echo "Total new subscriptions in the last 2 weeks: $COUNT"
