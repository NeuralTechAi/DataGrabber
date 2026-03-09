import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app, url_for

logger = logging.getLogger(__name__)

class EmailService:
    """Service for sending emails"""
    
    @staticmethod
    def send_password_reset_email(user_email, username, reset_token):
        """Send password reset email to user"""
        try:
            # Get email configuration from app config
            smtp_server = current_app.config.get('SMTP_SERVER', 'smtp.gmail.com')
            smtp_port = current_app.config.get('SMTP_PORT', 587)
            smtp_username = current_app.config.get('SMTP_USERNAME')
            
            # Get and format password - for Gmail App Passwords, remove any hyphens
            smtp_password = current_app.config.get('SMTP_PASSWORD', '')
            smtp_password = smtp_password.replace('-', '')  # Remove hyphens if present
            
            # Handle FROM_EMAIL format which might be "Name <email>" or just "email"
            from_email = current_app.config.get('FROM_EMAIL')
            if not from_email:
                from_email = smtp_username
            
            # Log email settings for debugging (without password)
            logger.info(f"Email settings: SMTP={smtp_server}:{smtp_port}, Username={smtp_username}, From={from_email}")
            
            if not smtp_username or not smtp_password:
                logger.error("SMTP credentials not configured")
                return False
            
            # Create reset URL
            reset_url = url_for('auth.reset_password', token=reset_token, _external=True)
            
            # Create email content
            subject = "DataGrabber - Password Reset Request"
            
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Password Reset - DataGrabber</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                    }}
                    .header {{
                        background: linear-gradient(135deg, #3b82f6, #8b5cf6);
                        color: white;
                        padding: 30px;
                        text-align: center;
                        border-radius: 10px 10px 0 0;
                    }}
                    .content {{
                        background: #f8fafc;
                        padding: 30px;
                        border-radius: 0 0 10px 10px;
                        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                    }}
                    .button {{
                        display: inline-block;
                        background: linear-gradient(135deg, #3b82f6, #8b5cf6);
                        color: white;
                        padding: 12px 30px;
                        text-decoration: none;
                        border-radius: 5px;
                        font-weight: bold;
                        margin: 20px 0;
                    }}
                    .footer {{
                        text-align: center;
                        margin-top: 30px;
                        color: #6b7280;
                        font-size: 14px;
                    }}
                    .warning {{
                        background: #fef3cd;
                        border: 1px solid #fdd023;
                        color: #8b5a00;
                        padding: 15px;
                        border-radius: 5px;
                        margin: 20px 0;
                    }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>🔐 DataGrabber</h1>
                    <p>Password Reset Request</p>
                </div>
                
                <div class="content">
                    <h2>Hello {username}!</h2>
                    
                    <p>We received a request to reset your password for your DataGrabber account. If you made this request, click the button below to set a new password:</p>
                    
                    <div style="text-align: center;">
                        <a href="{reset_url}" class="button">Reset My Password</a>
                    </div>
                    
                    <div class="warning">
                        <strong>⚠️ Security Notice:</strong>
                        <ul>
                            <li>This link will expire in 24 hours</li>
                            <li>If you didn't request this reset, please ignore this email</li>
                            <li>Never share this link with anyone</li>
                        </ul>
                    </div>
                    
                    <p>If the button above doesn't work, you can copy and paste this link into your browser:</p>
                    <p style="word-break: break-all; background: #e5e7eb; padding: 10px; border-radius: 5px; font-family: monospace;">
                        {reset_url}
                    </p>
                    
                    <p>If you didn't request a password reset, please ignore this email. Your account remains secure.</p>
                </div>
                
                <div class="footer">
                    <p>This email was sent from DataGrabber</p>
                    <p>Please do not reply to this email</p>
                </div>
            </body>
            </html>
            """
            
            text_content = f"""
            DataGrabber - Password Reset Request
            
            Hello {username}!
            
            We received a request to reset your password for your DataGrabber account.
            
            To reset your password, please visit this link:
            {reset_url}
            
            This link will expire in 24 hours.
            
            If you didn't request this password reset, please ignore this email.
            Your account remains secure.
            
            ---
            DataGrabber Team
            Please do not reply to this email.
            """
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            
            # Parse FROM_EMAIL if it's in "Name <email>" format
            if from_email and '<' in from_email and '>' in from_email:
                # It's already properly formatted
                msg['From'] = from_email
            else:
                # Just an email address
                msg['From'] = smtp_username
                
            msg['To'] = user_email
            
            # Log message details
            logger.info(f"Sending email: Subject={subject}, From={msg['From']}, To={user_email}")
            
            # Add both text and HTML versions
            text_part = MIMEText(text_content, 'plain')
            html_part = MIMEText(html_content, 'html')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Send email using Gmail-compatible approach
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                # Start TLS for security
                server.starttls()
                
                # Login with username - must be email address for Gmail
                server.login(smtp_username, smtp_password)
                
                # For Gmail, the sender must match the login email
                # Use sendmail instead of send_message to ensure compatibility
                server.sendmail(smtp_username, user_email, msg.as_string())
            
            logger.info(f"Password reset email sent to {user_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send password reset email to {user_email}: {e}")
            return False
    
    @staticmethod
    def send_password_changed_notification(user_email, username):
        """Send notification email when password is changed"""
        try:
            # Get email configuration
            smtp_server = current_app.config.get('SMTP_SERVER', 'smtp.gmail.com')
            smtp_port = current_app.config.get('SMTP_PORT', 587)
            smtp_username = current_app.config.get('SMTP_USERNAME')
            
            # Get and format password - for Gmail App Passwords, remove any hyphens
            smtp_password = current_app.config.get('SMTP_PASSWORD', '')
            smtp_password = smtp_password.replace('-', '')  # Remove hyphens if present
            
            # Handle FROM_EMAIL format which might be "Name <email>" or just "email"
            from_email = current_app.config.get('FROM_EMAIL')
            if not from_email:
                from_email = smtp_username
            
            # Log email settings for debugging (without password)
            logger.info(f"Email settings: SMTP={smtp_server}:{smtp_port}, Username={smtp_username}, From={from_email}")
            
            if not smtp_username or not smtp_password:
                logger.error("SMTP credentials not configured")
                return False
            
            subject = "DataGrabber - Password Changed"
            
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Password Changed - DataGrabber</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                    }}
                    .header {{
                        background: linear-gradient(135deg, #10b981, #059669);
                        color: white;
                        padding: 30px;
                        text-align: center;
                        border-radius: 10px 10px 0 0;
                    }}
                    .content {{
                        background: #f8fafc;
                        padding: 30px;
                        border-radius: 0 0 10px 10px;
                        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                    }}
                    .footer {{
                        text-align: center;
                        margin-top: 30px;
                        color: #6b7280;
                        font-size: 14px;
                    }}
                    .success {{
                        background: #d1fae5;
                        border: 1px solid #10b981;
                        color: #047857;
                        padding: 15px;
                        border-radius: 5px;
                        margin: 20px 0;
                    }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>🔐 DataGrabber</h1>
                    <p>Password Changed Successfully</p>
                </div>
                
                <div class="content">
                    <h2>Hello {username}!</h2>
                    
                    <div class="success">
                        <strong>✅ Security Update:</strong>
                        Your DataGrabber account password was successfully changed.
                    </div>
                    
                    <p>This email confirms that your password was updated recently. If you made this change, no further action is needed.</p>
                    
                    <p><strong>If you did not make this change:</strong></p>
                    <ul>
                        <li>Please log into your account immediately</li>
                        <li>Change your password again</li>
                        <li>Contact our support team if you need assistance</li>
                    </ul>
                    
                    <p>For your security, we recommend:</p>
                    <ul>
                        <li>Using a unique, strong password</li>
                        <li>Not sharing your login credentials</li>
                        <li>Logging out of shared devices</li>
                    </ul>
                </div>
                
                <div class="footer">
                    <p>This email was sent from DataGrabber</p>
                    <p>Please do not reply to this email</p>
                </div>
            </body>
            </html>
            """
            
            # Create message
            msg = MIMEMultipart()
            msg['Subject'] = subject
            
            # Parse FROM_EMAIL if it's in "Name <email>" format
            if from_email and '<' in from_email and '>' in from_email:
                # It's already properly formatted
                msg['From'] = from_email
            else:
                # Just an email address
                msg['From'] = smtp_username
                
            msg['To'] = user_email
            
            # Log message details
            logger.info(f"Sending email: Subject={subject}, From={msg['From']}, To={user_email}")
            
            # Add HTML content
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Send email using Gmail-compatible approach
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                # Start TLS for security
                server.starttls()
                
                # Login with username - must be email address for Gmail
                server.login(smtp_username, smtp_password)
                
                # For Gmail, the sender must match the login email
                # Use sendmail instead of send_message to ensure compatibility
                server.sendmail(smtp_username, user_email, msg.as_string())
            
            logger.info(f"Password changed notification sent to {user_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send password changed notification to {user_email}: {e}")
            return False

    @staticmethod
    def send_contact_form_email(name, email, subject, message, company=None, phone=None, is_demo=False):
        """Send contact form submission to support email"""
        try:
            # Get email configuration
            smtp_server = current_app.config.get('SMTP_SERVER', 'smtp.gmail.com')
            smtp_port = current_app.config.get('SMTP_PORT', 587)
            smtp_username = current_app.config.get('SMTP_USERNAME')

            # Get and format password - for Gmail App Passwords, remove any hyphens
            smtp_password = current_app.config.get('SMTP_PASSWORD', '')
            smtp_password = smtp_password.replace('-', '')  # Remove hyphens if present

            # Handle FROM_EMAIL format which might be "Name <email>" or just "email"
            from_email = current_app.config.get('FROM_EMAIL')
            if not from_email:
                from_email = smtp_username

            # Support/contact email - you can set this in your .env file
            support_email = current_app.config.get('SUPPORT_EMAIL', 'contactus@ntai.info')

            logger.info(f"Email settings: SMTP={smtp_server}:{smtp_port}, Username={smtp_username}, From={from_email}")

            if not smtp_username or not smtp_password:
                logger.error("SMTP credentials not configured")
                return False

            # Format email content based on type
            if is_demo:
                email_subject = f"Demo Request: {name} from {company if company else 'Not specified'}"
                email_body = f"""
Demo Request from DataGrabber Website

Name: {name}
Email: {email}
Company: {company if company else 'Not specified'}
Phone: {phone if phone else 'Not specified'}

Message:
{message}
"""
            else:
                email_subject = f"Contact Form: {subject}"
                email_body = f"""
Contact Form Submission from DataGrabber Website

Name: {name}
Email: {email}
Subject: {subject}

Message:
{message}
"""

            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>{'Demo Request' if is_demo else 'Contact Form'} - DataGrabber</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                    }}
                    .header {{
                        background: linear-gradient(135deg, #3b82f6, #8b5cf6);
                        color: white;
                        padding: 30px;
                        text-align: center;
                        border-radius: 10px 10px 0 0;
                    }}
                    .content {{
                        background: #f8fafc;
                        padding: 30px;
                        border-radius: 0 0 10px 10px;
                        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                    }}
                    .field {{
                        background: white;
                        border: 1px solid #e5e7eb;
                        padding: 15px;
                        margin: 10px 0;
                        border-radius: 5px;
                    }}
                    .field-label {{
                        font-weight: bold;
                        color: #374151;
                        margin-bottom: 5px;
                    }}
                    .message-field {{
                        background: #f9fafb;
                        border: 1px solid #d1d5db;
                        padding: 20px;
                        margin: 20px 0;
                        border-radius: 8px;
                        font-family: Georgia, serif;
                        white-space: pre-wrap;
                    }}
                    .footer {{
                        text-align: center;
                        margin-top: 30px;
                        color: #6b7280;
                        font-size: 14px;
                    }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>📧 DataGrabber</h1>
                    <p>{'Demo Request' if is_demo else 'Contact Form Submission'}</p>
                </div>

                <div class="content">
                    <div class="field">
                        <div class="field-label">Name:</div>
                        <div>{name}</div>
                    </div>

                    <div class="field">
                        <div class="field-label">Email:</div>
                        <div><a href="mailto:{email}">{email}</a></div>
                    </div>

                    {'<div class="field"><div class="field-label">Company:</div><div>' + (company if company else 'Not specified') + '</div></div>' if is_demo else ''}

                    {'<div class="field"><div class="field-label">Phone:</div><div>' + (phone if phone else 'Not specified') + '</div></div>' if is_demo else ''}

                    {('<div class="field"><div class="field-label">Subject:</div><div>' + subject + '</div></div>') if not is_demo else ''}

                    <div class="field">
                        <div class="field-label">Message:</div>
                        <div class="message-field">{message}</div>
                    </div>
                </div>

                <div class="footer">
                    <p>This email was sent from the DataGrabber website contact form</p>
                    <p>Reply directly to this email to respond to {name}</p>
                </div>
            </body>
            </html>
            """

            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = email_subject

            # Set From field to the email service but Reply-To to the user's email
            if from_email and '<' in from_email and '>' in from_email:
                msg['From'] = from_email
            else:
                msg['From'] = smtp_username

            msg['To'] = support_email
            msg['Reply-To'] = email  # Allow easy replies to the person who submitted the form

            logger.info(f"Sending contact form email: Subject={email_subject}, From={msg['From']}, To={support_email}, Reply-To={email}")

            # Add both text and HTML versions
            text_part = MIMEText(email_body, 'plain')
            html_part = MIMEText(html_content, 'html')

            msg.attach(text_part)
            msg.attach(html_part)

            # Send email using Gmail-compatible approach
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_username, smtp_password)
                server.sendmail(smtp_username, support_email, msg.as_string())

            logger.info(f"Contact form email sent from {name} ({email}) to {support_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send contact form email: {e}")
            return False