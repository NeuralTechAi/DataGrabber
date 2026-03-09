import re
import logging
from flask import render_template, request, redirect, url_for, session, flash, g, jsonify
from app.auth import bp
from app.models import User, Admin, PasswordResetToken
from app.extensions import db, bcrypt
from app.services.email_service import EmailService
from app.utils.validators import validate_password, SimpleCaptcha

logger = logging.getLogger(__name__)

@bp.before_app_request
def load_user():
    """Load user before each request"""
    g.user = None
    user_id = session.get('user_id')
    if user_id:
        g.user = User.query.get(user_id)

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        # Basic validation
        if not username or not email or not password:
            return jsonify({'success': False, 'message': 'All fields are required'})

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({
                'success': False,
                'message': 'This email is already registered. If you have forgotten your password, please use the password recovery option.'
            })

        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return jsonify({'success': False, 'message': 'Invalid email address'})

        # Validate password strength
        password_validation = validate_password(password)
        if not password_validation['valid']:
            return jsonify({
                'success': False, 
                'message': 'Password does not meet requirements: ' + '; '.join(password_validation['errors'])
            })

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        # Credits are no longer used for billing; start at 0
        new_user = User(username=username, email=email, password=hashed_password, credits=0)

        db.session.add(new_user)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Registration successful! Please log in.', 'redirect': url_for('auth.login')})

    return render_template('register.html')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login user"""
    if 'user_id' in session:
        return redirect(url_for('main.dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Basic validation
        if not email or not password:
            error_msg = 'All fields are required'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': error_msg}), 400
            flash(error_msg, 'danger')
            return render_template('login.html')
        
        user = User.query.filter_by(email=email).first()
        
        if user and bcrypt.check_password_hash(user.password, password):
            if user.is_suspended:
                error_msg = 'Your account has been suspended. Please contact support.'
                
                # Handle AJAX requests
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({'success': False, 'error': error_msg}), 400
                    
                flash(error_msg, 'danger')
                return render_template('login.html')
                
            session['user_id'] = user.id
            session.permanent = True
            
            # Handle AJAX requests
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': True, 
                    'redirect': url_for('main.dashboard'),
                    'message': f'Welcome back, {user.username}!'
                })
            
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(url_for('main.dashboard'))
        else:
            error_msg = 'Invalid email or password'
            
            # Handle AJAX requests
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': error_msg}), 400
                
            flash(error_msg, 'danger')
            return render_template('login.html')

    return render_template('login.html')

@bp.route('/logout')
def logout():
    """Logout user"""
    session.pop('user_id', None)
    flash('You have been logged out.', 'success')   
    return redirect(url_for('main.index'))

@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Request password reset"""
    if 'user_id' in session:
        return redirect(url_for('main.dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        
        if not email:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': 'Email is required'})
            flash('Email is required', 'danger')
            return redirect(url_for('auth.forgot_password'))
        
        # Always show success message for security (don't reveal if email exists)
        success_message = 'If an account with this email exists, you will receive password reset instructions.'
        
        user = User.query.filter_by(email=email).first()
        if user:
            try:
                # Clean up old tokens for this user
                old_tokens = PasswordResetToken.query.filter_by(user_id=user.id).all()
                for token in old_tokens:
                    db.session.delete(token)
                
                # Create new reset token
                reset_token = PasswordResetToken(user_id=user.id)
                db.session.add(reset_token)
                db.session.commit()
                
                # Send email
                EmailService.send_password_reset_email(user.email, user.username, reset_token.token)
                
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error creating password reset token: {e}")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'message': success_message})
        flash(success_message, 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('forgot_password.html')

@bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Reset password with token"""
    logger.info(f"Password reset request: method={request.method}, token={token[:16]}...")
    
    if 'user_id' in session:
        return redirect(url_for('main.dashboard'))
    
    # Find and validate token
    reset_token = PasswordResetToken.query.filter_by(token=token).first()
    
    if not reset_token or not reset_token.is_valid():
        flash('Invalid or expired password reset link. Please request a new one.', 'danger')
        return redirect(url_for('auth.forgot_password'))
    
    if request.method == 'POST':
        logger.info("Processing password reset form submission")
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        logger.info(f"Form data received: password={'YES' if password else 'NO'}, confirm_password={'YES' if confirm_password else 'NO'}")
        
        # Validation
        if not password or not confirm_password:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': 'Both password fields are required'})
            flash('Both password fields are required', 'danger')
            return render_template('reset_password.html', token=token)
        
        if password != confirm_password:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': 'Passwords do not match'})
            flash('Passwords do not match', 'danger')
            return render_template('reset_password.html', token=token)
        
        # Validate password strength
        password_validation = validate_password(password)
        if not password_validation['valid']:
            error_msg = 'Password does not meet requirements: ' + '; '.join(password_validation['errors'])
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': error_msg})
            flash(error_msg, 'danger')
            return render_template('reset_password.html', token=token)
        
        try:
            # Update user password
            user = reset_token.user
            user.password = bcrypt.generate_password_hash(password).decode('utf-8')
            
            # Mark token as used
            reset_token.mark_as_used()
            
            db.session.commit()
            
            # Send notification email
            EmailService.send_password_changed_notification(user.email, user.username)
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'message': 'Password updated successfully. You can now log in.', 'redirect': url_for('auth.login')})
            flash('Password updated successfully. You can now log in.', 'success')
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error resetting password: {e}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': 'An error occurred while resetting password'})
            flash('An error occurred while resetting password', 'danger')
            return render_template('reset_password.html', token=token)
    
    return render_template('reset_password.html', token=token)

# Admin routes
@bp.route('/admin/register', methods=['GET', 'POST'])
def admin_register():
    """Register admin"""
    superadmin_exists = Admin.query.filter_by(is_superadmin=True).first()
    
    if superadmin_exists:
        if 'admin_id' not in session:
            flash('You must be logged in as superadmin to register new admins.', 'danger')
            return redirect(url_for('auth.admin_login'))
        admin = Admin.query.get(session['admin_id'])
        if not admin or not admin.is_superadmin:
            flash('Only the superadmin can register new admins.', 'danger')
            return redirect(url_for('admin.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        # Validation
        if not username or not email or not password:
            flash('All fields are required', 'danger')
            return redirect(url_for('auth.admin_register'))

        if Admin.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('auth.admin_register'))

        if Admin.query.filter_by(email=email).first():
            flash('Email already exists', 'danger')
            return redirect(url_for('auth.admin_register'))

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_admin = Admin(
            username=username,
            email=email,
            password=hashed_password,
            is_superadmin=False if superadmin_exists else True
        )

        db.session.add(new_admin)
        db.session.commit()

        if not superadmin_exists:
            flash('Superadmin account created! Please login.', 'success')
            return redirect(url_for('auth.admin_login'))

        flash('New admin registered successfully!', 'success')
        return redirect(url_for('admin.dashboard'))

    return render_template('admin_register.html', superadmin_exists=superadmin_exists)

@bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login"""
    if 'admin_id' in session:
        return redirect(url_for('admin.dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        admin = Admin.query.filter_by(email=email).first()
        
        if not admin:
            flash('Admin not registered. Please register first.', 'danger')
            return redirect(url_for('auth.admin_register'))
            
        if admin and bcrypt.check_password_hash(admin.password, password):
            session['admin_id'] = admin.id
            session.permanent = True
            flash(f'Welcome back, Admin {admin.username}!', 'success')
            return redirect(url_for('admin.dashboard'))
        else:
            flash('Admin login failed. Please check your email and password.', 'danger')
            
    return render_template('admin_login.html')

@bp.route('/admin/logout')
def admin_logout():
    """Logout admin"""
    session.pop('admin_id', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('main.admin_landing'))