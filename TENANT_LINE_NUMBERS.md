# Exact Line Numbers for Route Updates in main.py

This document provides the exact line numbers where you need to add decorators.

## Finding the Routes

Use Ctrl+G (Go to Line) in VS Code or search for the route path.

## Routes Requiring Decorators

### FEATURE ROUTES - Add @tenant_guards.require_module('module_name')

#### Blog Feature

**Line ~2402 - Admin blog**
```python
@app.route('/admin/blog', methods=['GET', 'POST'])
@tenant_guards.require_admin()
@tenant_guards.require_module('blog')
def admin_blog():
```

**Line ~2480 - Public blog**
```python
@app.route('/blog')
@tenant_guards.require_module('blog')
def blog():
```

**Line ~2498 - Blog post detail**
```python
@app.route('/blog/<post_id>')
@tenant_guards.require_module('blog')
def blog_post(post_id):
```

#### Chat Feature

**Line ~2577 - Chat**
```python
@app.route('/chat', methods=['GET', 'POST'])
@tenant_guards.require_module('chat')
def chat():
```

**Line ~2815 - Admin chats**
```python
@app.route('/admin/chats', methods=['GET', 'POST'])
@tenant_guards.require_admin()
@tenant_guards.require_module('chat')
def admin_chats():
```

#### Tickets Feature

**Line ~2617 - Tickets**
```python
@app.route('/tickets', methods=['GET', 'POST'])
@tenant_guards.require_module('tickets')
def tickets():
```

**Line ~2866 - Admin tickets**
```python
@app.route('/admin/tickets', methods=['GET', 'POST'])
@tenant_guards.require_admin()
@tenant_guards.require_module('tickets')
def admin_tickets():
```

#### Appointments Feature

**Line ~1742 - Appointments list**
```python
@app.route('/appointments', methods=['GET'])
@tenant_guards.require_module('appointments')
def appointments():
```

**Line ~1783 - Book appointment option**
```python
@app.route('/appointments/book-option', methods=['POST'])
@tenant_guards.require_module('appointments')
def book_appointment_option():
```

**Line ~2308 - Admin block day**
```python
@app.route('/admin/appointments/block-day', methods=['POST'])
@tenant_guards.require_admin()
@tenant_guards.require_module('appointments')
def admin_block_day():
```

**Line ~2357 - Admin manage appointment**
```python
@app.route('/admin/appointment/<appointment_id>', methods=['POST'])
@tenant_guards.require_admin()
@tenant_guards.require_module('appointments')
def admin_appointment(appointment_id):
```

#### Invoices Feature

**Line ~2523 - My invoices**
```python
@app.route('/my/invoices')
@tenant_guards.require_module('invoices')
def my_invoices():
```

**Line ~2913 - Admin invoices**
```python
@app.route('/admin/invoices', methods=['GET', 'POST'])
@tenant_guards.require_admin()
@tenant_guards.require_module('invoices')
def admin_invoices():
```

### ADMIN ROUTES - Add @tenant_guards.require_admin()

These routes should have the admin decorator added (they manage admin-level functionality):

**Line ~1825 - Admin dashboard**
```python
@app.route('/admin/dashboard')
@tenant_guards.require_admin()
def admin_dashboard():
```

**Line ~1869 - Admin instances**
```python
@app.route('/admin/instances', methods=['GET', 'POST'])
@tenant_guards.require_admin()
def admin_instances():
```

**Line ~2103 - Admin instances stats**
```python
@app.route('/admin/instances/stats')
@tenant_guards.require_admin()
def admin_instances_stats():
```

**Line ~2110 - Admin system**
```python
@app.route('/admin/system', methods=['GET', 'POST'])
@tenant_guards.require_admin()
def admin_system():
```

**Line ~2191 - Admin system stats**
```python
@app.route('/admin/system/stats')
@tenant_guards.require_admin()
def admin_system_stats():
```

**Line ~2198 - Admin system logs live**
```python
@app.route('/admin/system/logs/live')
@tenant_guards.require_admin()
def admin_system_logs_live():
```

**Line ~2204 - Admin system logs core**
```python
@app.route('/admin/system/logs/core')
@tenant_guards.require_admin()
def admin_system_logs_core():
```

**Line ~2221 - Admin system logs instance**
```python
@app.route('/admin/system/logs/instance/<subdomain>')
@tenant_guards.require_admin()
def admin_system_logs_instance(subdomain):
```

**Line ~2239 - Admin system backup export**
```python
@app.route('/admin/system/backup/export/<subdomain>')
@tenant_guards.require_admin()
def admin_system_backup_export(subdomain):
```

**Line ~2263 - Admin system backup import**
```python
@app.route('/admin/system/backup/import/<subdomain>', methods=['POST'])
@tenant_guards.require_admin()
def admin_system_backup_import(subdomain):
```

