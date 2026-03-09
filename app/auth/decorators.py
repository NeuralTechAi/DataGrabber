from functools import wraps
from flask import session, redirect, url_for, abort, flash, g, current_app, request, jsonify
from app.models import User, Admin

def login_required(f):
    """Decorator for routes that require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('You must be logged in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def login_required(f):
    """Decorator for routes that require login"""
    def decorated_function(*args, **kwargs):
        current_app.logger.info(f'[AUTH] Checking login for endpoint: {request.endpoint}, path: {request.path}')
        current_app.logger.info(f'[AUTH] Session keys: {list(session.keys())}')
        if g.user is None:
            current_app.logger.warning(f'[AUTH] No valid user found for session. Clearing session and redirecting. Session: {session}')
            session.clear()

            # Detect AJAX / fetch / API requests that expect JSON back.
            # fetch() sends Accept: */*  so we can't rely solely on accept_mimetypes;
            # instead also check for XMLHttpRequest header, file-upload content type,
            # and JSON content type.
            is_ajax = (
                request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                or 'multipart/form-data' in request.content_type
                or request.is_json
                or request.accept_mimetypes.best_match(
                    ['application/json', 'text/html']
                ) == 'application/json'
            )
            if is_ajax:
                login_url = url_for('auth.login')
                return jsonify({
                    'error': 'Session expired. Please log in again.',
                    'redirect': login_url,
                }), 401

            flash('Your session has expired. Please log in again.', 'warning')
            return redirect(url_for('auth.login', next=request.url))

        current_app.logger.info(f'[AUTH] User {g.user.username} is authenticated. Proceeding.')
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def admin_required(f):
    """Decorator for routes that require admin login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        admin_id = session.get('admin_id')
        if not admin_id:
            flash("You must log in to access this page.", "warning")
            return redirect(url_for('auth.admin_login'))
        admin = Admin.query.get(admin_id)
        if not admin:
            session.pop('admin_id', None)
            flash("Invalid admin session, please log in again.", "danger")
            return redirect(url_for('auth.admin_login'))
        g.admin = admin
        return f(*args, **kwargs)
    return decorated_function

def superadmin_required(f):
    """Decorator for routes that require superadmin privileges"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        admin_id = session.get('admin_id')
        if not admin_id:
            abort(403)
        admin = Admin.query.get(admin_id)
        if not admin or not admin.is_superadmin:
            abort(403)
        g.admin = admin
        return f(*args, **kwargs)
    return decorated_function

def active_required(f):
    """Decorator to check if user is not suspended"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.user and g.user.is_suspended:
            flash('Your account has been suspended. Please contact support.', 'danger')
            return redirect(url_for('auth.logout'))
        return f(*args, **kwargs)
    return decorated_function