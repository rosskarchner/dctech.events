from template_utils import prepare_group_for_template, prepare_event_for_template
from queries import get_events, get_approved_groups

from flask import Flask, render_template
from flask_htmx import HTMX

from datetime import date
app = Flask(__name__, template_folder='templates')
htmx = HTMX(app)

base_context = {
    'title': 'DC Tech Events!',
}

def hx_aware_render(template_name=None, context=None):
    if context is None:
        context = {}
    context.update(base_context)
    
    # Convert mustache template name to Jinja2 template name
    jinja_template_name = template_name.replace('.mustache', '.html')
    
    partial_rendered = render_template(jinja_template_name, **context)
    if htmx:
        return partial_rendered
    else:
        return render_template('shell.html', content=partial_rendered)

@app.route("/")
def homepage():
    # Get approved events for current week and next 3 weeks
    days = get_events(start_date=None, additional_weeks=3, status='APPROVED')
    context = {
                'days': days
              }
    
    return hx_aware_render(template_name='homepage.mustache', context=context)


@app.route("/week-of/<int:year>-<int:month>-<int:day>/")
def week_of(year, month, day):
    # Get approved events for the given week
    requested_date=date(year, month, day )
    days = get_events(start_date=requested_date, additional_weeks=0, status='APPROVED')
    context = {
                'days': days
              }

    return hx_aware_render(template_name='week_page.mustache', context=context)

@app.route("/groups/")
def approved_groups_list():
    return hx_aware_render(template_name='approved_groups_list.mustache', context={'groups': get_approved_groups()})



@app.route("/admin/groups/")
def groups_admin_shell():
    return hx_aware_render(template_name='admin_group_shell.mustache') 


@app.route("/admin/events/")
def events_admin_shell():
    return hx_aware_render(template_name='admin_events_shell.mustache') 

@app.route("/events/suggest/")
def events_suggest_shell():
    return hx_aware_render(template_name='event_suggest_shell.mustache') 

@app.route("/group/suggest/")
def groups_suggest_shell():
    return hx_aware_render(template_name='group_suggest_shell.mustache') 


@app.route("/auth-callback/")
def auth_callback():
    return render_template('auth_callback.html')
    
@app.route("/test/")
def test_jinja():
    return render_template('test/hello.html', title="Test Page", message="Jinja2 is working!")


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)