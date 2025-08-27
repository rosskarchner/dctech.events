# GitHub Copilot-Powered Event Validation Setup

This guide explains how to set up and use the new AI-powered validation system for DC Tech Events using GitHub Copilot.

## Overview

The new validation system uses GitHub Copilot to make more nuanced decisions about whether events and groups are appropriate for the DC Tech Events calendar. It's much more flexible than the previous keyword-based approach.

## Features

- **AI-powered content analysis**: Uses GitHub Copilot to understand context and intent
- **Nuanced decision making**: Can distinguish between legitimate tech events and commercial training
- **Multiple fallback methods**: API → CLI → keyword-based validation
- **Detailed explanations**: Provides reasoning for validation decisions
- **Confidence scoring**: Indicates how certain the AI is about its decisions

## Setup Requirements

### 1. GitHub Copilot Access
- You need a GitHub Copilot Pro or Enterprise account
- The validation will work in GitHub Actions using your repository's `GITHUB_TOKEN`

### 2. GitHub CLI (for CLI fallback method)
The system includes a fallback that uses the GitHub CLI if the API method fails:
```bash
# Install GitHub CLI
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt update
sudo apt install gh

# Authenticate
gh auth login
```

### 3. AWS Location Service (for location validation)
The location validation still uses AWS Location Service. Make sure you have:
- AWS credentials configured
- A place index named `DCTechEventsIndex` created

## Files Created

1. **`.github/scripts/copilot_event_validator.py`** - Main Copilot API-based validator
2. **`.github/scripts/copilot_cli_validator.py`** - Copilot CLI-based validator (fallback)
3. **`.github/workflows/validate-events-copilot.yml`** - Updated GitHub Actions workflow
4. **`test_copilot_validation.py`** - Local testing script

## Testing Locally

You can test the validation system locally:

```bash
# Make the test script executable
chmod +x test_copilot_validation.py

# Run the test
python test_copilot_validation.py
```

This will test both event and group validation with sample data.

## How It Works

### Validation Process

1. **Primary Method**: Copilot API
   - Makes direct API calls to GitHub Copilot
   - Provides structured JSON responses
   - Most reliable and fastest method

2. **Fallback Method**: Copilot CLI
   - Uses `gh copilot suggest` command
   - Works when API access is limited
   - Requires GitHub CLI installation

3. **Final Fallback**: Keyword-based
   - Uses the original keyword matching system
   - Ensures validation always completes
   - Less nuanced but reliable

### AI Prompts

The system uses carefully crafted prompts that:
- Define clear criteria for tech events vs. paid training
- Request structured JSON responses
- Include confidence scoring
- Provide reasoning for decisions

### Example Validation Criteria

**Events must be:**
- Technology-related (programming, data science, AI, cybersecurity, etc.)
- Community events, meetups, conferences, workshops
- NOT paid training, bootcamps, or certification courses
- Virtual, hybrid, or in-person (all acceptable)

**Groups must be:**
- Technology-focused
- Community-oriented (user groups, professional associations)
- NOT primarily commercial training organizations
- Can include corporate-sponsored groups if they host community events

## Switching to Copilot Validation

### Option 1: Replace Current Workflow
Rename your current workflow and use the new one:
```bash
mv .github/workflows/validate-events.yml .github/workflows/validate-events-old.yml
mv .github/workflows/validate-events-copilot.yml .github/workflows/validate-events.yml
```

### Option 2: Test in Parallel
Keep both workflows and test the new one:
- Current workflow: `validate-events.yml`
- New workflow: `validate-events-copilot.yml`

## Customizing the Validation

### Adjusting Prompts
Edit the `_create_event_validation_prompt()` and `_create_group_validation_prompt()` methods in the validator scripts to:
- Add new criteria
- Change the strictness level
- Include specific examples
- Modify the JSON response format

### Changing Confidence Thresholds
Modify the confidence score checking in `_process_copilot_response()`:
```python
if confidence < 0.7:  # Change this threshold
    self.warnings.append(f"Low confidence ({confidence:.2f})")
```

### Adding New Validation Rules
You can add custom validation logic in the `copilot_validate_*_content()` methods.

## Monitoring and Debugging

### GitHub Actions Logs
The workflow will show which validation method was used:
- ✅ Copilot API (preferred)
- ⚠️ Copilot CLI (fallback)
- ⚠️ Keyword fallback (last resort)

### PR Comments
The system posts detailed comments on PRs with:
- Validation results
- AI reasoning
- Confidence scores
- Any concerns or warnings

### Local Testing
Use the test script to debug issues:
```bash
python test_copilot_validation.py
```

## Troubleshooting

### Common Issues

1. **"GitHub token required"**
   - Ensure `GITHUB_TOKEN` is set in your environment
   - For local testing, use `gh auth token`

2. **"Copilot API not available"**
   - Check your Copilot subscription status
   - Verify API access permissions
   - The system will fall back to CLI method

3. **"Could not parse JSON response"**
   - The AI sometimes includes extra text
   - The system tries to extract JSON automatically
   - Check the prompts if this happens frequently

4. **"Low confidence scores"**
   - The AI is uncertain about the decision
   - Review the content manually
   - Consider adjusting the prompts for clarity

### Getting Help

If you encounter issues:
1. Check the GitHub Actions logs
2. Run the local test script
3. Review the PR comments for detailed error messages
4. Check that all prerequisites are installed

## Benefits Over Keyword-Based Validation

- **Context awareness**: Understands the difference between "Python training workshop" (community event) and "Python certification course" (paid training)
- **Flexible criteria**: Can adapt to new types of events without code changes
- **Better accuracy**: Reduces false positives and false negatives
- **Detailed feedback**: Provides explanations for decisions
- **Future-proof**: Improves as AI models get better

## Cost Considerations

- GitHub Copilot Pro: $10/month (you already have this)
- API calls: Minimal cost for validation (few cents per PR)
- AWS Location Service: Existing cost for location validation

The AI validation should be very cost-effective since it only runs on PR submissions, not on every event in your calendar.
