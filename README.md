# DC Tech Events

A platform for aggregating and displaying technology conferences and meetups in and around Washington, DC.

## 🚀 Quick Start

### Prerequisites

- Python 3.10+ with pip
- Node.js 20+ with npm
- (Optional) AWS account with Location Services for enhanced address normalization

### Local Development

1. **Install dependencies**:

```bash
pip install -r requirements.txt
npm install
```

2. **Configure AWS Location Services (Optional)**:

The calendar refresh script can use AWS Location Services to normalize addresses. This is optional - the script falls back to local normalization when AWS credentials are not available.

To enable AWS Location Services:

```bash
export AWS_REGION=us-east-1
export AWS_ACCESS_KEY_ID=your_access_key_id
export AWS_SECRET_ACCESS_KEY=your_secret_access_key
export AWS_LOCATION_INDEX_NAME=your_place_index_name
```

See [cloudformation/README.md](cloudformation/README.md) for setting up AWS infrastructure.

3. **Build and run**:

```bash
make all          # Build everything
python app.py     # Start dev server
```

4. **Visit** `http://localhost:5000`

## 📝 Adding Events

### Add a Group/Meetup

Visit `/submit-group/` or create a YAML file in `_groups/` with your group's RSS or iCal feed.

### Add a Single Event

Visit `/submit/` or create a YAML file in `_single_events/` (format: `YYYY-MM-DD-event-title.yaml`).

## 🧹 Event Maintenance

### Address Normalization

Event addresses are automatically normalized using either:

1. **AWS Location Services** (preferred): When AWS credentials are configured, addresses are geocoded and normalized using Amazon Location Service. Results are cached to minimize API calls.
2. **Local Normalization** (fallback): When AWS is unavailable, a local algorithm removes redundant information like zip codes, country names, and duplicate city/state entries.

The system caches AWS normalization results in `_cache/locations.json` but never caches fallback results, ensuring all addresses are eventually normalized with AWS once credentials are available.

### Automatic Pruning

A GitHub Actions workflow runs on the 1st of each month to identify and remove old events (more than 7 days past their date). The workflow creates a pull request with the proposed deletions for review before merging.

### Manual Pruning

To manually prune old events:

```bash
python prune_old_events.py           # Delete old events
python prune_old_events.py --dry-run # Preview what would be deleted
python prune_old_events.py --days 14 # Keep events for 14 days instead
```

## 🤝 Contributing

- **Add events/groups**: Use the web forms (`/submit/` or `/submit-group/`) or submit a pull request with YAML files
- **Report issues**: Open an issue on GitHub
- **Improve code**: Fork, branch, code, and submit a pull request

### Development Workflow

1. **Validate changes**: Run `make validate` to check YAML files before submitting
2. **Run tests**: Execute `python -m unittest discover -s . -p "test_*.py"` to run all unit tests
3. **Submit PR**: All pull requests trigger automated tests via GitHub Actions

Pull requests require passing tests before they can be merged to the main branch.

## 📜 License

MIT License

---

**Site**: https://dctech.events  
**Issues**: https://github.com/rosskarchner/dctech.events/issues
