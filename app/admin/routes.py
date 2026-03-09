from flask import abort, render_template, request, redirect, url_for, session, flash, g, jsonify
import logging
from app.admin import bp
from app.models import User, Admin, Project, Document
from app.extensions import db
from app.auth.decorators import admin_required, superadmin_required
from app.models.admin import AdminActivity

logger = logging.getLogger(__name__)

def is_user_also_admin(user):
    """Helper function to check if a user is also an admin"""
    return Admin.query.filter_by(email=user.email).first() is not None

@bp.route('/dashboard')
@admin_required
def dashboard():
    """Admin dashboard"""
    # Get all users for the table
    users = User.query.all()
    
    # Identify which users are also admins
    admin_users = {}
    for user in users:
        admin_users[user.id] = is_user_also_admin(user)
    
    # Get statistics
    total_users = User.query.count()
    total_projects = Project.query.count()
    total_documents = Document.query.count()
    
    # Get recent activity
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    recent_projects = Project.query.order_by(Project.created_at.desc()).limit(5).all()
    
    return render_template(
        'admin/dashboard.html',
        users=users,
        admin_users=admin_users,
        is_superadmin=g.admin.is_superadmin,
        total_users=total_users,
        total_projects=total_projects,
        total_documents=total_documents,
        recent_users=recent_users,
        recent_projects=recent_projects
    )

@bp.route('/users')
@admin_required
def users():
    """Manage users"""
    users = User.query.all()
    return render_template('admin/users.html', users=users)

@bp.route('/admins')
@admin_required
def list_admins():
    """List all admins (superadmin first)"""
    if not g.admin.is_superadmin:
        abort(403)  # Only superadmins can see all admins

    # Order by superadmin first, then by creation date
    admins = Admin.query.order_by(Admin.is_superadmin.desc(), Admin.created_at.asc()).all()

    return render_template('admin/admins.html', admins=admins)

def log_admin_action(admin_id, action, target_user_email=None):
    """Log an action performed by an admin on a target user"""
    activity = AdminActivity(
        admin_id=admin_id,
        action=action,
        target_user_email=target_user_email
    )
    db.session.add(activity)
    db.session.commit()

@bp.route('/<int:admin_id>/remove', methods=['POST'])
@superadmin_required
def remove_admin(admin_id):
    """Remove another admin (superadmin only)"""
    if not g.admin.is_superadmin:
        abort(403)

    admin = Admin.query.get_or_404(admin_id)
    
    # Super Admin can't remove themselves
    if admin.id == g.admin.id:
        return jsonify({'success': False, 'error': 'Cannot remove yourself'}), 400

    # Comment out restriction - Super Admin can now remove any other admin, including other super admins
    # if admin.is_superadmin and admin.id != g.admin.id:
    #     return jsonify({'success': False, 'error': 'Cannot remove another superadmin'}), 400

    try:
        # Store admin info for logging
        admin_username = admin.username
        admin_email = admin.email
        
        db.session.delete(admin)
        db.session.commit()
        
        # Log the action
        log_admin_action(
            admin_id=g.admin.id,
            action=f"Removed admin {admin_username}",
            target_user_email=admin_email
        )
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    
@bp.route('/admin/<int:admin_id>/activity')
@admin_required
def view_admin_activity(admin_id):
    """View activities of an admin (superadmin only)"""
    if not g.admin.is_superadmin:
        abort(403)

    admin = Admin.query.get_or_404(admin_id)

    # Fetch activities for this admin
    activities = (
        AdminActivity.query
        .filter_by(admin_id=admin.id)
        .order_by(AdminActivity.timestamp.desc())
        .all()
    )

    return render_template(
        "admin/admin_activity.html",
        admin=admin,
        activities=activities
    )

@bp.route('/users/<int:user_id>/suspend', methods=['POST'])
@admin_required
def suspend_user(user_id):
    """Suspend a user"""
    user = User.query.get_or_404(user_id)
    user.is_suspended = True
    db.session.commit()
      # Log action
    log_admin_action(
            admin_id=g.admin.id,
            action=f"Suspended user {user.username}",
            target_user_email=user.email
        )

    flash(f'User {user.username} has been suspended.', 'success')
    return redirect(url_for('admin.users'))

