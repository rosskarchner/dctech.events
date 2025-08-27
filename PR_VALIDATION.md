# PR Validation for DC Tech Events

This document explains how pull request validation works for the DC Tech Events calendar.

## Overview

The DC Tech Events project uses **GitHub Copilot-powered AI validation** to automatically review and approve event submissions. This provides intelligent, context-aware validation that goes far beyond simple keyword matching.

## What Gets Validated

### ✅ Single Events (`_single_events/`)
- **Fully automated** validation using GitHub Copilot
- **Automatic merging** if validation passes
- **Human review** if AI validation fails

### ⚠️ Groups (`_groups/`)
- **No automation** - all group changes require manual review
- **Manual approval** and merging required
- PRs with group changes will remain open for human review

## How Validation Works

### 1. Trigger Conditions
Validation runs automatically when a PR is opened, updated, or reopened that includes changes to:
- `_single_events/**` files

### 2. Validation Methods (in order of preference)

#### Primary: GitHub Copilot API
- Makes direct API calls to GitHub Copilot
- Provides structured JSON responses with reasoning
- Most reliable and fastest method

#### Fallback: GitHub Copilot CLI
- Uses `gh copilot suggest` command
- Activated when API access is limited
- Requires GitHub CLI installation in the runner

#### Final Fallback: Human Review
- If both Copilot methods fail, PR is left open
- Detailed comment posted with manual review guidelines
- No automatic merging occurs

### 3. Validation Criteria

The AI evaluates events against these criteria:

#### ✅ **MUST BE:**
- **Technology-related**: Programming, data science, AI, cybersecurity, cloud computing, DevOps, etc.
- **Community events**: Meetups, conferences, workshops, user group meetings
- **Free or community-priced**: Not commercial training programs

#### ❌ **MUST NOT BE:**
- **Paid training**: Bootcamps, certification courses, commercial training programs
- **Non-tech events**: Even if hosted by tech companies
- **Purely commercial**: Sales presentations, product demos without educational value

#### ✅ **CAN BE:**
- **Virtual, hybrid, or in-person** events
- **Corporate-sponsored** if genuinely community-focused
- **Beginner to advanced** technical content

## Validation Process

### Step 1: Basic Validation
- YAML structure and syntax
- Required fields: `title`, `date`, `time`, `url`, `location`
- Date format (YYYY-MM-DD) and reasonableness
- Time format (HH:MM, 24-hour)
- URL accessibility

### Step 2: AI Content Analysis
- Fetches content from the event URL
- Analyzes title and description using AI
- Determines if event meets community tech event criteria
- Provides confidence score and reasoning

### Step 3: Location Validation
- Uses AWS Location Service to geocode addresses
- Ensures events are within 50 miles of Washington, DC
- Falls back to keyword matching for DC area locations

## PR Comments and Feedback

### Successful Validation
```
✅ Event validation completed using GitHub Copilot API
```
- PR will be automatically merged
- Event will appear on the calendar

### Failed Validation
```
❌ Errors (must be fixed):
- Copilot determined this event is not appropriate: [reasoning]
- Event appears to be paid training (not allowed)
```
- PR remains open for fixes
- Detailed explanation of issues provided

### Low Confidence Warning
```
⚠️ Warnings:
- Copilot has low confidence (0.65) in this assessment
```
- PR may still pass but flagged for attention
- Manual review recommended

### Copilot Unavailable
```
⚠️ GitHub Copilot validation failed - Human review required

Both Copilot API and CLI methods were unavailable. Please manually review this event submission to ensure:
- Event is technology-related (programming, data science, AI, cybersecurity, etc.)
- Event is a community gathering (meetup, conference, workshop, etc.)
- Event is NOT paid training, bootcamp, or certification course
- Event location is within 50 miles of Washington, DC

If the event looks appropriate, you can manually merge this PR.
```

## Example Validations

### ✅ **APPROVED**: Community Tech Meetup
```yaml
title: "DC Python Meetup: Machine Learning with Scikit-Learn"
date: 2024-03-15
time: 18:30
url: https://www.meetup.com/dcpython/events/123456/
location: "Arlington, VA"
```
**AI Reasoning**: "Community Python meetup focused on machine learning education. Free event for developers to learn and network."

### ❌ **REJECTED**: Paid Training
```yaml
title: "AWS Certified Solutions Architect Bootcamp - 5 Days"
date: 2024-03-20
time: 09:00
url: https://training-company.com/aws-bootcamp
location: "Washington, DC"
```
**AI Reasoning**: "Commercial training program with certification focus. Mentions enrollment fees and intensive bootcamp format typical of paid training."

### ✅ **APPROVED**: Corporate-Sponsored Community Event
```yaml
title: "Microsoft Azure User Group: Kubernetes Best Practices"
date: 2024-03-25
time: 19:00
url: https://www.meetup.com/azure-dc/events/789012/
location: "Reston, VA"
```
**AI Reasoning**: "Corporate-sponsored but genuine community user group meeting. Technical content relevant to developers and IT professionals."

## Manual Review Guidelines

When Copilot validation fails or for group submissions, use these guidelines:

### Events Checklist
- [ ] Is this a technology-focused event?
- [ ] Is this a community gathering (not paid training)?
- [ ] Is the event free or reasonably priced for community members?
- [ ] Is the location within 50 miles of Washington, DC?
- [ ] Does the event provide educational or networking value to tech professionals?

### Groups Checklist
- [ ] Is this a technology-focused organization?
- [ ] Do they regularly host community events?
- [ ] Are they NOT primarily a commercial training company?
- [ ] Do their events serve the DC tech community?
- [ ] Is their calendar feed (iCal/RSS) accessible and properly formatted?

## Troubleshooting

### Common Issues

**"URL is not accessible"**
- Event URL returns 404 or is behind authentication
- Fix: Provide a publicly accessible event page URL

**"Event date is in the past"**
- Event date has already occurred
- Fix: Update to future date or remove if event has passed

**"Could not geocode location"**
- Location string is too vague or incorrect
- Fix: Use more specific address or recognizable DC area location

**"Copilot determined this event is not technology-related"**
- Event content doesn't clearly indicate tech focus
- Fix: Ensure event description emphasizes technical content

**"Event appears to be paid training"**
- Content mentions fees, certification, enrollment, bootcamp language
- Fix: Verify this is truly a community event, not commercial training

### Getting Help

If you believe an event was incorrectly rejected:

1. **Review the AI reasoning** provided in the PR comment
2. **Check the event URL** to ensure it clearly describes a community tech event
3. **Update the event description** if needed to clarify its community nature
4. **Request manual review** by commenting on the PR

## Benefits of AI Validation

### Compared to Keyword-Based Systems
- **Context-aware**: Understands intent, not just word matching
- **Nuanced decisions**: Can distinguish "Python workshop" (good) from "Python certification course" (paid training)
- **Detailed feedback**: Explains reasoning for decisions
- **Adaptable**: Improves as AI models advance
- **Consistent**: Applies same criteria fairly across all submissions

### Efficiency Gains
- **Faster processing**: Most PRs auto-merge within minutes
- **Reduced manual work**: Only edge cases require human review
- **Better accuracy**: Fewer false positives and negatives
- **Scalable**: Handles increased submission volume automatically

## Configuration

The validation system can be customized by modifying:

- **Prompts**: Edit validation criteria in the validator scripts
- **Confidence thresholds**: Adjust minimum confidence scores
- **Location radius**: Change the 50-mile DC area limit
- **Required fields**: Modify YAML structure requirements

See `COPILOT_VALIDATION_SETUP.md` for detailed configuration instructions.
