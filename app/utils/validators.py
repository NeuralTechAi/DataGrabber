import re
from typing import Dict, List, Any

def validate_password(password: str) -> Dict[str, Any]:
    """
    Validate password strength according to security requirements.
    
    Requirements:
    - At least 8 characters long
    - Contains at least one uppercase letter
    - Contains at least one lowercase letter  
    - Contains at least one number
    - Contains at least one special character
    
    Returns:
        Dict with 'valid' boolean and 'errors' list
    """
    errors = []
    
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")
    
    if not re.search(r'[A-Z]', password):
        errors.append("Password must contain at least one uppercase letter")
        
    if not re.search(r'[a-z]', password):
        errors.append("Password must contain at least one lowercase letter")
        
    if not re.search(r'[0-9]', password):
        errors.append("Password must contain at least one number")
        
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        errors.append("Password must contain at least one special character (!@#$%^&*(),.?\":{}|<>)")
    
    return {
        'valid': len(errors) == 0,
        'errors': errors
    }

def get_password_requirements() -> List[str]:
    """Get list of password requirements for UI display"""
    return [
        "At least 8 characters long",
        "Contains at least one uppercase letter (A-Z)",
        "Contains at least one lowercase letter (a-z)", 
        "Contains at least one number (0-9)",
        "Contains at least one special character (!@#$%^&*(),.?\":{}|<>)"
    ]

class SimpleCaptcha:
    """Simple math-based captcha for bot protection"""
    
    @staticmethod
    def generate_challenge() -> Dict[str, Any]:
        """Generate a simple math challenge"""
        import random
        
        a = random.randint(1, 20)
        b = random.randint(1, 20)
        operation = random.choice(['+', '-', '*'])
        
        if operation == '+':
            answer = a + b
            question = f"What is {a} + {b}?"
        elif operation == '-':
            # Ensure positive result
            if a < b:
                a, b = b, a
            answer = a - b
            question = f"What is {a} - {b}?"
        else:  # multiplication
            # Keep numbers smaller for multiplication
            a = random.randint(1, 10)
            b = random.randint(1, 10)
            answer = a * b
            question = f"What is {a} × {b}?"
        
        return {
            'question': question,
            'answer': str(answer),
            'challenge_id': f"{a}{operation}{b}"
        }
    
    @staticmethod
    def verify_challenge(user_answer: str, correct_answer: str) -> bool:
        """Verify captcha answer"""
        try:
            return str(user_answer).strip() == str(correct_answer).strip()
        except (ValueError, AttributeError):
            return False