**Line ~2666 - Admin users**
```python
@app.route('/admin/users', methods=['GET', 'POST'])
@tenant_guards.require_admin()
def admin_users():
```

**Line ~2698 - Admin team**
```python
@app.route('/admin/team', methods=['GET', 'POST'])
@tenant_guards.require_admin()
def admin_team():
```

## Summary Table

| Route | Line | Decorator(s) |
|-------|------|-------------|
| /blog | ~2480 | @require_module('blog') |
| /blog/<post_id> | ~2498 | @require_module('blog') |
| /admin/blog | ~2402 | @require_admin() + @require_module('blog') |
| /chat | ~2577 | @require_module('chat') |
| /admin/chats | ~2815 | @require_admin() + @require_module('chat') |
| /tickets | ~2617 | @require_module('tickets') |
| /admin/tickets | ~2866 | @require_admin() + @require_module('tickets') |
| /appointments | ~1742 | @require_module('appointments') |
| /appointments/book-option | ~1783 | @require_module('appointments') |
| /admin/appointments/block-day | ~2308 | @require_admin() + @require_module('appointments') |
| /admin/appointment/<id> | ~2357 | @require_admin() + @require_module('appointments') |
| /my/invoices | ~2523 | @require_module('invoices') |
| /admin/invoices | ~2913 | @require_admin() + @require_module('invoices') |
| /admin/dashboard | ~1825 | @require_admin() |
| /admin/instances | ~1869 | @require_admin() |
| /admin/instances/stats | ~2103 | @require_admin() |
| /admin/system | ~2110 | @require_admin() |
| /admin/system/stats | ~2191 | @require_admin() |
| /admin/system/logs/live | ~2198 | @require_admin() |
| /admin/system/logs/core | ~2204 | @require_admin() |
| /admin/system/logs/instance/<subdomain> | ~2221 | @require_admin() |
| /admin/system/backup/export/<subdomain> | ~2239 | @require_admin() |
| /admin/system/backup/import/<subdomain> | ~2263 | @require_admin() |
| /admin/users | ~2666 | @require_admin() |
| /admin/team | ~2698 | @require_admin() |

## How to Apply Updates

### Using VS Code

1. Press Ctrl+G
2. Type the line number (e.g., "2480")
3. Press Enter
4. Add the decorator(s) above the @app.route() line

### Pattern to Follow

**Before:**
```python
@app.route('/path')
def handler():
```

**After:**
```python
@app.route('/path')
@tenant_guards.require_module('module_name')
def handler():
```

**For admin routes:**
```python
@app.route('/admin/path')
@tenant_guards.require_admin()
def admin_handler():
```

**For admin feature routes:**
```python
@app.route('/admin/feature/path')
@tenant_guards.require_admin()
@tenant_guards.require_module('feature')
def admin_feature_handler():
```

### Automated Update (Optional)

Create a script to add decorators programmatically:

```python
import re

# Read the file
with open('main.py', 'r') as f:
    lines = f.readlines()

# Mapping of line numbers to decorators
updates = {
    2480: "@tenant_guards.require_module('blog')\n",
    2498: "@tenant_guards.require_module('blog')\n",
    # ... etc
}

# Apply updates (in reverse order to preserve line numbers)
for line_num in sorted(updates.keys(), reverse=True):
    decorator = updates[line_num]
    lines.insert(line_num - 1, decorator)

# Write back
with open('main.py', 'w') as f:
    f.writelines(lines)
```

## Verification

After adding decorators, verify they work:

```bash
# Test that decorator is applied
grep -n "@require_module\|@require_admin" main.py | wc -l
# Should show ~25+ decorators

# Test syntax
python -m py_compile main.py

# Run tests
pytest test_tenant_system.py -v

# Start the app
python main.py
```

## What NOT to Update

These routes should NOT have module guards added:

- `/` (home page)
- `/login`
- `/register`
- `/logout`
- `/dienstleistungen`
- `/projekte`
- `/team`
- `/kontakt`
- `/datenschutz`
- `/impressum`
- `/nutzungsbedingungen`
- `/my/instance` (user instance management - may want to add guards)

These are public or public-facing pages that should be accessible regardless of tenant module configuration.

## Line Numbers May Vary

The line numbers (~2480, ~2498, etc.) are approximate. Search for the route path instead:

- Search for `@app.route('/blog')`
- Add the decorator above it
- Repeat for each route

## Double-Check Your Work

After updating, verify:

1. ✅ Decorator is on the line ABOVE @app.route()
2. ✅ Module name matches module in tenants.json
3. ✅ No typos in decorator name
4. ✅ Both @require_admin() and @require_module() for admin features
5. ✅ Only @require_admin() for admin-only routes
6. ✅ Only @require_module() for feature-specific routes
