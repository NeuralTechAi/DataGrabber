from flask import render_template, g, session, request, jsonify, redirect, url_for
from app.main import bp
from app.models import Project, Document, DataRecord, Admin
from app.auth.decorators import login_required

@bp.route('/')
def index():
    """Landing page (no pricing/Stripe context needed)"""
    return render_template('landing.html')

@bp.route('/dashboard')
@login_required
def dashboard():
    """User dashboard"""
    user = g.user
    projects = Project.query.filter_by(user_id=user.id).all()
    
    # Synchronize the user's money balance with their credits
    if user.sync_balance_with_credits():
        from app.extensions import db
        db.session.commit()
    
    # Get usage statistics
    total_documents = Document.query.join(Project).filter(Project.user_id == user.id).count()
    total_records = DataRecord.query.join(Document).join(Project).filter(Project.user_id == user.id).count()
    
    # Get recent activity (documents only – no payments)
    recent_documents = Document.query.join(Project).filter(Project.user_id == user.id).order_by(Document.uploaded_at.desc()).limit(5).all()
    
    return render_template(
        'dashboard.html',
        user=user,
        projects=projects,
        total_documents=total_documents,
        total_records=total_records,
        recent_documents=recent_documents,
        credits_display=user.credits,
        money_balance=user.balance  # Kept for compatibility with existing templates
    )

# In app/main/routes.py

@bp.route('/debug-session')
def debug_session():
    """Debug session information"""
    return {
        'session': dict(session),
        'user_id': session.get('user_id'),
        'has_user': g.user is not None,
        'user_info': g.user.username if g.user else None
    }

@bp.route('/admin')
def admin_landing():
    """Admin landing page"""
    superadmin_exists = Admin.query.filter_by(is_superadmin=True).first() is not None
    return render_template('admin_landing.html', superadmin_exists=superadmin_exists)

@bp.route('/documentation')
def documentation():
    """Documentation page"""
    return render_template('documentation.html')

@bp.route('/contact')
def contact():
    """Contact page – redirected to home"""
    return redirect(url_for('main.index'))

@bp.route('/contact/submit', methods=['POST'])
def contact_submit():
    """Contact form disabled – redirect to home"""
    return redirect(url_for('main.index'))


