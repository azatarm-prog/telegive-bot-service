# Deployment Troubleshooting Guide

## Current Issue: 502 Bad Gateway

The service is deployed but not responding, indicating the Flask application is failing to start properly.

## Immediate Troubleshooting Steps

### 1. Check Railway Deployment Logs

1. Go to your Railway project dashboard
2. Click on your `telegive-bot-service` deployment
3. Go to the **"Deployments"** tab
4. Click on the latest deployment
5. Check the **"Deploy Logs"** and **"Application Logs"**

Look for error messages that indicate what's preventing the app from starting.

### 2. Test with Minimal Version

I've created a minimal diagnostic version to isolate the issue:

**Option A: Temporarily switch to minimal version**
```bash
# In Railway, temporarily change the Procfile to:
web: python app_minimal.py
```

**Option B: Test minimal version locally**
```bash
cd telegive-bot
python app_minimal.py
```

### 3. Common Issues and Solutions

#### Issue: Missing Dependencies
**Symptoms:** Import errors in logs
**Solution:** Check if all packages in `requirements.txt` are installing properly

#### Issue: Database Connection
**Symptoms:** Database connection errors
**Solution:** Verify `DATABASE_URL` is set correctly in Railway

#### Issue: Port Configuration
**Symptoms:** App starts but Railway can't connect
**Solution:** Ensure app binds to `0.0.0.0` and uses Railway's `PORT` environment variable

#### Issue: Environment Variables
**Symptoms:** Configuration errors, missing secrets
**Solution:** Verify all required environment variables are set in Railway

## Diagnostic Endpoints

Once the minimal version is running, test these endpoints:

- `https://your-app.railway.app/` - Basic status
- `https://your-app.railway.app/health` - Health check
- `https://your-app.railway.app/env-check` - Environment variables check

## Step-by-Step Debugging

### Step 1: Enable Minimal Version
1. In Railway, go to your service settings
2. Change the start command to: `python app_minimal.py`
3. Deploy and test if it works

### Step 2: Check Environment Variables
1. Access `/env-check` endpoint
2. Verify all required variables are set
3. Check for any missing or incorrect values

### Step 3: Gradually Add Complexity
If minimal version works:
1. Switch back to main app: `python app.py`
2. Check logs for specific error messages
3. Fix issues one by one

## Common Railway-Specific Issues

### 1. Procfile Configuration
**Current Procfile:**
```
web: gunicorn --bind 0.0.0.0:$PORT app:app
```

**Alternative (if gunicorn issues):**
```
web: python app.py
```

### 2. Database URL Format
Railway provides `DATABASE_URL` in this format:
```
postgresql://username:password@host:port/database
```

Ensure your app handles this format correctly.

### 3. Port Binding
Railway automatically sets the `PORT` environment variable. Your app must:
- Bind to `0.0.0.0` (not `127.0.0.1`)
- Use the `PORT` environment variable
- Default to port 5000 if `PORT` is not set

### 4. File Permissions
Railway containers may have restricted file permissions:
- Use `/tmp` for temporary files
- Avoid writing to system directories like `/var`

## Environment Variables Checklist

Verify these are set in Railway:

### Required Variables
- ✅ `SERVICE_NAME="telegive-bot-service"`
- ✅ `SERVICE_PORT="5000"`
- ✅ `SECRET_KEY` (your secret key)
- ✅ `DATABASE_URL` (automatically set by Railway if PostgreSQL is added)

### Service URLs
- ✅ `TELEGIVE_AUTH_URL`
- ✅ `TELEGIVE_CHANNEL_URL`
- ✅ `TELEGIVE_PARTICIPANT_URL`
- ✅ `TELEGIVE_GIVEAWAY_URL`

### Security
- ✅ `ADMIN_TOKEN`
- ✅ `JWT_SECRET_KEY`
- ✅ `WEBHOOK_SECRET`

## Quick Fixes to Try

### Fix 1: Simplify Procfile
```
web: python app.py
```

### Fix 2: Add Debug Mode (temporarily)
In Railway environment variables, add:
```
FLASK_DEBUG=true
DEBUG=true
```

### Fix 3: Check Python Version
Ensure Railway is using Python 3.11:
```
# In runtime.txt (create if doesn't exist)
python-3.11.0
```

## Getting Help

If issues persist:

1. **Share the deployment logs** from Railway
2. **Test the minimal version** first
3. **Check environment variables** using `/env-check`
4. **Verify database connectivity** if using PostgreSQL

## Next Steps

1. Try the minimal version first
2. Check Railway deployment logs
3. Verify environment variables
4. Gradually add complexity back
5. Share specific error messages for targeted fixes

The deployment prevention system we implemented is working - it's helping identify and resolve issues systematically!

