import os
import json
import logging
from datetime import datetime
from flask import render_template, request, jsonify, redirect, url_for, abort, g
from werkzeug.utils import secure_filename
from app.projects import bp
from app.models import Project, Document, DataRecord
from app.extensions import db
from app.auth.decorators import login_required, active_required
from app.services.ai_service import AIService
from app.services.document_service import DocumentService
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)

@bp.route('/')
@login_required
def index():
    """List all user projects"""
    projects = Project.query.filter_by(user_id=g.user.id).all()
    return render_template('projects.html', projects=projects)


@bp.route('/storage-paths', methods=['GET'])
@login_required
def storage_paths():
    """Return allowed storage base paths for the current environment."""
    from app.utils.environment import get_allowed_browse_paths, get_default_storage_path

    allowed = []
    for path in get_allowed_browse_paths():
        try:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path) and os.access(abs_path, os.W_OK):
                allowed.append(abs_path)
        except Exception:
            continue

    # Ensure default path appears first when available
    default_base = os.path.abspath(get_default_storage_path())
    if default_base in allowed:
        allowed = [default_base] + [p for p in allowed if p != default_base]
    elif os.path.exists(default_base) and os.access(default_base, os.W_OK):
        allowed.insert(0, default_base)

    return jsonify({
        'success': True,
        'paths': allowed,
        'default_path': default_base if allowed else None
    })

@bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    """Create a new project"""
    if request.method == 'POST':
        data = request.json
        name = data.get('name')
        description = data.get('description', '')
        fields = data.get('fields', [])
        requested_storage_path = data.get('storage_path')

        if not name:
            return jsonify({'error': 'Project name is required'}), 400

        if not requested_storage_path:
            return jsonify({'error': 'Storage path is required'}), 400

        # SECURITY: Validate storage path is within allowed directories
        from app.utils.environment import get_allowed_browse_paths, is_cloud_environment

        # In cloud environments, force use of /tmp (don't rely on FLASK_ENV alone)
        if is_cloud_environment():
            # Ultra-strict mode: only /tmp and subdirectories
            allowed_base_paths = ['/tmp']
            storage_path = os.path.join('/tmp', 'DataGrabber', secure_filename(name))
            logger.info(f"Cloud mode: Forcing storage path to {storage_path}")
        else:
            # Local development: validate against allowed paths
            allowed_base_paths = get_allowed_browse_paths()

            # Validate requested path is within allowed directories
            path_allowed = False
            try:
                abs_requested = os.path.abspath(requested_storage_path)
                for allowed_path in allowed_base_paths:
                    abs_allowed = os.path.abspath(allowed_path)
                    if abs_requested.startswith(abs_allowed):
                        # Additional check: ensure the allowed path exists and is accessible
                        if os.path.exists(allowed_path) and os.access(allowed_path, os.W_OK):
                            path_allowed = True
                            storage_path = requested_storage_path
                            break
            except Exception as e:
                logger.warning(f"Path validation error: {e}")
                path_allowed = False

            if not path_allowed:
                # Fallback to safe default path
                from app.utils.environment import get_default_storage_path
                base_path = get_default_storage_path()
                storage_path = os.path.join(base_path, 'DataGrabber', secure_filename(name))
                logger.warning(f"Storage path {requested_storage_path} not allowed, using fallback: {storage_path}")
        
        provider, model = AIService.get_default_provider_and_model()
        if not provider or not model:
            return jsonify({'error': 'No AI provider available. Please check configuration.'}), 500
            
        try:
            project = Project(
                user_id=g.user.id,
                name=name,
                description=description,
                fields=fields,
                storage_path=storage_path,
                provider=provider,
                model=model
            )
            db.session.add(project)
            db.session.commit()
            
            # Create project directory
            os.makedirs(storage_path, exist_ok=True)
            
            # Save template file
            template_data = {
                "name": name,
                "description": description,
                "fields": fields,
                "provider": provider,
                "model": model
            }
            template_path = os.path.join(storage_path, "project_template.json")
            with open(template_path, "w", encoding="utf-8") as f:
                json.dump(template_data, f, indent=2)
            
            # Create Excel file with headers
            import pandas as pd
            excel_path = os.path.join(storage_path, "extracted_data.xlsx")
            field_names = [field['name'] for field in fields]
            df = pd.DataFrame(columns=field_names + ['filename', 'extracted_date'])
            df.to_excel(excel_path, index=False)
            
            return jsonify({'success': True, 'project_id': project.id})
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500
    
    return render_template('new_project.html')

