#!/usr/bin/env python3
"""
Fix project storage paths that are invalid
"""
import os
import sys

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

def fix_invalid_project_paths():
    """Fix projects with invalid storage paths"""
    print("=== FIXING PROJECT STORAGE PATHS ===")

    try:
        from app import create_app
        from app.models import Project
        from app.extensions import db

        app = create_app()

        with app.app_context():
            # Find projects with invalid paths
            projects = Project.query.all()
            fixed_count = 0

            for project in projects:
                if project.storage_path and not os.path.exists(project.storage_path):
                    print(f"\nProject: {project.name} (ID: {project.id})")
                    print(f"  Current invalid path: {project.storage_path}")

                    # Create a new valid path
                    if '/home/cnb' in project.storage_path:
                        # Replace /home/cnb with user's home directory
                        new_path = os.path.join(os.path.expanduser('~'), 'DataGrabber', project.name.replace(' ', '_'))
                    else:
                        # Default fallback
                        new_path = os.path.join(os.path.expanduser('~'), 'DataGrabber', project.name.replace(' ', '_'))

                    print(f"  New path: {new_path}")

                    # Create the directory
                    try:
                        os.makedirs(new_path, exist_ok=True)
                        print(f"  ✅ Created directory: {new_path}")

                        # Update the project
                        project.storage_path = new_path
                        db.session.commit()
                        print(f"  ✅ Updated project storage path")

                        fixed_count += 1

                    except Exception as e:
                        print(f"  ❌ Error creating directory: {e}")

            print(f"\n✅ Fixed {fixed_count} project(s)")
            return True

    except Exception as e:
        print(f"❌ Error fixing paths: {e}")
        return False

def test_gemini_api_simple():
    """Test if Gemini API key works with a simple request"""
    print("\n=== TESTING GEMINI API KEY ===")

    try:
        import google.generativeai as genai

        # Get API key
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            print("❌ No GEMINI_API_KEY found")
            return False

        print(f"Testing API key: {api_key[:10]}...")

        # Configure genai
        genai.configure(api_key=api_key)

        # Try to list models (simple test)
        try:
            models = list(genai.list_models())
            print(f"✅ API key works! Found {len(models)} models")
            return True
        except Exception as e:
            print(f"❌ API key test failed: {e}")
            print("The API key appears to be invalid or expired")
            return False

    except Exception as e:
        print(f"❌ Error testing Gemini API: {e}")
        return False

def suggest_fixes():
    """Suggest how to fix the issues"""
    print("\n=== SUGGESTED FIXES ===")

    print("\n1. For the Gemini API Key issue:")
    print("   - The current key appears to be invalid")
    print("   - Get a new API key from: https://aistudio.google.com/app/apikey")
    print("   - Update the GEMINI_API_KEY in your .env file")

    print("\n2. For the project path issue:")
    print("   - Project paths have been automatically fixed")
    print("   - New paths created in ~/DataGrabber/")

    print("\n3. Environment setting:")
    print("   - Consider setting FLASK_ENV=development for local testing")
    print("   - This prevents overly strict cloud restrictions")

def main():
    """Run all fixes"""
    print("DataGrabber Issue Fixes")
    print("=" * 25)

    # Fix project paths
    fix_invalid_project_paths()

    # Test API key
    test_gemini_api_simple()

    # Provide suggestions
    suggest_fixes()

if __name__ == '__main__':
    main()