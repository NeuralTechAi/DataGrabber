# Cloud Run Deployment Guide for DataGrabber

This guide explains how to deploy the DataGrabber application to Google Cloud Run.

## Issues Fixed for Cloud Run

### 1. File Browsing Issues
- ✅ Fixed hardcoded local paths (`/home`, user directories)
- ✅ Cloud-aware directory browsing (uses `/tmp` in production)
- ✅ Environment-aware path selection
- ✅ Security restrictions for cloud environments

### 2. Gemini API Key Authentication
- ✅ Enhanced environment variable detection
- ✅ Fallback API key loading from both env vars and config
- ✅ Better error handling and logging for API key issues
- ✅ Validation before processing files

### 3. Permission Issues
- ✅ Cloud-aware file storage paths (`/tmp` instead of user home)
- ✅ Proper directory creation with error handling
- ✅ Environment detection for storage configuration
- ✅ Consistent path handling throughout the application

### 4. Cloud Run Optimizations
- ✅ Dockerfile with proper permissions and user management
- ✅ Enhanced environment detection for Cloud Run
- ✅ Production configuration for cloud environments
- ✅ Resource limits and timeout configurations

## Deployment Steps

### Prerequisites
1. Google Cloud CLI installed and authenticated
2. A Google Cloud project with billing enabled
3. Your Gemini API key

### Quick Deployment
```bash
# Make the script executable (if not already)
chmod +x deploy.sh

# Deploy to Cloud Run (replace with your project ID)
./deploy.sh your-project-id datagrabber543 us-central1
```

### Manual Deployment
```bash
# 1. Set your project
gcloud config set project YOUR_PROJECT_ID

# 2. Enable required APIs
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com

# 3. Deploy the application
gcloud run deploy datagrabber \
    --source . \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --memory 1Gi \
    --cpu 1 \
    --timeout 900 \
    --concurrency 80 \
    --max-instances 10 \
    --set-env-vars "FLASK_ENV=production"

# 4. Set your environment variables
gcloud run services update datagrabber \
    --region us-central1 \
    --set-env-vars="GEMINI_API_KEY=your_gemini_api_key_here,DATABASE_URL=your_database_url"
```

## Environment Variables

Set these environment variables in Cloud Run:

### Required
- `GEMINI_API_KEY`: Your Google Gemini API key
- `DATABASE_URL`: Your PostgreSQL database connection string

### Optional
- `SECRET_KEY`: Application secret key (auto-generated if not set)
- `OPENAI_API_KEY`: If you want to use OpenAI models
- `ANTHROPIC_API_KEY`: If you want to use Anthropic models
- `STRIPE_PUBLIC_KEY`: For payment processing
- `STRIPE_SECRET_KEY`: For payment processing
- `SMTP_USERNAME`: For email functionality
- `SMTP_PASSWORD`: For email functionality

## File Storage in Cloud Run

### Important Notes
- ✅ Files are stored in `/tmp` directory (ephemeral storage)
- ✅ No data is permanently stored on the container filesystem
- ✅ Application serves as a link between user and AI API (no file copying to memory/storage)
- ✅ All processing is done in real-time with temporary file handling

### Storage Behavior
1. Files uploaded by users are temporarily stored in `/tmp/uploads`
2. Project data is stored in `/tmp/DataGrabber`
3. Files are processed immediately and results stored in database
4. Temporary files are cleaned up after processing
5. No persistent file storage on the container

## Testing the Deployment

After deployment, test these features:

### 1. File Browsing
- Navigate to create new project
- Test directory browsing functionality
- Verify it only shows `/tmp` directories in cloud environment

### 2. API Key Authentication
- Upload a test file for processing
- Verify Gemini API works correctly
- Check logs for any API key issues

### 3. File Upload
- Test single file upload
- Test multiple file upload
- Test folder processing
- Verify files are processed and cleaned up

### 4. Template Management
- Create new templates
- Save and reuse templates
- Verify template storage works in cloud environment

## Troubleshooting

### API Key Issues
```bash
# Check if environment variables are set
gcloud run services describe datagrabber --region us-central1 --format="value(spec.template.spec.template.spec.containers[0].env[].name,spec.template.spec.template.spec.containers[0].env[].value)"

# Update API key
gcloud run services update datagrabber --region us-central1 --set-env-vars="GEMINI_API_KEY=your_new_key"
```

### File Permission Issues
- Check Cloud Run logs: `gcloud logs read --service=datagrabber`
- Verify `/tmp` directory permissions in container
- Ensure proper user permissions in Dockerfile

### Database Connection Issues
- Verify DATABASE_URL format: `postgresql://user:password@host:port/database`
- Check database connectivity from Cloud Run
- Ensure database allows connections from Cloud Run IPs

## Monitoring and Logs

```bash
# View logs
gcloud logs read --service=datagrabber --limit=50

# Monitor performance
gcloud run services describe datagrabber --region us-central1

# View metrics
gcloud run services list
```

## Security Notes

1. ✅ Non-root user in container
2. ✅ Limited filesystem access (`/tmp` only)
3. ✅ Environment variable security
4. ✅ HTTPS enforced in production
5. ✅ No persistent file storage
6. ✅ Proper input validation and sanitization

## Performance Considerations

- Memory: 1GB (adjust based on file processing needs)
- CPU: 1 vCPU (sufficient for most workloads)
- Concurrency: 80 requests per instance
- Timeout: 15 minutes (for large file processing)
- Auto-scaling: 0-10 instances