@bp.route('/users/<int:user_id>/unsuspend', methods=['POST'])
@admin_required
def unsuspend_user(user_id):
    """Unsuspend a user"""
    user = User.query.get_or_404(user_id)
    user.is_suspended = False
    db.session.commit()
      # Log action
    log_admin_action(
        admin_id=g.admin.id,
        action=f"Unsuspended user {user.username}",
        target_user_email=user.email
    )

    flash(f'User {user.username} has been unsuspended.', 'success')
    return redirect(url_for('admin.users'))

@bp.route('/projects')
@admin_required
def projects():
    """View all projects"""
    projects = Project.query.all()
    return render_template('admin/projects.html', projects=projects)

@bp.route('/user/<int:user_id>/remove', methods=['POST'])
@admin_required
def remove_user(user_id):
    """Remove a user - Any Admin can remove regular users, SuperAdmin can remove any user"""
    try:
        user = User.query.get_or_404(user_id)
        
        # Check if the user is also an admin
        is_admin_user = Admin.query.filter_by(email=user.email).first() is not None
        
        # Only Super Admins can remove users who are also admins
        if is_admin_user and not g.admin.is_superadmin:
            return jsonify({
                'success': False, 
                'error': 'Only Super Admins can remove users who are also Admin users'
            }), 403
            
        # Store user info before deletion for logging
        username = user.username
        email = user.email
        
        # First, delete associated processing jobs to avoid foreign key constraint errors
        from app.models.processing_job import ProcessingJob
        processing_jobs = ProcessingJob.query.filter_by(user_id=user.id).all()
        
        # Log the deletion of processing jobs
        job_count = 0
        if processing_jobs:
            job_count = len(processing_jobs)
            logger.info(f"Deleting {job_count} processing jobs for user {user.id} before user deletion")
            
            # Delete each processing job
            for job in processing_jobs:
                db.session.delete(job)
            
            # Commit the deletion of processing jobs
            db.session.commit()
            logger.info(f"Successfully deleted {job_count} processing jobs for user {user.id}")
            
        # Delete password reset tokens to avoid foreign key constraint errors
        from app.models.password_reset import PasswordResetToken
        password_tokens = PasswordResetToken.query.filter_by(user_id=user.id).all()
        
        # Log the deletion of password reset tokens
        token_count = 0
        if password_tokens:
            token_count = len(password_tokens)
            logger.info(f"Deleting {token_count} password reset tokens for user {user.id} before user deletion")
            
            # Delete each password reset token
            for token in password_tokens:
                db.session.delete(token)
            
            # Commit the deletion of password reset tokens
            db.session.commit()
            logger.info(f"Successfully deleted {token_count} password reset tokens for user {user.id}")
        
        # Now delete the user
        db.session.delete(user)
        db.session.commit()
        
        # Log the admin action
        action_description = f"Removed user {username}"
        if is_admin_user:
            action_description += " (who was also an Admin)"
        
        # Include details about deleted related entities
        related_items = []
        if job_count > 0:
            related_items.append(f"{job_count} processing jobs")
        if token_count > 0:
            related_items.append(f"{token_count} password reset tokens")
            
        if related_items:
            action_description += " (including " + ", ".join(related_items) + ")"
            
        log_admin_action(
            admin_id=g.admin.id,
            action=action_description,
            target_user_email=email
        )
        
        return jsonify({'success': True})
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error removing user {user_id}: {e}")
        return jsonify({'success': False, 'error': f"Failed to remove user: {str(e)}"}), 500
    

@bp.route('/user/<int:user_id>/suspend', methods=['POST'])
@admin_required
def suspend_user_ajax(user_id):
    """Suspend a user (AJAX version)"""
    try:
        user = User.query.get_or_404(user_id)
        user.is_suspended = True
        db.session.commit()
        log_admin_action(
            admin_id=g.admin.id,
            action=f"Suspended user {user.username}",
            target_user_email=user.email
        )
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/user/<int:user_id>/unsuspend', methods=['POST'])
@admin_required
def unsuspend_user_ajax(user_id):
    """Unsuspend a user (AJAX version)"""
    try:
        user = User.query.get_or_404(user_id)
        user.is_suspended = False
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/user/<int:user_id>/stats')
@admin_required
def user_stats(user_id):
    """Get user statistics"""
    user = User.query.get_or_404(user_id)
    total_projects = Project.query.filter_by(user_id=user_id).count()
    total_documents = Document.query.join(Project).filter(Project.user_id == user_id).count()
    
    return render_template('admin/user_stats.html', 
                         user=user,
                         total_projects=total_projects,
                         total_documents=total_documents)