@bp.route('/<project_id>')
@login_required
def view(project_id):
    """View a specific project"""
    project = Project.query.get(project_id)
    if not project or project.user_id != g.user.id:
        abort(404)
    
    documents = Document.query.filter_by(project_id=project.id).all()
    data_records = DataRecord.query.join(Document).filter(Document.project_id == project.id).all()
    
    # Load extracted data from Excel file and merge with database metadata
    extracted_data_list = []
    try:
        import pandas as pd
        excel_path = os.path.join(project.storage_path, "extracted_data.xlsx")
        if os.path.exists(excel_path):
            df = pd.read_excel(excel_path)
            # Convert DataFrame to list of dictionaries
            excel_data = df.to_dict('records')
            
            # Create a mapping of filename to document for efficient lookup
            filename_to_doc = {doc.filename: doc for doc in documents}
            
            # Merge Excel data with database metadata
            for i, excel_row in enumerate(excel_data):
                # Find the corresponding database record
                filename = excel_row.get('filename', '')
                doc = filename_to_doc.get(filename)
                
                # Create merged record with both Excel data and metadata
                merged_record = excel_row.copy()
                
                # Add metadata from database if available
                if doc and i < len(data_records):
                    db_record = data_records[i] if i < len(data_records) else None
                    if db_record:
                        merged_record['id'] = db_record.id
                        merged_record['document_id'] = db_record.document_id
                        merged_record['created_at'] = db_record.created_at
                    else:
                        # Fallback values
                        merged_record['id'] = f"excel_{i}"
                        merged_record['document_id'] = doc.id if doc else None
                        merged_record['created_at'] = doc.created_at if doc else None
                else:
                    # Fallback values for missing records
                    merged_record['id'] = f"excel_{i}"
                    merged_record['document_id'] = None
                    merged_record['created_at'] = None
                    
                extracted_data_list.append(merged_record)
        else:
            # No Excel file exists, use database records
            for record in data_records:
                record_data = record.get_data()
                if record_data:
                    record_data['id'] = record.id
                    record_data['document_id'] = record.document_id
                    record_data['created_at'] = record.created_at
                    extracted_data_list.append(record_data)
    except Exception as e:
        logger.error(f"Error loading extracted data from Excel: {e}")
        # Fallback: Load data using the get_data() method 
        for record in data_records:
            record_data = record.get_data()
            if record_data:
                record_data['id'] = record.id
                record_data['document_id'] = record.document_id  
                record_data['created_at'] = record.created_at
                extracted_data_list.append(record_data)
    
    # Format storage path for display
    storage_path_display = StorageService.format_path_for_display(project.storage_path)
    
    return render_template(
        'project.html', 
        project=project, 
        documents=documents, 
        data_records=extracted_data_list,  # Now contains Excel data
        storage_path_display=storage_path_display
    )

