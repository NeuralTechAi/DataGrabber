"""User routes: profile, password, AI settings."""

import re
import uuid
import time
from datetime import timedelta
from flask import render_template, g, request, jsonify, flash, redirect, url_for, session
from app.auth.decorators import login_required
from app.user import bp
from app.models import User, UserAISettings
from app.extensions import db, bcrypt
from app.services.email_service import EmailService

# Provider and model options for user AI settings (OpenAI default, Gemini fallback, Ollama, OpenRouter)
AI_PROVIDERS_MODELS = {
    'openai': [
        ('gpt-4o-mini', 'gpt-4o-mini (default)'),
        ('gpt-5.2', 'GPT-5.2'),
        ('gpt-5-mini', 'GPT-5-mini'),
        ('gpt-4.1', 'gpt-4.1'),
        ('gpt-4.1-mini', 'GPT-4.1-mini'),
        ('gpt-4o', 'ChatGPT-4o'),
    ],
    'gemini': [
        ('gemini-2.5-flash', 'gemini-2.5-flash (default)'),
        ('gemini-3-flash', 'gemini-3-flash'),
        ('gemini-2.0-flash', 'gemini-2.0-flash'),
        ('gemini-3.1-flash-lite-preview', 'gemini-3.1-flash-lite-preview'),
        ('gemini-3-flash-preview', 'gemini-3-flash-preview'),
    ],
    'ollama': [],   # User enters model name; we use a text input
    'openrouter': [
        ('openrouter/openai/gpt-4o-mini', 'GPT-4o Mini'),
        ('openrouter/openai/gpt-4o', 'GPT-4o'),
        ('openrouter/anthropic/claude-3.5-sonnet', 'Claude 3.5 Sonnet'),
    ],
}
DEFAULT_OPENAI_MODEL = 'gpt-4o-mini'
DEFAULT_GEMINI_MODEL = 'gemini-2.5-flash'


@bp.route('/profile')
@login_required
def profile():
    """User profile page"""
    # Assuming g.user contains your user data
    user = g.user

    # Precompute the dates
    activity_dates = {
        'activity1': (user.created_at + timedelta(days=1)).strftime('%Y-%m-%d %H:%M'),
        'activity2': (user.created_at + timedelta(days=2)).strftime('%Y-%m-%d %H:%M'),
        'activity3': (user.created_at + timedelta(days=5)).strftime('%Y-%m-%d %H:%M')
    }

    return render_template('profile.html', user=user, activity_dates=activity_dates)

@bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """Change user password"""
    try:
        current_password = request.form.get('currentPassword')
        new_password = request.form.get('newPassword')
        confirm_password = request.form.get('confirmPassword')
        
        # Validation
        if not current_password or not new_password or not confirm_password:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': 'All fields are required'})
            flash('All fields are required', 'danger')
            return redirect(url_for('user.profile'))
        
        # Check if current password is correct
        user = g.user
        if not bcrypt.check_password_hash(user.password, current_password):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': 'Current password is incorrect'})
            flash('Current password is incorrect', 'danger')
            return redirect(url_for('user.profile'))
        
        # Check if new passwords match
        if new_password != confirm_password:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': 'New passwords do not match'})
            flash('New passwords do not match', 'danger')
            return redirect(url_for('user.profile'))
        
        # Check password strength
        if len(new_password) < 8:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': 'Password must be at least 8 characters long'})
            flash('Password must be at least 8 characters long', 'danger')
            return redirect(url_for('user.profile'))
        
        # Hash new password and update
        hashed_password = bcrypt.generate_password_hash(new_password).decode('utf-8')
        user.password = hashed_password
        db.session.commit()
        
        # Send notification email
        try:
            EmailService.send_password_changed_notification(user.email, user.username)
        except Exception as e:
            # Don't fail the password change if email fails
            pass
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': 'Password updated successfully'})
        flash('Password updated successfully', 'success')
        return redirect(url_for('user.profile'))
        
    except Exception as e:
        db.session.rollback()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'An error occurred while updating password'})
        flash('An error occurred while updating password', 'danger')
        return redirect(url_for('user.profile'))
        
@bp.route('/delete-account', methods=['POST'])
@login_required
def delete_account():
    """Delete user account (soft delete)"""
    try:
        user = g.user
        user_id = user.id
        
        # Generate anonymous values
        anonymous_id = f"deleted-{str(int(time.time()))}-{user_id}"
        anonymous_email = f"{anonymous_id}@deleted.account"
        
        # Update user record to anonymize it
        user.username = anonymous_id
        user.email = anonymous_email
        user.password = bcrypt.generate_password_hash(str(user_id) + str(int(time.time()))).decode('utf-8')
        
        # Check if the User model has is_suspended field
        if hasattr(user, 'is_suspended'):
            user.is_suspended = True
        
        # Commit changes
        db.session.commit()
        
        # Clear user session
        session.pop('user_id', None)
        
        # Return success response
        return jsonify({
            'success': True,
            'message': 'Your account has been deleted successfully.'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': 'An error occurred while deleting your account. Please try again.'
        })


@bp.route('/ai-settings', methods=['GET', 'POST'])
@login_required
def ai_settings():
    """Per-user AI provider, model, and API key settings. Any logged-in user can access."""
    user = g.user
    if request.method == 'POST':
        provider = (request.form.get('provider') or '').strip().lower()
        model = (request.form.get('model') or '').strip()
        openai_key = (request.form.get('openai_api_key') or '').strip()
        gemini_key = (request.form.get('gemini_api_key') or '').strip()
        openrouter_key = (request.form.get('openrouter_api_key') or '').strip()
        ollama_base_url = (request.form.get('ollama_base_url') or '').strip() or 'http://localhost:11434/v1'
        ollama_model = (request.form.get('ollama_model') or '').strip() or 'llama3.2'

        if provider not in ('openai', 'gemini', 'ollama', 'openrouter'):
            flash('Invalid provider.', 'danger')
            return redirect(url_for('user.ai_settings'))

        # Get or create user AI settings
        settings = UserAISettings.query.filter_by(user_id=user.id).first()
        if not settings:
            settings = UserAISettings(user_id=user.id)
            db.session.add(settings)

        settings.ai_provider = provider
        settings.ai_model = model or None
        # Only update API keys if user submitted a new value (empty = keep existing)
        if openai_key:
            settings.openai_api_key = openai_key
        if gemini_key:
            settings.gemini_api_key = gemini_key
        if openrouter_key:
            settings.openrouter_api_key = openrouter_key
        # Ollama fields always updated
        settings.ollama_base_url = ollama_base_url
        settings.ollama_model = ollama_model

        db.session.commit()
        flash('AI settings saved.', 'success')
        return redirect(url_for('user.ai_settings'))

    # GET: load current settings
    settings = UserAISettings.query.filter_by(user_id=user.id).first()
    return render_template(
        'user/ai_settings.html',
        providers_models=AI_PROVIDERS_MODELS,
        default_openai=DEFAULT_OPENAI_MODEL,
        default_gemini=DEFAULT_GEMINI_MODEL,
        settings=settings,
    )