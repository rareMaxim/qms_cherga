# QMS Cherga - AI Assistant Guide

## Project Overview

**QMS Cherga** is an open-source Queue Management System (QMS) built on the Frappe Framework. It provides a SaaS solution for managing queues with features including:
- Live queue management
- Appointment booking
- Self-service kiosk
- Display board for queue status
- Operator dashboard

**Author**: Maxym Sysoiev (maks4a@gmail.com)
**License**: MIT
**Language**: Python 3.10+, JavaScript (Vue 3)

## Technology Stack

### Backend
- **Framework**: Frappe Framework v15+
- **Language**: Python 3.10+
- **Database**: MariaDB (via Frappe)
- **ORM**: Frappe ORM
- **Real-time**: WebSocket (Socket.IO) via Frappe

### Frontend
- **Framework**: Vue 3 (Composition API)
- **Build Tool**: Vite 6
- **Styling**: Tailwind CSS 4
- **Icons**: Font Awesome, Lucide Icons
- **Components**: Unplugin Vue Components
- **Real-time**: Socket.IO Client

### Development Tools
- **Linting/Formatting**: Ruff (Python), ESLint (JS), Prettier
- **Pre-commit**: pre-commit hooks configured
- **Package Manager**: npm/yarn (frontend), bench (Frappe)

## Directory Structure

```
qms_cherga/
├── frontend/                    # Vue 3 frontend application
│   ├── src/
│   │   ├── views/              # Main Vue views (Kiosk, DisplayBoard, OperatorDashboard)
│   │   ├── components/         # Reusable Vue components
│   │   ├── services/           # API and Socket services
│   │   └── main-*.js           # Entry points for each app
│   ├── dist/                   # Build output (generated, gitignored)
│   ├── vite.config.js          # Vite configuration
│   └── tailwind.config.js      # Tailwind CSS configuration
│
├── qms_cherga/                 # Main Python module (Frappe app)
│   ├── qms_cherga/             # Core module (nested)
│   │   ├── doctype/            # All DocTypes (database models)
│   │   │   ├── qms_ticket/     # Example: Ticket DocType
│   │   │   │   ├── qms_ticket.json      # DocType definition
│   │   │   │   ├── qms_ticket.py        # Controller (business logic)
│   │   │   │   ├── qms_ticket.js        # Client-side script
│   │   │   │   └── test_qms_ticket.py   # Tests
│   │   │   ├── qms_service/
│   │   │   ├── qms_operator/
│   │   │   ├── qms_office/
│   │   │   └── ...             # Other DocTypes
│   │   ├── workspace/          # Frappe workspace definitions
│   │   ├── onboarding_step/    # Onboarding configuration
│   │   └── print_format/       # Print templates
│   │
│   ├── public/                 # Static assets served by Frappe
│   │   ├── js/                 # Built JS files (auto-deployed from frontend)
│   │   └── css/                # Built CSS files (auto-deployed from frontend)
│   │
│   ├── www/                    # Web pages (public-facing)
│   │   └── qms_kiosk.py        # Page controller
│   │
│   ├── templates/              # Jinja2 templates
│   │   ├── pages/              # Page templates
│   │   └── base_minimal.py     # Custom base template
│   │
│   ├── utils/                  # Utility functions
│   │   └── response.py         # Standardized API responses
│   │
│   ├── tests/                  # Module-level tests
│   │   └── test_api.py
│   │
│   ├── api.py                  # Whitelisted API endpoints (main API file, 60KB+)
│   ├── hooks.py                # Frappe hooks configuration
│   ├── modules.txt             # Module list
│   └── patches.txt             # Database migration patches
│
├── .pre-commit-config.yaml     # Pre-commit hooks configuration
├── pyproject.toml              # Python project configuration
├── package.json                # Frontend dependencies
├── deploy-vue-assets.js        # Script to deploy built assets to Frappe
├── .gitignore                  # Git ignore rules
└── README.md                   # Project documentation
```

## Key Architecture Patterns

### Frappe Framework Patterns

1. **DocType Pattern**: Core data structure
   - JSON definition (`.json`) - schema, fields, permissions
   - Python controller (`.py`) - business logic, validations, hooks
   - Client script (`.js`) - UI behaviors, form customizations
   - Tests (`test_*.py`) - unit tests

2. **Whitelisted APIs**: Use `@frappe.whitelist()` decorator for endpoints
   - Located in `qms_cherga/api.py`
   - Return standardized responses using `utils/response.py`

3. **Document Events**: Lifecycle hooks in DocType controllers
   - `after_insert()` - after document creation
   - `on_update()` - after document update
   - `after_delete()` - after deletion
   - `validate()` - before save validation

### Frontend Architecture

1. **Multi-Entry Point**: Three separate applications
   - **Kiosk**: Self-service ticket creation
   - **Display Board**: Real-time queue display
   - **Operator Dashboard**: Operator queue management

