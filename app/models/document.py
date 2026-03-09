import os
import uuid
from datetime import datetime
from app.extensions import db

class Document(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = db.Column(db.String(36), db.ForeignKey('project.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)  # Empty string when files are deleted after processing
    file_type = db.Column(db.String(10), nullable=False)
    page_count = db.Column(db.Integer, default=1)
    processed = db.Column(db.Boolean, default=False)  # Track if document has been processed
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    data_records = db.relationship('DataRecord', backref='document', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Document {self.filename}>'

class DataRecord(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = db.Column(db.String(36), db.ForeignKey('document.id'), nullable=False)
    # Data is stored in project's extracted_data.xlsx file, not in database
    # This reduces database size and allows for larger data extraction
    data_file_path = db.Column(db.String(512), nullable=True)  # Path to individual data file (optional)
    row_index = db.Column(db.Integer, nullable=True)  # Row index in the project's Excel file
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def get_data(self):
        """Retrieve data from the project's Excel file based on row_index"""
        try:
            import pandas as pd
            from app.models.project import Project
            
            # Get the document and project
            document = Document.query.get(self.document_id)
            if not document:
                return {}
                
            project = Project.query.get(document.project_id)
            if not project:
                return {}
            
            # Read data from project's Excel file
            excel_path = os.path.join(project.storage_path, "extracted_data.xlsx")
            if not os.path.exists(excel_path):
                return {}
                
            df = pd.read_excel(excel_path)
            
            # Find the row with this document's filename
            matching_rows = df[df['filename'] == document.filename]
            if matching_rows.empty:
                return {}
                
            # Return the first matching row as a dictionary
            row_data = matching_rows.iloc[0].to_dict()
            # Remove metadata columns to return only field data
            metadata_cols = ['filename', 'extracted_date']
            return {k: v for k, v in row_data.items() if k not in metadata_cols}
            
        except Exception as e:
            import logging
            logging.error(f"Error retrieving data for DataRecord {self.id}: {e}")
            return {}
    
    def __repr__(self):
        return f'<DataRecord {self.id}>'