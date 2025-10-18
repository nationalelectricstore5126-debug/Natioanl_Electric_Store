# Natioanl_Electric_Store
National Electric Store - Inventory Management System
Overview
A Flask-based inventory management system for National Electric Store that uses Google Sheets as a database backend. The system provides a complete solution for managing products, stock movements, and generating reports.

Project Purpose
This application helps track inventory for an electrical products store, including:

Product catalog management with categories
Stock in/out tracking
Financial reporting (purchases, sales, balance)
Real-time dashboard statistics
Transaction history
Current State
Status: Fully configured and running on Replit Last Updated: October 18, 2025

The application is successfully connected to Google Sheets and ready for use.

Architecture
Technology Stack
Backend: Flask 2.3.3 (Python web framework)
Database: Google Sheets (via gspread library)
Authentication: OAuth2 Service Account
Frontend: Vanilla JavaScript with embedded HTML/CSS
Deployment: Gunicorn WSGI server
Project Structure
.
├── app.py                 # Main Flask application with all API routes
├── templates/
│   └── index.html        # Main dashboard and login page
├── template/             # Module templates (loaded dynamically)
│   ├── Product.html      # Product management interface
│   ├── Stock.html        # Stock in/out interface
│   ├── Reports.html      # Reports and analytics
│   └── Settings.html     # Settings page
├── requirements.txt      # Python dependencies
└── replit.md            # This file
Google Sheets Structure
The application expects a Google Sheet with the following worksheets:

Products: Stores product catalog (ID, Main Category, Sub Category)
Stock In: Records incoming stock transactions
Stock Out: Records outgoing stock transactions
Transactions: Master transaction log (Type, Product ID, Quantity, Price, Date, Categories)
Reports: Generated reports storage
Configuration
Environment Variables (Required)
The following secrets must be configured in Replit Secrets:

GOOGLE_SERVICE_ACCOUNT: Base64-encoded Google Service Account JSON credentials
GOOGLE_SHEET_ID: The ID of your Google Sheet (from the URL)
Default Login Credentials
Username: Natioanl_Electric_Store
Password: National098#$
These are configured in templates/index.html and should be updated for production use.

Development Workflow
Running Locally
The application runs automatically via the configured workflow:

python app.py
The server starts on http://0.0.0.0:5000

Deployment
Configured for autoscale deployment using Gunicorn:

gunicorn --bind=0.0.0.0:5000 --reuse-port --workers=2 app:app
Key Features
Dashboard
Real-time statistics: Total products, monthly stock in/out, balance
Financial metrics: Total purchases, sales, profit/loss
Auto-refresh every 30 seconds
Product Management
Add/delete products with categories
Two-level categorization (Main Category, Sub Category)
Real-time stock quantity calculation from transactions
Stock Management
Stock In: Record purchases with price
Stock Out: Record sales with selling price
Automatic stock validation (prevents overselling)
Reports
Complete transaction history
Filter by type (in/out), product, category
Export capabilities
API Endpoints
Main Routes
GET / - Dashboard/Login page
GET /product - Product management page
GET /stock - Stock management page
GET /reports - Reports page
API Endpoints
GET /api/dashboard-stats - Dashboard statistics
GET/POST/DELETE /api/products - Product CRUD operations
POST /api/stockin - Record stock in transaction
POST /api/stockout - Record stock out transaction
GET /api/reports - Get transaction history
GET /api/categories - Get available categories
GET /api/health - Health check endpoint
Recent Changes
2025-10-18: Initial Replit setup
Configured Python 3.11 environment
Installed Flask and Google Sheets dependencies
Fixed authentication to use Replit secrets
Configured Flask to run on 0.0.0.0:5000
Set up deployment configuration with Gunicorn
Added comprehensive .gitignore for Python projects
User Preferences
None specified yet.

Known Issues
LSP shows 26 diagnostics in app.py (mostly style warnings, app functions correctly)
The application uses a development Flask server in the workflow (Gunicorn is used for deployment)
Notes
The application stores all data in Google Sheets, so ensure the service account has proper access
Make sure to share your Google Sheet with the service account email address
The system calculates current stock from the Transactions worksheet
All monetary values are stored without currency symbols for calculation purposes
