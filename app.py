#!/usr/bin/env python3
"""
DataGrabber Application Entry Point
"""
'''import os
from app import create_app
from app.extensions import db

# Create the app using the factory
app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    app.run(
        #debug=True, 
        host='0.0.0.0', 
        port=int(os.environ.get("PORT", 8080))
    )

'''

import os
from app import create_app
from app.extensions import db

# Create the app using the factory
app = create_app()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