2. **Build Process**:
   - `yarn build` → Vite builds to `frontend/dist/`
   - `deploy-vue-assets.js` → Copies built files to `qms_cherga/public/`
   - HTML files in `frontend/*.html` are templates with Jinja2

3. **Real-time Communication**:
   - Socket.IO for live updates
   - Room-based subscriptions (e.g., `qms_office:{office_id}`)
   - Events: `qms_ticket_created`, `qms_ticket_updated_doc`, `qms_ticket_deleted`

### API Response Pattern

All API endpoints use standardized responses from `utils/response.py`:

```python
# Success
success_response(data=..., message="Optional message")

# Error
error_response(
    message="Error message",
    error_code="OPTIONAL_CODE",
    details="Debug info",
    http_status_code=400
)

# Info
info_response(message="Info message", data=...)
```

## Code Style and Conventions

### Python (Ruff Configuration)

- **Line Length**: 110 characters
- **Target**: Python 3.10+
- **Indentation**: Tabs (as per Frappe convention)
- **Quotes**: Double quotes
- **Import Sorting**: Automated by Ruff
- **Type Hints**: Auto-generated for DocTypes, encouraged for APIs

Key lint rules enabled:
- F (Pyflakes)
- E/W (pycodestyle)
- I (isort)
- UP (pyupgrade)
- B (flake8-bugbear)
- RUF (Ruff-specific)

### JavaScript/Vue

- **Formatter**: Prettier
- **Linter**: ESLint
- **Style**: Composition API for Vue 3
- **Indentation**: 2 spaces (standard JS convention)

### Pre-commit Hooks

Always run before commits:
```bash
pre-commit install
```

Hooks configured:
- Trailing whitespace removal
- Merge conflict detection
- JSON/YAML/TOML validation
- Ruff import sorting, linting, formatting
- Prettier (JS/Vue/SCSS)
- ESLint (JavaScript)

## Development Workflow

### Setting Up Development Environment

1. **Install the app**:
   ```bash
   cd $PATH_TO_YOUR_BENCH
   bench get-app https://github.com/rareMaxim/qms_cherga --branch develop
   bench install-app qms_cherga
   ```

2. **Install pre-commit**:
   ```bash
   cd apps/qms_cherga
   pre-commit install
   ```

3. **Install frontend dependencies**:
   ```bash
   cd apps/qms_cherga
   npm install
   ```

### Frontend Development

**Development server** (hot reload):
```bash
yarn dev
# or: cd frontend && yarn vite --host --force
```

**Production build**:
```bash
yarn build
# This runs: cd frontend && vite build && yarn deploy:vue
```

**Manual deployment**:
```bash
yarn deploy:vue
# Runs deploy-vue-assets.js to copy dist/ to public/
```

### Backend Development

**Start Frappe bench**:
```bash
bench start
```

**Run tests**:
```bash
# All tests
bench run-tests --app qms_cherga

# Specific test
bench run-tests --app qms_cherga --module qms_cherga.qms_cherga.doctype.qms_ticket.test_qms_ticket
```

**Access logs**:
- Check bench console output
- View Error Log DocType in Frappe UI

### Database Migrations

When modifying DocTypes:
1. Modify the JSON definition via Frappe UI or directly
2. Run `bench migrate` to apply changes
3. Consider creating patches in `patches.txt` for data migrations

## DocTypes (Core Entities)

### Main DocTypes

1. **QMS Organization**: Top-level entity (multi-tenant)
2. **QMS Office**: Physical location/branch
3. **QMS Service Category**: Service grouping
4. **QMS Service**: Individual service offered
5. **QMS Service Point**: Operator workstation
6. **QMS Operator**: Staff member serving queue
7. **QMS Ticket**: Queue ticket/record
8. **QMS Schedule**: Operating hours and rules
9. **QMS Daily Counter**: Daily ticket numbering
10. **QMS Kiosk Settings**: Kiosk configuration

### Important Fields & Relationships

- **QMS Ticket**: Links to Office, Service, Service Point, Operator
  - Statuses: Scheduled, Waiting, Called, Serving, Completed, NoShow, Cancelled, Postponed
  - Auto-generated ticket_number
  - Timing fields: issue_time, call_time, start_service_time, completion_time

- **QMS Operator**: Links to Frappe User, Office
  - Skills mapping via QMS Operator Skill

## Common Development Tasks

### Adding a New API Endpoint

1. Open `qms_cherga/api.py`
2. Add function with `@frappe.whitelist()` decorator:
   ```python
   @frappe.whitelist()
   def my_new_endpoint(param1, param2):
       """API documentation here."""
       try:
           # Your logic
           result = do_something(param1, param2)
           return success_response(data=result)
       except Exception as e:
           frappe.log_error(frappe.get_traceback(), "My Endpoint Error")
           return error_response("Error message", details=str(e))
   ```
