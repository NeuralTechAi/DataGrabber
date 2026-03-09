import uuid
from datetime import datetime
from app.extensions import db

class ProcessingJob(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    project_id = db.Column(db.String(36), db.ForeignKey('project.id'), nullable=False)
    job_type = db.Column(db.String(50), nullable=False)  # 'folder_upload', 'batch_processing'
    status = db.Column(db.String(20), default='queued')  # queued, processing, completed, failed, cancelled, insufficient_credits
    
    # Progress tracking
    total_files = db.Column(db.Integer, default=0)
    processed_files = db.Column(db.Integer, default=0)
    failed_files = db.Column(db.Integer, default=0)
    skipped_files = db.Column(db.Integer, default=0)
    
    # Credit tracking
    estimated_credits = db.Column(db.Integer, default=0)
    credits_used = db.Column(db.Integer, default=0)
    
    # Job data
    folder_path = db.Column(db.String(500))  # For folder upload jobs
    error_message = db.Column(db.Text)
    result_data = db.Column(db.JSON)  # Store lists of processed/failed/skipped files
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='processing_jobs')
    project = db.relationship('Project', backref='processing_jobs')
    
    def __repr__(self):
        return f'<ProcessingJob {self.id}>'
    
    def get_progress_percentage(self):
        """Calculate progress percentage"""
        if self.total_files == 0:
            return 0
        return (self.processed_files + self.failed_files + self.skipped_files) / self.total_files * 100
    
    def get_estimated_time_remaining(self):
        """Estimate remaining time based on current progress"""
        if self.status != 'processing' or not self.started_at:
            return None
            
        elapsed = (datetime.utcnow() - self.started_at).total_seconds()
        progress = self.get_progress_percentage()
        
        if progress == 0:
            return None
            
        total_estimated_time = (elapsed / progress) * 100
        return max(0, total_estimated_time - elapsed)
    
    def update_progress(self, processed=0, failed=0, skipped=0, credits_used=0, absolute=False):
        """Update job progress with database retry logic
        
        Args:
            processed: Number of processed files (can be incremental or absolute)
            failed: Number of failed files (can be incremental or absolute)
            skipped: Number of skipped files (can be incremental or absolute)
            credits_used: Credits used (can be incremental or absolute)
            absolute: If True, values are absolute totals; if False, incremental changes
        """
        import time
        
        max_retries = 3
        retry_delay = 0.1
        
        for attempt in range(max_retries):
            try:
                if absolute:
                    # Set absolute values
                    self.processed_files = processed
                    self.failed_files = failed
                    self.skipped_files = skipped
                    self.credits_used = credits_used
                else:
                    # Add incremental values (original behavior)
                    if processed > 0:
                        self.processed_files += processed
                    if failed > 0:
                        self.failed_files += failed
                    if skipped > 0:
                        self.skipped_files += skipped
                    if credits_used > 0:
                        self.credits_used += credits_used
                    
                self.updated_at = datetime.utcnow()
                
                # Check if job is complete
                total_processed = self.processed_files + self.failed_files + self.skipped_files
                if total_processed >= self.total_files and self.status == 'processing':
                    self.status = 'completed'
                    self.completed_at = datetime.utcnow()
                
                db.session.commit()
                break  # Success, exit retry loop
                
            except Exception as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    db.session.rollback()  # Clear failed transaction
                    continue
                else:
                    # Last attempt or non-lock error, re-raise
                    db.session.rollback()
                    raise e
    
    def cancel(self, reason="User cancelled"):
        """Cancel the job"""
        self.status = 'cancelled'
        self.error_message = reason
        self.completed_at = datetime.utcnow()
        db.session.commit()
    
    def fail(self, error_message):
        """Mark job as failed"""
        self.status = 'failed'
        self.error_message = error_message
        self.completed_at = datetime.utcnow()
        db.session.commit()
    
    def start(self):
        """Mark job as started"""
        self.status = 'processing'
        self.started_at = datetime.utcnow()
        db.session.commit()
    
    def complete_with_error(self, error_message):
        """Complete job with error state"""
        self.status = 'failed'
        self.error_message = error_message
        self.completed_at = datetime.utcnow()
        db.session.commit()