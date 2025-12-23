# DC Tech Events

A platform for aggregating and displaying technology conferences and meetups in and around Washington, DC.

## 🚀 Quick Start

### Prerequisites

- Python 3.10+ with pip
- Node.js 20+ with npm

### Local Development

1. **Install dependencies**:

```bash
pip install -r requirements.txt
npm install
```

2. **Build and run**:

```bash
make all          # Build everything
python app.py     # Start dev server
```

3. **Visit** `http://localhost:5000`

## 📝 Adding Events

### Add a Group/Meetup

Visit `/submit-group/` or create a YAML file in `_groups/` with your group's RSS or iCal feed.

### Add a Single Event

Visit `/submit/` or create a YAML file in `_single_events/` (format: `YYYY-MM-DD-event-title.yaml`).

## 🧹 Event Maintenance

### Address Handling

For aggregated events, the system extracts and displays city and state information only (e.g., "Arlington, VA"). This simplifies location handling and eliminates the need for complex address normalization. The `usaddress` library is used to accurately parse various address formats and extract city/state components.

Address extraction works with:
- Full street addresses: "1630 7th St NW, Washington, DC 20001" → "Washington, DC"
- City and state: "Arlington, VA 22201" → "Arlington, VA"
- Addresses with venue names: "The White House, 1600 Pennsylvania Avenue NW, Washington, DC" → "Washington, DC"

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