@bp.route('/<project_id>/upload', methods=['POST'])
@login_required
@active_required
def upload(project_id):
    """Upload documents to a project"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Upload request received for project {project_id}")
    
    project = Project.query.get(project_id)
    if not project or project.user_id != g.user.id:
        logger.error(f"Project {project_id} not found or access denied")
        abort(404)

    # SECURITY: Validate project storage path is safe
    from app.utils.environment import get_allowed_browse_paths, is_cloud_environment

    # Check if storage path is within allowed directories
    path_safe = False
    if is_cloud_environment():
        # In cloud, only allow /tmp paths
        if project.storage_path.startswith('/tmp'):
            path_safe = True
    else:
        # In development, check against allowed paths
        allowed_paths = get_allowed_browse_paths()
        try:
            abs_storage = os.path.abspath(project.storage_path)
            for allowed_path in allowed_paths:
                abs_allowed = os.path.abspath(allowed_path)
                if abs_storage.startswith(abs_allowed):
                    if os.path.exists(allowed_path) and os.access(allowed_path, os.W_OK):
                        path_safe = True
                        break
        except Exception as e:
            logger.warning(f"Storage path validation error: {e}")

    if not path_safe:
        logger.error(f"Project storage path {project.storage_path} is not in allowed directories")
        return jsonify({'error': 'Project storage path is not accessible in this environment'}), 403
    
    if 'files[]' not in request.files:
        logger.error("No files[] in request.files")
        return jsonify({'error': 'No files uploaded'}), 400
    
    files = request.files.getlist('files[]')
    logger.info(f"Received {len(files)} files")
    
    if not files:
        return jsonify({'error': 'No selected files'}), 400
    
    if logger.isEnabledFor(logging.DEBUG):
        for i, file in enumerate(files[:5]):  # Log first 5 only
            logger.debug(f"File {i}: {file.filename}")
        if len(files) > 5:
            logger.debug(f"... and {len(files) - 5} more")
    
    # Save files temporarily and queue for background processing
    try:
        logger.info("Starting file upload and queuing for background processing...")
        
        # Save uploaded files temporarily
        temp_file_paths = []
        abs_storage_path = os.path.abspath(project.storage_path)
        os.makedirs(abs_storage_path, exist_ok=True)
        
        for file in files:
            if file.filename:
                temp_path = os.path.abspath(os.path.join(abs_storage_path, secure_filename(file.filename)))
                file.save(temp_path)
                temp_file_paths.append(temp_path)
        
        if not temp_file_paths:
            return jsonify({'error': 'No valid files to process'}), 400
        
        # Queue files for background processing with progress tracking
        from app.services.background_processor import background_processor
        result = background_processor.queue_file_processing(
            project_id=project.id,
            file_paths=temp_file_paths,
            user_id=g.user.id
        )
        
        logger.info(f"File processing queued: {result}")
        
        if result['success']:
            return jsonify({
                'success': True,
                'job_queued': True,
                'job_id': result['job_id'],
                'estimated_credits': result['estimated_credits'],
                'total_files': result['total_files']
            })
        else:
            # Clean up temp files on error
            for temp_path in temp_file_paths:
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                except:
                    pass
            
            if result.get('error') == 'insufficient_credits':
                return jsonify({
                    'success': False,
                    'needs_purchase': True,
                    'required_credits': result.get('required_credits', 0),
                    'current_credits': result.get('current_credits', 0),
                    'error': result.get('message', 'Not enough credits')
                }), 400
            else:
                return jsonify({'error': result.get('error', 'Unknown error')}), 500
        
    except Exception as e:
        logger.error(f"Error processing file upload: {e}", exc_info=True)
        # Clean up temp files on error
        for temp_path in temp_file_paths:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except:
                pass
        return jsonify({'error': str(e)}), 500
# Server-side folder browsing routes removed
# These have been replaced with client-side folder selection
# using HTML5 directory input capabilities
    
@bp.route('/<project_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(project_id):
    """Edit a project"""
    project = Project.query.get(project_id)
    if not project or project.user_id != g.user.id:
        abort(404)
    
    if request.method == 'POST':
        data = request.json
        project.name = data.get('name', project.name)
        project.description = data.get('description', project.description)
        project.fields = data.get('fields', project.fields)
        
        try:
            db.session.commit()
            return jsonify({'success': True})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500
    
    return render_template('edit_project.html', project=project)

@bp.route('/<project_id>/delete', methods=['POST'])
@login_required
def delete(project_id):
    """Delete a project"""
    project = Project.query.get(project_id)
    if not project or project.user_id != g.user.id:
        abort(404)
    
    try:
        data = request.json
        delete_files = data.get('delete_files', False)
        
        # Import ProcessingJob model
        from app.models.processing_job import ProcessingJob
        
        # Delete associated processing jobs first (to avoid foreign key constraint)
        ProcessingJob.query.filter_by(project_id=project.id).delete()
        
        # Delete associated documents and data records
        documents = Document.query.filter_by(project_id=project.id).all()
        for doc in documents:
            DataRecord.query.filter_by(document_id=doc.id).delete()
            db.session.delete(doc)
        
        # Update Excel file to remove all project data
        import pandas as pd
        excel_path = os.path.join(project.storage_path, "extracted_data.xlsx")
        if os.path.exists(excel_path):
            try:
                # Simply remove the file since we're deleting the entire project
                os.remove(excel_path)
                import logging
                logging.info(f"Removed Excel file: {excel_path}")
            except Exception as excel_error:
                import logging
                logging.error(f"Error removing Excel file {excel_path}: {excel_error}")
        
        # Delete the project
        db.session.delete(project)
        db.session.commit()
        
        # Optionally delete files from storage
        if delete_files and project.storage_path and os.path.exists(project.storage_path):
            import shutil
            shutil.rmtree(project.storage_path, ignore_errors=True)
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
    
@bp.route('/documents/bulk-delete', methods=['POST'])
@login_required
def bulk_delete_documents():
    """Bulk delete documents and their data (processed or not)"""
    document_ids = request.json.get('document_ids', [])
    if not document_ids:
        return jsonify({'success': False, 'error': 'No documents selected'}), 400

    try:
        import pandas as pd
        docs = Document.query.filter(Document.id.in_(document_ids)).all()
        projects_to_update = {}
        filenames_to_remove = []
        
        for doc in docs:
            # Only delete if user owns the project
            if doc.project.user_id != g.user.id:
                continue
                
            project = doc.project
            if project.id not in projects_to_update:
                projects_to_update[project.id] = {
                    'project': project,
                    'filenames': []
                }
            
            # Store filename for Excel removal
            filenames_to_remove.append(doc.filename)
            projects_to_update[project.id]['filenames'].append(doc.filename)
            
            # Delete the document (cascades to data records)
            db.session.delete(doc)
        
        # Update Excel files for each project
        for project_id, project_data in projects_to_update.items():
            project = project_data['project']
            filenames = project_data['filenames']
            
            excel_path = os.path.join(project.storage_path, "extracted_data.xlsx")
            if os.path.exists(excel_path):
                try:
                    # Read Excel file
                    df = pd.read_excel(excel_path)
                    
                    # Remove rows with matching filenames
                    df_filtered = df[~df['filename'].isin(filenames)]
                    
                    # Save updated Excel file
                    df_filtered.to_excel(excel_path, index=False)
                    
                    # Log the update
                    import logging
                    logging.info(f"Removed {len(filenames)} document records from {excel_path}")
                    
                except Exception as excel_error:
                    import logging
                    logging.error(f"Error updating Excel file {excel_path}: {excel_error}")
                    # Continue with database commit even if Excel update fails
        
        db.session.commit()
        return jsonify({'success': True, 'message': f'Deleted {len(filenames_to_remove)} documents and their data'})
        
    except Exception as e:
        db.session.rollback()
        import logging
        logging.error(f"Error in bulk_delete_documents: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/data/bulk-delete', methods=['POST'])
@login_required
def bulk_delete_data_records():
    """Bulk delete data records and update Excel file"""
    record_ids = request.json.get('record_ids', [])
    if not record_ids:
        return jsonify({'success': False, 'error': 'No records selected'}), 400

    try:
        import pandas as pd
        records = DataRecord.query.filter(DataRecord.id.in_(record_ids)).all()
        projects_to_update = {}
        filenames_to_remove = []
        
        documents_to_delete = []
        
        for record in records:
            # Ensure user owns the project
            if record.document.project.user_id != g.user.id:
                continue
            
            project = record.document.project
            if project.id not in projects_to_update:
                projects_to_update[project.id] = {
                    'project': project,
                    'filenames': []
                }
            
            # Store filename for Excel removal
            filenames_to_remove.append(record.document.filename)
            projects_to_update[project.id]['filenames'].append(record.document.filename)
            
            # Store document for deletion to avoid conflicts
            documents_to_delete.append(record.document)
            
            # Delete the data record first
            db.session.delete(record)
        
        # Delete corresponding documents to avoid orphaned records
        for document in documents_to_delete:
            db.session.delete(document)
        
        # Update Excel files for each project
        for project_id, project_data in projects_to_update.items():
            project = project_data['project']
            filenames = project_data['filenames']
            
            excel_path = os.path.join(project.storage_path, "extracted_data.xlsx")
            if os.path.exists(excel_path):
                try:
                    # Read Excel file
                    df = pd.read_excel(excel_path)
                    
                    # Remove rows with matching filenames
                    df_filtered = df[~df['filename'].isin(filenames)]
                    
                    # Save updated Excel file
                    df_filtered.to_excel(excel_path, index=False)
                    
                    # Log the update
                    import logging
                    logging.info(f"Removed {len(filenames)} records from {excel_path}")
                    
                except Exception as excel_error:
                    import logging
                    logging.error(f"Error updating Excel file {excel_path}: {excel_error}")
                    # Continue with database commit even if Excel update fails
            
        db.session.commit()
        return jsonify({'success': True, 'message': f'Deleted {len(filenames_to_remove)} records'})
        
    except Exception as e:
        db.session.rollback()
        import logging
        logging.error(f"Error in bulk_delete_data_records: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/data/<record_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_data_record(record_id):
    """Edit a data record"""
    record = DataRecord.query.get(record_id)
    if not record:
        abort(404)
    
    document = record.document
    project = document.project
    
    # Check if the user owns the project
    if project.user_id != g.user.id:
        abort(403)
    
    if request.method == 'POST':
        data = request.json
        record.updated_at = datetime.utcnow()
        
        try:
            # Update data in Excel file instead of database
            import pandas as pd
            excel_path = os.path.join(project.storage_path, "extracted_data.xlsx")
            
            if os.path.exists(excel_path):
                df = pd.read_excel(excel_path)
                # Find the row with this document's filename
                mask = df['filename'] == document.filename
                if mask.any():
                    # Update the row with new data
                    for field_name, value in data.items():
                        if field_name in df.columns:
                            df.loc[mask, field_name] = value
                    
                    # Update the extracted_date to reflect modification
                    df.loc[mask, 'extracted_date'] = datetime.utcnow().isoformat()
                    
                    # Save back to Excel file
                    df.to_excel(excel_path, index=False)
            
            db.session.commit()
            return jsonify({'success': True})
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating record {record.id}: {e}")
            return jsonify({'error': str(e)}), 500
    
    return render_template(
        'edit_record.html', 
        record=record, 
        document=document, 
        project=project
    )

@bp.route('/data/<record_id>/delete', methods=['POST'])
@login_required
def delete_data_record(record_id):
    """Delete a data record and its corresponding document"""
    record = DataRecord.query.get(record_id)
    if not record:
        abort(404)
    
    document = record.document
    project = document.project
    
    # Check if the user owns the project
    if project.user_id != g.user.id:
        abort(403)
    
    try:
        import pandas as pd
        filename_to_remove = document.filename
        
        # Update Excel file first
        excel_path = os.path.join(project.storage_path, "extracted_data.xlsx")
        if os.path.exists(excel_path):
            try:
                # Read Excel file
                df = pd.read_excel(excel_path)
                
                # Remove row with matching filename
                df_filtered = df[df['filename'] != filename_to_remove]
                
                # Save updated Excel file
                df_filtered.to_excel(excel_path, index=False)
                
                # Log the update
                import logging
                logging.info(f"Removed record for {filename_to_remove} from {excel_path}")
                
            except Exception as excel_error:
                import logging
                logging.error(f"Error updating Excel file {excel_path}: {excel_error}")
                # Continue with database operation even if Excel update fails
        
        # Delete the data record first (due to foreign key constraint)
        db.session.delete(record)
        # Delete the corresponding document
        db.session.delete(document)
        db.session.commit()
        return jsonify({'success': True, 'message': f'Deleted record for {filename_to_remove}'})
        
    except Exception as e:
        db.session.rollback()
        import logging
        logging.error(f"Error in delete_data_record: {e}")
        return jsonify({'error': str(e)}), 500
    
@bp.route('/<project_id>/export', methods=['GET'])
@login_required
def export_project_data(project_id):
    """Export all data from a project as CSV or Excel"""
    project = Project.query.get(project_id)
    if not project or project.user_id != g.user.id:
        abort(404)
    
    format_type = request.args.get('format', 'csv')
    
    # Get all records for this project from Excel file
    records = []
    try:
        import pandas as pd
        excel_path = os.path.join(project.storage_path, "extracted_data.xlsx")
        if os.path.exists(excel_path):
            df = pd.read_excel(excel_path)
            records = df.to_dict('records')
    except Exception as e:
        logger.error(f"Error reading Excel data for export: {e}")
        # Fallback: try to get data using the new method
        for doc in project.documents:
            for record in doc.data_records:
                record_data = record.get_data()
                if record_data:  # Only add if data was successfully retrieved
                    record_data['filename'] = doc.filename
                    record_data['extracted_date'] = record.created_at.isoformat()
                    records.append(record_data)
    
    if not records:
        return jsonify({'error': 'No data to export'}), 400
    
    # Create DataFrame
    import pandas as pd
    import io
    from flask import send_file
    
    df = pd.DataFrame(records)
    
    # Create output file
    output = io.BytesIO()
    
    if format_type == 'excel':
        # Save as Excel
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name=project.name)
        output.seek(0)
        return send_file(
            output, 
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f"{project.name}_data.xlsx"
        )
    else:
        # Save as CSV
        df.to_csv(output, index=False)
        output.seek(0)
        return send_file(
            output,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f"{project.name}_data.csv"
        )
    
# Batch upload route removed - replaced by client-side folder selection
# Folders are now handled by the regular upload endpoint with multiple files

@bp.route('/<project_id>/job-status/<job_id>')
@login_required
def job_status(project_id, job_id):
    """Get the status of a processing job"""
    project = Project.query.get(project_id)
    if not project or project.user_id != g.user.id:
        abort(404)
    
    from app.services.background_processor import background_processor
    
    status = background_processor.get_job_status(job_id)
    if 'error' in status:
        return jsonify(status), 404
    
    return jsonify(status)

@bp.route('/<project_id>/jobs-status', methods=['POST'])
@login_required
def jobs_status(project_id):
    """Aggregate status for multiple job IDs (used by chunked folder uploads).
    Body: {"job_ids": ["id1", "id2", ...]}
    Returns counts merged across all jobs so the client only needs one poll request.
    """
    project = Project.query.get(project_id)
    if not project or project.user_id != g.user.id:
        abort(404)

    job_ids = (request.get_json(silent=True) or {}).get('job_ids', [])
    if not job_ids:
        return jsonify({'error': 'No job_ids provided'}), 400

    from app.models.processing_job import ProcessingJob
    TERMINAL = {'completed', 'failed', 'cancelled'}

    jobs = ProcessingJob.query.filter(
        ProcessingJob.id.in_(job_ids),
        ProcessingJob.project_id == project_id
    ).all()

    total_files     = sum(j.total_files     or 0 for j in jobs)
    processed_files = sum(j.processed_files or 0 for j in jobs)
    failed_files    = sum(j.failed_files    or 0 for j in jobs)
    active_jobs     = [j for j in jobs if j.status not in TERMINAL]

    progress_pct = int(processed_files / total_files * 100) if total_files > 0 else 0

    return jsonify({
        'all_done':          len(active_jobs) == 0,
        'active_jobs':       len(active_jobs),
        'total_jobs':        len(jobs),
        'total_files':       total_files,
        'processed_files':   processed_files,
        'failed_files':      failed_files,
        'progress_percentage': progress_pct,
    })


@bp.route('/<project_id>/cancel-job/<job_id>', methods=['POST'])
@login_required
def cancel_job(project_id, job_id):
    """Cancel a processing job"""
    project = Project.query.get(project_id)
    if not project or project.user_id != g.user.id:
        abort(404)
    
    from app.services.background_processor import background_processor
    
    result = background_processor.cancel_job(job_id, g.user.id)
    if 'error' in result:
        return jsonify(result), 400
    
    return jsonify(result)