@bp.route('/user/<int:user_id>/add-credits', methods=['POST'])
@admin_required
def add_credits(user_id):
    """Legacy endpoint kept for compatibility; credits are no longer used."""
    return jsonify({'success': False, 'error': 'Credits system has been disabled; app is now free to use.'}), 400

@bp.route('/ai-settings', methods=['GET', 'POST'])
@superadmin_required
def ai_settings():
    """Admin AI provider/model/API key management"""
    from flask import current_app

    if request.method == 'POST':
        provider = request.form.get('provider')
        model = request.form.get('model')
        api_key = request.form.get('api_key')
        # Save to DB or config file as needed
        current_app.config['AI_PROVIDER'] = provider
        current_app.config['AI_MODEL'] = model
        
        # Set the appropriate API key based on provider
        if provider == 'openai':
            current_app.config['OPENAI_API_KEY'] = api_key
        elif provider == 'gemini':
            current_app.config['GEMINI_API_KEY'] = api_key
        elif provider == 'anthropic':
            current_app.config['ANTHROPIC_API_KEY'] = api_key
        
        flash('AI settings updated!', 'success')
        return redirect(url_for('admin.ai_settings'))

    # Expanded providers/models list - Gemini as priority
    providers = {
        'gemini': [
            'gemini-1.5-flash', 'gemini-2.0-flash', 'gemini-1.5-pro', 'gemini-2.5-flash', 'gemini-2.5-pro'
        ],
        'openai': [
            'gpt-4o-mini', 'gpt-4o', 'gpt-3.5-turbo', 'gpt-4-turbo', 'gpt-4', 'gpt-3.5-turbo-16k'
        ],
        'anthropic': [
            'claude-3-haiku-20240307', 'claude-3-sonnet-20240229', 'claude-3-opus-20240229', 'claude-2.1'
        ],
        'mistral': [
            'mistral-tiny', 'mistral-small', 'mistral-medium', 'mistral-large'
        ],
        'bedrock': [
            'amazon.titan-text-express-v1', 'amazon.titan-text-lite-v1', 'anthropic.claude-v2', 'ai21.j2-ultra-v1'
        ],
        'xai': [
            'grok-1', 'grok-1.5'
        ],
        'custom': [
            'custom-model-1', 'custom-model-2'
        ]
    }
    return render_template('admin/ai_settings.html', providers=providers)

@bp.route('/user/<int:user_id>/details')
@admin_required
def admin_user_details(user_id):
    user = User.query.get_or_404(user_id)
    credit_history = []
    payment_history = []

    # Check if user is also an admin
    is_admin_user = is_user_also_admin(user)

    stats = {
        'projects': Project.query.filter_by(user_id=user.id).count(),
        'documents': Document.query.join(Project).filter(Project.user_id == user.id).count(),
        'credits': user.credits,
        'created_at': user.created_at,
    }
    
    return render_template(
        'admin/user_details.html',
        user=user,
        credit_history=credit_history,
        payment_history=payment_history,
        stats=stats,
        is_admin_user=is_admin_user,
        is_superadmin=g.admin.is_superadmin
    )


# @bp.route('/user/<int:user_id>/details')
# @admin_required
# def user_details(user_id):
#     """Get user details"""
#     user = User.query.get_or_404(user_id)
#     projects = Project.query.filter_by(user_id=user_id).all()
#     payments = Payment.query.filter_by(user_id=user_id).all()
    
#     return render_template('admin/user_details.html', 
#                          user=user, 
#                          projects=projects, 
#                          payments=payments)

@bp.route('/admin/user/<int:user_id>/stats')
@admin_required
def admin_user_stats(user_id):
    user = User.query.get_or_404(user_id)

    # Example: subscription history, token usage, login history
    # Payments/subscriptions have been removed; keep token usage only
    subscriptions = []
    token_usage = Project.query.filter_by(user_id=user.id).order_by(Project.created_at.desc()).all()
    #login_history = LoginHistory.query.filter_by(user_id=user.id).order_by(LoginHistory.timestamp.desc()).all()

    return render_template("admin/user_stats_modal.html", 
                            user=user, 
                            subscriptions=subscriptions, 
                            token_usage=token_usage)