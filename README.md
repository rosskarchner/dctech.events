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

## 🤝 Contributing

- **Add events/groups**: Use the web forms (`/submit/` or `/submit-group/`) or submit a pull request with YAML files
- **Report issues**: Open an issue on GitHub
- **Improve code**: Fork, branch, code, and submit a pull request

Run `make validate` to check YAML files before submitting.

## 📜 License

MIT License

---

**Site**: https://dctech.events  
**Issues**: https://github.com/rosskarchner/dctech.events/issues
