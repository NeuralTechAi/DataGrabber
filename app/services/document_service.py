# In app/services/document_service.py
import os
import logging
from typing import Dict, List
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import current_app
from app.models import Document, DataRecord, Project
from app.extensions import db
from app.services.ai_service import AIService
import google.generativeai as genai

logger = logging.getLogger(__name__)

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    logger.warning("Pandas not available, data export will be limited")


class DocumentService:
    """Service for document processing operations"""

    @staticmethod
    def extract_text_from_pdf(pdf_file_path: str) -> str:
        """Extract text from a PDF file with page numbers"""
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(pdf_file_path)
            text = ""
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                page_text = page.get_text()
                text += f"Page {page_num + 1}:\n{page_text}\n\n"
            doc.close()
            return text
        except Exception as e:
            logger.error(f"Error extracting text from PDF {pdf_file_path}: {e}")
            return ""
    
    @staticmethod
    def get_pdf_page_count(pdf_file_path: str) -> int:
        """Get the number of pages in a PDF file"""
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(pdf_file_path)
            page_count = len(doc)
            doc.close()
            return page_count
        except Exception as e:
            logger.error(f"Error getting PDF page count {pdf_file_path}: {e}")
            return 1
    
    @staticmethod
    def _extract_text_from_txt_file(file_path: str) -> str:
        """Extract text from a plain text file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return content
        except UnicodeDecodeError:
            # Try with different encoding if UTF-8 fails
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    content = f.read()
                return content
            except Exception as e:
                logger.error(f"Error reading text file with latin-1 encoding {file_path}: {e}")
                raise
        except Exception as e:
            logger.error(f"Error reading text file {file_path}: {e}")
            raise
    
    @staticmethod
    def extract_text_from_file(file_path: str, file_type: str = None) -> str:
        """Extract text from any supported file type using the best available AI service"""
        try:
            # Determine file_type if not provided
            if file_type is None:
                if '.' in file_path:
                    file_ext = file_path.rsplit('.', 1)[1].lower()
                    file_type = DocumentService._get_file_type_category(file_ext)
                else:
                    file_type = 'document'  # Default to document if no extension
            
            # Log file info for debugging
            logger.debug(f"Extracting text from file: {file_path}, detected type: {file_type}")
            
            # For .txt files, read directly without AI processing
            if file_type == 'document' and file_path.lower().endswith('.txt'):
                return DocumentService._extract_text_from_txt_file(file_path)
            
            # Use Gemini as default if available (supports all file types)
            if current_app.config.get('GEMINI_API_KEY'):
                return DocumentService._extract_text_from_file_with_gemini(file_path, file_type)
            elif current_app.config.get('OPENAI_API_KEY') and file_type in ['image', 'pdf']:
                # OpenAI only supports images and PDFs
                return DocumentService._extract_text_from_image_with_openai(file_path)
            elif current_app.config.get('ANTHROPIC_API_KEY') and hasattr(DocumentService, '_extract_text_from_image_with_anthropic'):
                # Only call if method exists
                return DocumentService._extract_text_from_image_with_anthropic(file_path)
            else:
                logger.warning(f"No AI service available for file text extraction of type: {file_type}")
                return f"No text extraction service available for {file_type} files"
        except Exception as e:
            logger.error(f"Error extracting text from file {file_path} (type: {file_type}): {e}")
            return f"Error extracting text: {str(e)}"
    
    @staticmethod
    def extract_text_from_image(image_file_path: str) -> str:
        """Extract text from an image using the best available AI service (deprecated - use extract_text_from_file)"""
        # Get file extension to determine type more accurately
        if '.' in image_file_path:
            file_ext = image_file_path.rsplit('.', 1)[1].lower()
            if file_ext in ['jpg', 'jpeg', 'png', 'webp', 'bmp', 'gif']:
                file_type = 'image'
            else:
                file_type = DocumentService._get_file_type_category(file_ext)
        else:
            file_type = 'image'  # Default if no extension
            
        logger.debug(f"extract_text_from_image: Processing {image_file_path} as type: {file_type}")
        return DocumentService.extract_text_from_file(image_file_path, file_type)
    
    @staticmethod
    def _extract_text_from_image_with_openai(image_file_path: str) -> str:
        """Extract text from an image using OpenAI Vision"""
        try:
            from openai import OpenAI
            import base64
            
            client = OpenAI(api_key=current_app.config['OPENAI_API_KEY'])
            
            with open(image_file_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text", 
                                "text": "Please analyze this image and extract all visible text. Format it in a readable way."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error with OpenAI vision: {e}")
            raise
    
    @staticmethod
    def _extract_text_from_file_with_gemini(file_path: str, file_type: str) -> str:
        """Extract text from any file type using Google Gemini with upload_file"""
        try:
            # Configure Gemini API
            genai.configure(api_key=current_app.config['GEMINI_API_KEY'])
            
            # Initialize the model with default or configured model
            model_name = current_app.config.get('AI_MODEL', 'gemini-1.5-flash')
            model = genai.GenerativeModel(model_name=model_name)
            
            # Upload the file (works for all supported formats)
            uploaded_file = genai.upload_file(path=file_path)
            
            # Generate context-specific prompts
            context_prompts = {
                'document': "Extract and transcribe all text content from this document, preserving formatting and structure.",
                'image': "Analyze this image and extract all visible text. Format it in a readable way and preserve the structure where possible.",
                'data': "Extract and transcribe the data from this file, including column headers, row data, and any text content.",
                'audio': "Transcribe the spoken content from this audio file into text format.",
                'video': "Extract and transcribe any visible text, captions, or spoken content from this video file.",
                'code': "Extract and transcribe the code content, including comments and documentation.",
                'archive': "Analyze the contents of this archive and provide a summary of the files and any extractable text content.",
                'pdf': "Extract and transcribe all text content from this PDF, including text from all pages and any embedded content."
            }
            
            prompt = context_prompts.get(file_type, "Extract and transcribe all readable text content from this file.")
            
            # Generate content to extract text
            response = model.generate_content([prompt, uploaded_file])
            
            return response.text
            
        except Exception as e:
            logger.error(f"Error with Gemini file processing: {e}")
            raise
    
    @staticmethod
    def _extract_text_from_image_with_gemini(image_file_path: str) -> str:
        """Extract text from an image using Google Gemini with upload_file (deprecated - use _extract_text_from_file_with_gemini)"""
        return DocumentService._extract_text_from_file_with_gemini(image_file_path, 'image')
    
    @staticmethod
    def _extract_text_from_image_with_anthropic(image_file_path: str) -> str:
        """Extract text from an image using Anthropic Claude's vision capabilities"""
        try:
            import base64
            from anthropic import Anthropic
            
            client = Anthropic(api_key=current_app.config['ANTHROPIC_API_KEY'])
            
            with open(image_file_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Determine content type based on extension
            file_ext = image_file_path.lower().rsplit('.', 1)[-1] if '.' in image_file_path else 'jpg'
            mime_type = f"image/{file_ext}" if file_ext != 'jpg' else "image/jpeg"
            
            message = client.messages.create(
                model=current_app.config.get('AI_MODEL', 'claude-3-sonnet-20240229'),
                max_tokens=1000,
                temperature=0,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Please analyze this image and extract all visible text. Format it in a readable way."
                            },
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": mime_type,
                                    "data": base64_image
                                }
                            }
                        ]
                    }
                ]
            )
            
            return message.content[0].text
            
        except Exception as e:
            logger.error(f"Error with Anthropic vision processing: {e}")
            raise
    
    @staticmethod
    def _get_file_type_category(file_ext: str) -> str:
        """Categorize file extension into broader types for processing"""
        file_ext = file_ext.lower()
        
        # Document types
        if file_ext in ['pdf', 'txt', 'doc', 'docx', 'rtf', 'dot', 'dotx', 'hwp', 'hwpx']:
            return 'document'
        
        # Image types
        elif file_ext in ['jpg', 'jpeg', 'png', 'webp', 'bmp', 'gif']:
            return 'image'
            
        # Data types
        elif file_ext in ['xls', 'xlsx', 'csv', 'tsv']:
            return 'data'
            
        # Audio types
        elif file_ext in ['mp3', 'wav', 'aiff', 'aac', 'ogg', 'flac']:
            return 'audio'
            
        # Video types
        elif file_ext in ['mp4', 'mov', 'avi', 'flv', 'mpg', 'mpeg', 'webm', 'wmv', '3gpp']:
            return 'video'
            
        # Code types
        elif file_ext in ['js', 'html', 'css', 'md', 'yaml', 'yml', 'json', 'xml', 'py', 'cpp', 'java']:
            return 'code'
            
        # Archive types
        elif file_ext in ['zip']:
            return 'archive'
            
        # Default to document for unknown types
        else:
            return 'document'
    
    @staticmethod
    def process_document(document_id: str) -> bool:
        try:
            document = Document.query.get(document_id)
            if not document:
                logger.error(f"Document {document_id} not found")
                return False

            project = document.project

            # Enhanced logging for document processing
            file_exists = os.path.exists(document.file_path)
            logger.info(f"Processing document {document.filename} (type: {document.file_type}) - File exists: {file_exists}")
            
            # Detailed diagnostics for the file
            if file_exists:
                file_size = os.path.getsize(document.file_path)
                file_ext = document.filename.rsplit('.', 1)[1].lower() if '.' in document.filename else 'unknown'
                
                logger.info(f"File details: {document.filename} (extension: {file_ext}, type: {document.file_type}, size: {file_size} bytes)")
                
                # Special logging for image files
                if document.file_type == 'image':
                    logger.info(f"IMAGE FILE PROCESSING: {document.filename} (size: {file_size} bytes, path: {document.file_path})")
                    # Check if file is potentially valid 
                    if file_size < 100:
                        logger.warning(f"WARNING: Image file is suspiciously small: {document.filename} ({file_size} bytes)")
            else:
                logger.error(f"File not found: {document.file_path}")
                return False
            
            # Extract data with better error handling (use project owner's AI settings)
            try:
                from app.models import User
                user = User.query.get(project.user_id)
                extracted_data_list = AIService.extract_data_with_ai(
                    document.file_path, project.fields, document.file_type, user=user
                )
                
                # Check if we received an error response
                if (isinstance(extracted_data_list, list) and len(extracted_data_list) > 0 and 
                    isinstance(extracted_data_list[0], dict) and "error" in extracted_data_list[0]):
                    error_msg = extracted_data_list[0].get("error", "Unknown error")
                    logger.error(f"AI extraction error for {document.filename}: {error_msg}")
                    # Continue processing anyway, with error messages as field values
                
                logger.info(f"Extracted data for {document.filename}: {len(extracted_data_list) if isinstance(extracted_data_list, list) else 1} records")
                
                # Enhanced debug logging for extracted data
                if isinstance(extracted_data_list, list) and len(extracted_data_list) > 0:
                    first_record = extracted_data_list[0]
                    # Check if there are actual values in the data
                    has_actual_values = any(
                        v and v != "Not found" and not v.startswith("Error:") 
                        for v in first_record.values() if isinstance(v, str)
                    )
                    
                    logger.debug(f"Sample extracted data for {document.filename}: {str(first_record)[:300]}...")
                    
                    if not has_actual_values:
                        logger.warning(f"No meaningful data extracted from {document.filename} - all fields empty or 'Not found'")
                        
                elif isinstance(extracted_data_list, dict):
                    logger.debug(f"Extracted data for {document.filename}: {str(extracted_data_list)[:300]}...")
            except Exception as extraction_error:
                logger.error(f"Critical error during AI extraction for {document.filename}: {extraction_error}", exc_info=True)
                # Create an error response to continue processing
                extracted_data_list = [{field['name']: f"Extraction error: {str(extraction_error)}" for field in project.fields}]

            # If it's a single dict (image), wrap in a list for consistency
            if isinstance(extracted_data_list, dict):
                extracted_data_list = [extracted_data_list]
                
            # Check for empty or None results
            if not extracted_data_list:
                logger.error(f"No data extracted from {document.filename} - AI returned empty result")
                extracted_data_list = [{field['name']: "No data returned" for field in project.fields}]

            # Merge all page dicts into one: for each field, join values with newlines
            merged_data = {}
            for field in project.fields:
                field_name = field['name']
                # Handle potential error messages in field values
                values = []
                for page_data in extracted_data_list:
                    if page_data and isinstance(page_data, dict):
                        value = page_data.get(field_name, '')
                        if value and value.lower() != "not found" and not value.startswith("Error:"):
                            values.append(value)
                
                merged_data[field_name] = "\n".join(values) if values else "Not found"

            # Create DataRecord without storing data in database
            # Data will be retrieved from Excel file using get_data() method
            data_record = DataRecord(
                document_id=document.id
                # data column removed - data stored in Excel file only
            )
            db.session.add(data_record)

            # --- Append results into Excel file ---
            try:
                excel_path = os.path.join(project.storage_path, "extracted_data.xlsx")
                row = {k: merged_data.get(k, "") for k in [field['name'] for field in project.fields]}
                row['filename'] = document.filename
                row['extracted_date'] = datetime.utcnow().isoformat()

                if os.path.exists(excel_path):
                    df = pd.read_excel(excel_path)
                    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
                else:
                    df = pd.DataFrame([row])

                df.to_excel(excel_path, index=False)
                logger.info(f"Successfully updated Excel file with data from {document.filename}")
            except Exception as e:
                logger.error(f"Failed to update Excel file for project {project.id}: {e}", exc_info=True)

            # --- Clean up: Only delete copied files, preserve originals ---
            try:
                # Only delete if file is in project storage (copied file)
                # Don't delete if file is in original folder location
                project_storage = os.path.abspath(project.storage_path)
                file_location = os.path.abspath(document.file_path) if document.file_path else ""
                
                # Check if file is within project storage directory
                is_copied_file = file_location.startswith(project_storage)
                
                if is_copied_file and os.path.exists(document.file_path):
                    os.remove(document.file_path)
                    logger.info(f"Deleted copied document file: {document.file_path}")
                    # Update document record to reflect file has been processed and removed
                    document.file_path = ""  # Set to empty string to indicate file was processed and removed
                elif not is_copied_file:
                    logger.info(f"Preserving original file: {document.file_path}")
                    # Keep the original path for reference, but mark as processed
            except Exception as e:
                logger.error(f"Error during file cleanup for {document.file_path}: {e}", exc_info=True)

            # Mark document as processed (remains true even if extracted data is later deleted)
            document.processed = True
            logger.info(f"Document {document.filename} marked as processed")

            db.session.commit()
            return True

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error processing document {document_id}: {e}", exc_info=True)
            return False

    
    @staticmethod
    def process_uploaded_files(project: Project, files: List, user) -> Dict:
        """Process multiple uploaded files for a project - SEQUENTIAL VERSION"""
        # Expanded list of file types supported by Google Gemini upload_file
        allowed_extensions = {
            # Documents
            'pdf', 'txt', 'doc', 'docx', 'rtf', 'dot', 'dotx', 'hwp', 'hwpx',
            # Images  
            'jpg', 'jpeg', 'png', 'webp', 'bmp', 'gif',
            # Data files
            'xls', 'xlsx', 'csv', 'tsv',
            # Audio files
            'mp3', 'wav', 'aiff', 'aac', 'ogg', 'flac',
            # Video files
            'mp4', 'mov', 'avi', 'flv', 'mpg', 'mpeg', 'webm', 'wmv', '3gpp',
            # Code files
            'js', 'html', 'css', 'md', 'yaml', 'yml', 'json', 'xml', 'py', 'cpp', 'java',
            # Archives
            'zip'
        }
        valid_files = []
        skipped_files = []
        invalid_files = []
        total_pages = 0
        # Credits/pricing removed – total_pages is now informational only
        
        try:
            logger.info(f"Starting processing of {len(files)} uploaded files for project {project.id}")
            
            # Validate files and calculate total cost
            for file in files:
                if not file.filename:
                    logger.warning("Skipping file with empty filename")
                    continue
                    
                logger.info(f"Processing uploaded file: {file.filename}")
                
                file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
                if file_ext not in allowed_extensions:
                    logger.warning(f"Skipping file with unsupported extension: {file.filename} (ext: {file_ext})")
                    invalid_files.append(file.filename)
                    continue
                
                # Skip if this file is already processed for this project
                existing_doc = Document.query.filter_by(project_id=project.id, filename=file.filename).first()
                if existing_doc:
                    if existing_doc.processed:
                        logger.info(f"Regular upload: Skipping {file.filename} - already processed successfully")
                        skipped_files.append(file.filename)
                    else:
                        logger.info(f"Regular upload: Skipping {file.filename} - already exists but not yet processed")
                        skipped_files.append(file.filename)
                    continue
                
                # Create storage directory if it doesn't exist
                abs_storage_path = os.path.abspath(project.storage_path)
                os.makedirs(abs_storage_path, exist_ok=True)
                
                # Save file with secure filename
                secure_name = secure_filename(file.filename)
                temp_path = os.path.abspath(os.path.join(abs_storage_path, secure_name))
                
                try:
                    file.save(temp_path)
                    file_size = os.path.getsize(temp_path)
                    logger.info(f"Saved file: {file.filename} as {secure_name} (size: {file_size} bytes)")
                    
                    # Validate file was saved properly
                    if not os.path.exists(temp_path) or os.path.getsize(temp_path) == 0:
                        logger.error(f"Failed to save file properly: {file.filename} (empty or missing)")
                        invalid_files.append(file.filename)
                        continue
                except Exception as save_error:
                    logger.error(f"Error saving file {file.filename}: {save_error}")
                    invalid_files.append(file.filename)
                    continue
                
                # Get page count based on file type
                pages = 1  # Default to 1 page
                try:
                    if file_ext == 'pdf':
                        pages = DocumentService.get_pdf_page_count(temp_path)
                        logger.info(f"PDF page count for {file.filename}: {pages}")
                except Exception as page_error:
                    logger.warning(f"Error getting page count for {file.filename}, using default of 1: {page_error}")
                    pages = 1
                    
                total_pages += pages
                
                # Determine file type category
                file_type = DocumentService._get_file_type_category(file_ext)
                
                # Special logging for image files
                if file_type == 'image':
                    logger.info(f"IMAGE FILE UPLOAD: {file.filename} (size: {file_size} bytes, ext: {file_ext})")
                
                logger.info(f"File {file.filename} (ext: {file_ext}) categorized as: {file_type}")
                
                valid_files.append({
                    'filename': file.filename,
                    'temp_path': temp_path,
                    'file_ext': file_ext,
                    'file_type': file_type,
                    'pages': pages,
                    'size': file_size
                })
            
            # Clean up temp files for skipped files
            for file in files:
                if file.filename in skipped_files or file.filename in invalid_files:
                    temp_path = os.path.abspath(os.path.join(project.storage_path, secure_filename(file.filename)))
                    if os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                            logger.debug(f"Cleaned up temporary file: {temp_path}")
                        except Exception as cleanup_error:
                            logger.warning(f"Failed to clean up temporary file {temp_path}: {cleanup_error}")
            
            # Handle case with no valid files
            if not valid_files:
                logger.warning(f"No valid files to process: {len(skipped_files)} skipped, {len(invalid_files)} invalid")
                if skipped_files:
                    return {
                        'success': True,
                        'processed_files': [],
                        'skipped_files': skipped_files,
                        'invalid_files': invalid_files,
                        'total_files': 0,
                        'credits_used': 0,
                        'remaining_credits': user.credits,
                        'failed_files': len(invalid_files),
                        'processed_count': 0,
                        'skipped_count': len(skipped_files)
                    }
                else:
                    return {'error': 'No valid files uploaded', 'invalid_files': invalid_files}, 400
            
            # Process files sequentially (credits/billing removed – always allowed)
            processed_files = []
            failed_files = []
            
            for file_info in valid_files:
                try:
                    logger.info(f"Processing file: {file_info['filename']} ({file_info['file_type']}, {file_info['size']} bytes)")
                    
                    # Create document record
                    document = Document(
                        project_id=project.id,
                        filename=file_info['filename'],
                        file_path=file_info['temp_path'],
                        file_type=file_info['file_type'],
                        page_count=file_info['pages']
                    )
                    db.session.add(document)
                    db.session.flush()  # Get the document ID without committing
                    
                    # Process document and extract data
                    success = DocumentService.process_document(document.id)
                    if success:
                        processed_files.append(file_info['filename'])
                        logger.info(f"Successfully processed file: {file_info['filename']}")
                    else:
                        logger.error(f"Failed to process document: {file_info['filename']}")
                        failed_files.append(file_info['filename'])
                        
                except Exception as e:
                    logger.error(f"Error processing file {file_info['filename']}: {e}", exc_info=True)
                    failed_files.append(file_info['filename'])
                    continue
            
            # No credit or balance deduction – app is now free to use
            db.session.commit()
            
            result = {
                'success': True,
                'processed_files': processed_files,
                'skipped_files': skipped_files,
                'invalid_files': invalid_files,
                'failed_files': failed_files,
                'total_files': len(processed_files),
                'credits_used': 0,
                'remaining_credits': user.credits,
                'processed_count': len(processed_files),
                'skipped_count': len(skipped_files),
                'failed_count': len(failed_files)
            }
            
            logger.info(f"Processing complete: {len(processed_files)}/{len(valid_files)} files processed successfully, {len(skipped_files)} skipped, {len(failed_files)} failed")
            return result
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error in process_uploaded_files: {e}", exc_info=True)
            
            # Clean up any temp files
            for file_info in valid_files:
                if os.path.exists(file_info['temp_path']):
                    try:
                        os.remove(file_info['temp_path'])
                    except Exception as cleanup_error:
                        logger.warning(f"Failed to clean up {file_info['temp_path']} during error handling: {cleanup_error}")
            
            raise Exception(f"Failed to process uploaded files: {str(e)}")