3. Call from frontend: `frappe.call({ method: 'qms_cherga.api.my_new_endpoint', args: {...} })`

### Creating a New DocType

1. **Via UI** (recommended):
   - Go to Frappe Desk → DocType List → New
   - Define fields, permissions, naming
   - Save

2. **Add controller logic**:
   - Edit `qms_cherga/qms_cherga/doctype/<doctype_name>/<doctype_name>.py`
   - Add validation, lifecycle hooks

3. **Add client script** (optional):
   - Edit `.js` file for form behaviors

4. **Write tests**:
   - Edit `test_<doctype_name>.py`

### Adding a New Frontend View

1. Create Vue component in `frontend/src/views/MyView.vue`
2. Create entry point: `frontend/src/main-myview.js`
3. Create HTML template: `frontend/myview.html`
4. Update `vite.config.js` to include new entry:
   ```javascript
   input: {
       myview: resolve(__dirname, 'myview.html'),
       // ... existing entries
   }
   ```
5. Build and deploy: `yarn build`
6. Create page in `qms_cherga/www/my_view.py` and `.html` template

### Publishing Real-time Events

In DocType controller:
```python
def publish_event(self, event_name_for_socket, event_type_in_payload):
    """Publish real-time event via WebSocket."""
    from qms_cherga.api import office_room

    frappe.publish_realtime(
        event=event_name_for_socket,
        message={
            "type": event_type_in_payload,
            "ticket": self.as_dict()
        },
        room=office_room(self.office)
    )
```

## Important Gotchas and Notes

### Frappe-Specific

1. **Permissions**: All API methods need `@frappe.whitelist()` and appropriate permissions
2. **Transactions**: Frappe automatically handles DB transactions; use `frappe.db.commit()` sparingly
3. **Session**: Access current user via `frappe.session.user`
4. **Translations**: Use `frappe._("Text")` for translatable strings (supports Ukrainian)
5. **Type Annotations**: Auto-generated in DocType controllers, maintain them

### Frontend

1. **Base URL**: All assets served from `/assets/qms_cherga/` (configured in Vite)
2. **Jinja in HTML**: Frontend HTML templates mix Jinja2 (server-side) and Vue (client-side)
3. **Build artifacts**: `frontend/dist/` and generated files in `www/` are gitignored
4. **Socket.IO**: Must authenticate and join rooms before receiving events

### Git

1. **Ignored files**: Built HTML files in `www/`, built assets in `public/js|css/*.*.{js,css}`
2. **Generated files**: DocType JSON files auto-update, commit them
3. **Branch**: Development happens on `develop` branch

### Performance

1. **Large API file**: `api.py` is 60KB+ (1600+ lines), consider splitting for maintainability
2. **Real-time events**: Be mindful of event frequency to avoid overwhelming clients
3. **Database queries**: Use Frappe ORM efficiently, leverage caching where appropriate

## Testing

### Python Tests

Located in:
- `qms_cherga/tests/test_api.py` - API tests
- Each DocType folder: `test_<doctype>.py`

Run tests:
```bash
# All tests
bench run-tests --app qms_cherga

# Specific module
bench run-tests --app qms_cherga --module qms_cherga.tests.test_api

# With coverage
bench run-tests --app qms_cherga --coverage
```

### Manual Testing

1. **Kiosk**: Navigate to `/qms_kiosk`
2. **Display Board**: Navigate to display board URL
3. **Operator Dashboard**: Navigate to operator dashboard URL
4. Use Frappe UI to manage DocTypes directly

## Resources

- **Frappe Framework Docs**: https://frappeframework.com/docs
- **Vue 3 Docs**: https://vuejs.org/guide/introduction.html
- **Vite Docs**: https://vitejs.dev/guide/
- **Tailwind CSS**: https://tailwindcss.com/docs

## Quick Reference

### Common Commands

```bash
# Bench operations
bench start                    # Start development server
bench migrate                  # Run migrations
bench build                    # Build assets
bench clear-cache              # Clear Frappe cache
bench console                  # Python console with Frappe context

# Frontend
yarn dev                       # Start Vite dev server
yarn build                     # Build production assets
yarn deploy:vue                # Deploy built assets to public/

# Code quality
pre-commit run --all-files     # Run all pre-commit hooks
ruff check .                   # Lint Python code
ruff format .                  # Format Python code
```

### File Locations Quick Reference

- **Add API endpoint**: `qms_cherga/api.py`
- **Modify DocType**: `qms_cherga/qms_cherga/doctype/<name>/`
- **Frontend views**: `frontend/src/views/`
- **Frontend components**: `frontend/src/components/`
- **Utility functions**: `qms_cherga/utils/`
- **Web pages**: `qms_cherga/www/`
- **Templates**: `qms_cherga/templates/`
- **Hooks config**: `qms_cherga/hooks.py`

---

**Last Updated**: 2025-11-15
**For**: AI assistants working with the QMS Cherga codebase
