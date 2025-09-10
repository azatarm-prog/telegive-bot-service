# Service Recovery Plan

## Current Status: 502 Bad Gateway

The Telegram Bot Service is deployed but not responding. This systematic recovery plan will help identify and resolve the issue.

## 🎯 **Recovery Strategy**

### Phase 1: Minimal Diagnostics ✅
- [x] Created `app_minimal.py` - Basic Flask app with health endpoints
- [x] Created `app_progressive.py` - Step-by-step diagnostic testing
- [x] Provided troubleshooting documentation

### Phase 2: Systematic Testing 🔄
Test each diagnostic level to isolate the problem:

1. **Level 1: Basic Flask** → `app_minimal.py`
2. **Level 2: Progressive Testing** → `app_progressive.py`  
3. **Level 3: Full Application** → `app.py`

### Phase 3: Issue Resolution 📋
Based on diagnostic results, apply targeted fixes.

## 🚀 **Step-by-Step Recovery Process**

### **Step 1: Deploy Minimal Version**

**Railway Configuration:**
```bash
# Change start command to:
python app_minimal.py
```

**Test Endpoints:**
- `GET /` - Basic status
- `GET /health` - Health check
- `GET /env-check` - Environment diagnostics

**Expected Result:** Should return JSON responses if Railway setup is correct.

### **Step 2: Deploy Progressive Version** 

**Railway Configuration:**
```bash
# Change start command to:
python app_progressive.py
```

**Test Diagnostic Steps:**
- `GET /step1/basic` - Basic Flask functionality
- `GET /step2/environment` - Environment variables
- `GET /step3/imports` - Python package imports
- `GET /step4/database` - Database connectivity
- `GET /step5/services` - External service connectivity
- `GET /diagnostic/full` - Complete diagnostic report

**Analysis:** Each step will show exactly where the failure occurs.

### **Step 3: Apply Targeted Fixes**

Based on diagnostic results:

#### **If Step 1 Fails:** Railway Configuration Issue
- Check PORT environment variable
- Verify Procfile syntax
- Check Python version compatibility

#### **If Step 2 Fails:** Environment Variables Issue
- Verify all required variables are set
- Check for typos in variable names
- Ensure secrets are properly configured

#### **If Step 3 Fails:** Import/Dependency Issue
- Check requirements.txt
- Verify package versions
- Fix circular imports

#### **If Step 4 Fails:** Database Issue
- Verify DATABASE_URL format
- Check PostgreSQL service status
- Test database permissions

#### **If Step 5 Fails:** External Services Issue
- Check service URLs
- Verify network connectivity
- Test service authentication

## 🔧 **Common Fixes**

### **Fix 1: Simplify Procfile**
```
# Current (complex)
web: gunicorn --bind 0.0.0.0:$PORT app:app

# Simplified (for testing)
web: python app.py
```

### **Fix 2: Add Missing Dependencies**
```bash
# Add to requirements.txt if missing:
gunicorn==21.2.0
psycopg2-binary==2.9.7
```

### **Fix 3: Fix Port Binding**
```python
# Ensure app.py uses Railway's PORT
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
```

### **Fix 4: Database URL Handling**
```python
# Handle Railway's DATABASE_URL format
import os
from urllib.parse import urlparse

database_url = os.getenv('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
```

## 📊 **Diagnostic Checklist**

### ✅ **Environment Variables**
- [ ] `SERVICE_NAME` set
- [ ] `SECRET_KEY` set  
- [ ] `DATABASE_URL` set (auto by Railway)
- [ ] `ADMIN_TOKEN` set
- [ ] `JWT_SECRET_KEY` set
- [ ] `WEBHOOK_SECRET` set
- [ ] Service URLs set (AUTH, CHANNEL, PARTICIPANT, GIVEAWAY)

### ✅ **Dependencies**
- [ ] Flask installed
- [ ] SQLAlchemy installed
- [ ] psycopg2 installed
- [ ] All requirements.txt packages installed

### ✅ **Configuration**
- [ ] Procfile syntax correct
- [ ] Port binding to 0.0.0.0
- [ ] Using Railway's PORT variable
- [ ] Database URL format correct

### ✅ **Services**
- [ ] PostgreSQL service added to Railway project
- [ ] External service URLs accessible
- [ ] Network connectivity working

## 🎯 **Success Criteria**

### **Minimal Version Success:**
```json
{
  "service": "telegive-bot-service",
  "status": "running",
  "message": "Minimal diagnostic version is working"
}
```

### **Progressive Version Success:**
```json
{
  "diagnostic": "full",
  "overall_status": "success",
  "steps": [...]
}
```

### **Full Application Success:**
```json
{
  "status": "healthy",
  "service": "telegive-bot-service",
  "database": "connected",
  "external_services": "available"
}
```

## 🚨 **Emergency Rollback**

If all else fails, use the minimal version as a temporary solution:

1. **Deploy minimal version** for basic functionality
2. **Gradually add features** back one by one
3. **Test each addition** before proceeding
4. **Identify the exact breaking point**

## 📞 **Next Steps**

1. **Start with minimal version** - Verify Railway setup works
2. **Run progressive diagnostics** - Identify exact failure point  
3. **Apply targeted fixes** - Resolve specific issues
4. **Test incrementally** - Ensure each fix works
5. **Deploy full application** - Complete service restoration

## 🔄 **Iterative Approach**

```
Minimal → Progressive → Targeted Fixes → Full Application
   ↓           ↓              ↓              ↓
 Works?    Identify      Apply Fix      Test & Deploy
           Issue
```

This systematic approach ensures we identify and fix the exact issue preventing your service from starting, rather than guessing at potential problems.

