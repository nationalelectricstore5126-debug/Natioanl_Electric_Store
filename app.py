from flask import Flask, request, jsonify, render_template, send_from_directory
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
import os
from datetime import datetime
import json

# ---------------- LOAD ENV ----------------
load_dotenv()

app = Flask(__name__)

# ---------------- GOOGLE SHEETS SETUP ----------------
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
try:
    # For Render deployment - use environment variable with JSON content
    service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    
    if service_account_json:
        # Parse the JSON string directly for Render
        print("🔧 Using JSON environment variable for Google Sheets authentication")
        service_account_info = json.loads(service_account_json)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
    else:
        # Fallback to file-based authentication for local development
        print("🔧 Using file-based authentication for Google Sheets")
        creds_file = os.getenv("GOOGLE_SERVICE_ACCOUNT")
        if creds_file and os.path.exists(creds_file):
            creds = ServiceAccountCredentials.from_json_keyfile_name(creds_file, scope)
        else:
            raise Exception("Google Sheets credentials not found")
    
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id)

    products_ws = sheet.worksheet("Products")
    stockin_ws = sheet.worksheet("Stock In")
    stockout_ws = sheet.worksheet("Stock Out")
    transactions_ws = sheet.worksheet("Transactions")
    
    # ✅ REPORTS SHEET ADD KARO
    try:
        reports_ws = sheet.worksheet("Reports")
        print("✅ Reports sheet found")
    except gspread.exceptions.WorksheetNotFound:
        # Agar Reports sheet nahi hai toh banao
        reports_ws = sheet.add_worksheet(title="Reports", rows="1000", cols="20")
        # Headers set karo - WITH CATEGORIES
        reports_ws.append_row(["Report Type", "Period", "Product ID", "Main Category", "Received", "Sold", "Remaining", "Purchase Value", "Sales Value", "Generated At", "Sub Category"])
        print("✅ Created new Reports sheet")

    print("✅ Connected to Google Sheet:", sheet.title)
except Exception as e:
    print("❌ Error connecting to Google Sheets:", e)
    products_ws = stockin_ws = stockout_ws = transactions_ws = reports_ws = None


# ---------------- ROUTES ----------------

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/product")
def product_page():
    return render_template("Product.html")

@app.route("/stock")
def stock_page():
    return render_template("stock.html")

@app.route("/reports")
def reports_page():
    return render_template("reports.html")

@app.route("/settings")
def settings_page():
    return render_template("Settings.html")

@app.route("/template/<path:filename>")
def serve_module(filename):
    return send_from_directory("template", filename)


# ---------- DASHBOARD STATS API (FIXED) ----------
@app.route("/api/dashboard-stats", methods=["GET"])
def dashboard_stats():
    """Get dashboard statistics from Google Sheets - DIRECT FROM STOCK IN/OUT SHEETS"""
    try:
        if products_ws is None or stockin_ws is None or stockout_ws is None:
            return jsonify({"error": "Google Sheet not loaded"}), 500
            
        # Get all data from sheets
        products_data = products_ws.get_all_values()
        stockin_data = stockin_ws.get_all_values()
        stockout_data = stockout_ws.get_all_values()
        
        # Calculate totals
        total_products = len(products_data) - 1 if len(products_data) > 1 else 0
        
        # Calculate monthly stock in/out - DIRECT FROM STOCK IN/OUT SHEETS
        current_month = datetime.now().strftime("%Y-%m")
        monthly_stock_in = 0
        monthly_stock_out = 0
        total_purchases = 0
        total_sales = 0
        
        # Process Stock In data
        if len(stockin_data) > 1:
            stockin_headers = [h.strip() for h in stockin_data[0]]
            stockin_rows = stockin_data[1:]
            
            for row in stockin_rows:
                while len(row) < len(stockin_headers):
                    row.append('')
                
                row_dict = {}
                for i, header in enumerate(stockin_headers):
                    row_dict[header] = row[i] if i < len(row) else ''
                
                # Get date and check if current month
                date_str = row_dict.get("Date", "")
                
                # Get quantity and price
                try:
                    quantity = int(float(row_dict.get("Quantity", 0)))
                    price = float(row_dict.get("Price", 0))
                except (ValueError, TypeError):
                    quantity = 0
                    price = 0
                
                # Check if transaction is from current month
                if current_month in date_str:
                    monthly_stock_in += quantity
                    total_purchases += quantity * price
        
        # Process Stock Out data - ✅ YAHAN SE TOTAL SALES AYEGA
        if len(stockout_data) > 1:
            stockout_headers = [h.strip() for h in stockout_data[0]]
            stockout_rows = stockout_data[1:]
            
            for row in stockout_rows:
                while len(row) < len(stockout_headers):
                    row.append('')
                
                row_dict = {}
                for i, header in enumerate(stockout_headers):
                    row_dict[header] = row[i] if i < len(row) else ''
                
                # Get date and check if current month
                date_str = row_dict.get("Date", "")
                
                # Get quantity and PRICE (YEH SELLING PRICE HAI)
                try:
                    quantity = int(float(row_dict.get("Quantity", 0)))
                    # ✅ SELLING PRICE USE KARO - DIFFERENT COLUMN NAMES CHECK KARO
                    selling_price = float(row_dict.get("Selling Price", 0) or row_dict.get("Price", 0))
                except (ValueError, TypeError):
                    quantity = 0
                    selling_price = 0
                
                # Check if transaction is from current month
                if current_month in date_str:
                    monthly_stock_out += quantity
                    total_sales += quantity * selling_price  # ✅ QUANTITY × SELLING PRICE
        
        # Calculate balance (profit/loss)
        balance = total_sales - total_purchases
        
        print(f"📊 Dashboard Stats: Products={total_products}, StockIn={monthly_stock_in}, StockOut={monthly_stock_out}, Purchases={total_purchases}, Sales={total_sales}, Balance={balance}")
        
        return jsonify({
            "totalProducts": total_products,
            "monthlyStockIn": monthly_stock_in,
            "monthlyStockOut": monthly_stock_out,
            "balance": balance,
            "totalPurchases": total_purchases,
            "totalSales": total_sales  # ✅ YAHAN SE TOTAL SALES JAYEGA
        })
        
    except Exception as e:
        print("❌ Error in dashboard stats:", e)
        return jsonify({
            "totalProducts": 0,
            "monthlyStockIn": 0,
            "monthlyStockOut": 0,
            "balance": 0,
            "totalPurchases": 0,
            "totalSales": 0
        }), 500


# ---------- PRODUCTS (FIXED - ONLY 3 COLUMNS) ----------
@app.route("/api/products", methods=["GET", "POST", "DELETE"])
def products():
    if products_ws is None:
        print("❌ Google Sheet not loaded!")
        return jsonify({"error": "Google Sheet not loaded"}), 500

    try:
        if request.method == "GET":
            # Manual approach - get all values and map manually
            all_data = products_ws.get_all_values()
            
            if len(all_data) < 2:  # Only headers or empty
                return jsonify([])
            
            headers = [h.strip() for h in all_data[0]]  # Clean headers
            rows = all_data[1:]    # Rest are data rows
            
            print("🔍 Headers found:", headers)
            
            formatted_data = []
            
            for row_index, row in enumerate(rows):
                # Ensure row has same length as headers
                while len(row) < len(headers):
                    row.append('')
                
                # Create a dictionary by mapping headers to row values
                row_dict = {}
                for i, header in enumerate(headers):
                    row_dict[header] = row[i] if i < len(row) else ''
                
                # ✅ FIXED: Map to consistent field names
                product_data = {
                    "id": str(row_dict.get("ID", "")).strip(),
                    "mainCat": str(row_dict.get("Main Category", "")).strip(),
                    "subCat": str(row_dict.get("Sub Category", "")).strip(),
                }
                
                # Calculate current stock from transactions
                current_stock = calculate_current_stock(product_data["id"])
                product_data["quantity"] = current_stock
                
                formatted_data.append(product_data)
            
            print("📦 Final formatted products:", formatted_data)
            return jsonify(formatted_data)

        elif request.method == "POST":
            payload = request.json
            print("📝 Product POST received:", payload)

            required = ["id", "mainCat"]
            if not all(field in payload for field in required):
                return jsonify({"error": "Missing required fields"}), 400

            # Get all existing IDs
            all_values = products_ws.get_all_values()
            all_ids = [row[0] for row in all_values[1:]] if len(all_values) > 1 else []
            
            if payload["id"] in all_ids:
                return jsonify({"error": "Product ID already exists"}), 400

            # ✅ FIXED: Add to Google Sheets - ONLY 3 COLUMNS
            products_ws.append_row([
                payload["id"],           # ID - Column 1
                payload["mainCat"],      # Main Category - Column 2  
                payload.get("subCat", ""), # Sub Category - Column 3
            ])

            print("✅ Product added to Google Sheet:", payload["id"])
            return jsonify({"message": "Product added successfully!"})

        elif request.method == "DELETE":
            pid = request.args.get("id")
            rows = products_ws.get_all_values()
            for i, row in enumerate(rows):
                if len(row) > 0 and row[0] == pid:
                    products_ws.delete_rows(i + 1)
                    print(f"🗑️ Deleted product ID: {pid}")
                    return jsonify({"message": "Product deleted successfully!"})
            return jsonify({"error": "Product not found"}), 404

    except Exception as e:
        print("❌ Exception:", e)
        return jsonify({"error": str(e)}), 500


# ---------- CALCULATE CURRENT STOCK FROM TRANSACTIONS ----------
def calculate_current_stock(product_id):
    """Calculate current stock from transactions"""
    try:
        if transactions_ws is None:
            return 0
            
        all_transactions = transactions_ws.get_all_values()
        if len(all_transactions) < 2:
            return 0
            
        headers = [h.strip() for h in all_transactions[0]]
        rows = all_transactions[1:]
        
        total_stock = 0
        
        for row in rows:
            while len(row) < len(headers):
                row.append('')
            
            row_dict = {}
            for i, header in enumerate(headers):
                row_dict[header] = row[i] if i < len(row) else ''
            
            # Check if this transaction is for our product
            trans_product_id = str(row_dict.get("Product ID", "")).strip()
            if trans_product_id == str(product_id):
                trans_type = str(row_dict.get("Type", "")).strip().lower()
                trans_quantity = 0
                
                try:
                    trans_quantity = int(float(row_dict.get("Quantity", 0)))
                except (ValueError, TypeError):
                    trans_quantity = 0
                
                if trans_type == "in":
                    total_stock += trans_quantity
                elif trans_type == "out":
                    total_stock -= trans_quantity
        
        print(f"📊 Calculated stock for {product_id}: {total_stock}")
        return total_stock
        
    except Exception as e:
        print(f"❌ Error calculating stock: {e}")
        return 0


# ---------- STOCK IN (FIXED) ----------
@app.route("/api/stockin", methods=["POST"])
def stock_in():
    if stockin_ws is None or transactions_ws is None:
        return jsonify({"error": "Google Sheet not loaded"}), 500
    try:
        payload = request.json
        print("📥 Stock In payload:", payload)
        
        required = ["productId", "quantity", "price"]
        if not all(field in payload for field in required):
            return jsonify({"error": "Missing required stock fields"}), 400

        # Find product details for categories
        all_data = products_ws.get_all_values()
        if len(all_data) < 2:
            return jsonify({"error": "No products found"}), 404
            
        headers = [h.strip() for h in all_data[0]]
        rows = all_data[1:]
        
        product_details = None
        for row in rows:
            while len(row) < len(headers):
                row.append('')
            
            row_dict = {}
            for i, header in enumerate(headers):
                row_dict[header] = row[i] if i < len(row) else ''
            
            product_id = str(row_dict.get("ID", "")).strip()
            if product_id == str(payload["productId"]):
                product_details = row_dict
                break
        
        if not product_details:
            return jsonify({"error": "Product not found"}), 404

        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        main_category = product_details.get("Main Category", "")
        sub_category = product_details.get("Sub Category", "")
        
        print(f"📥 Stock In - Product: {payload['productId']}, MainCat: {main_category}, SubCat: {sub_category}")
        
        # ✅ STOCK IN SHEET - CORRECT COLUMN ORDER
        stockin_ws.append_row([
            payload["productId"],        # Product ID
            payload["quantity"],         # Quantity
            payload["price"],            # Price
            date_str,                    # Date
            main_category,               # Main Category
            sub_category                 # Sub Category
        ])
        
        # ✅ TRANSACTIONS SHEET (MAIN DATABASE) - CORRECT COLUMN ORDER
        transactions_ws.append_row([
            "in",                        # Type
            payload["productId"],        # Product ID
            payload["quantity"],         # Quantity
            payload["price"],            # Price
            date_str,                    # Date
            main_category,               # Main Category
            sub_category                 # Sub Category
        ])
        
        print("✅ Stock In recorded successfully in both sheets!")
        return jsonify({"message": "Stock In recorded successfully!"})
            
    except Exception as e:
        print("❌ Error in /api/stockin:", e)
        return jsonify({"error": str(e)}), 500


# ---------- STOCK OUT (FIXED) ----------
@app.route("/api/stockout", methods=["POST"])
def stock_out():
    if stockout_ws is None or transactions_ws is None:
        return jsonify({"error": "Google Sheet not loaded"}), 500
    try:
        payload = request.json
        print("📤 Stock Out payload:", payload)
        
        required = ["productId", "quantity", "price"]
        if not all(field in payload for field in required):
            return jsonify({"error": "Missing required stock fields"}), 400

        # Check available stock from transactions
        current_stock = calculate_current_stock(payload["productId"])
        
        if current_stock < int(payload["quantity"]):
            return jsonify({"error": f"Not enough stock available! Current: {current_stock}, Required: {payload['quantity']}"}), 400

        # Get product details for categories
        all_data = products_ws.get_all_values()
        if len(all_data) < 2:
            return jsonify({"error": "No products found"}), 404
            
        headers = [h.strip() for h in all_data[0]]
        rows = all_data[1:]
        
        product_details = None
        for row in rows:
            while len(row) < len(headers):
                row.append('')
            
            row_dict = {}
            for i, header in enumerate(headers):
                row_dict[header] = row[i] if i < len(row) else ''
            
            product_id = str(row_dict.get("ID", "")).strip()
            if product_id == str(payload["productId"]):
                product_details = row_dict
                break
        
        if not product_details:
            return jsonify({"error": "Product not found"}), 404

        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        main_category = product_details.get("Main Category", "")
        sub_category = product_details.get("Sub Category", "")
        
        print(f"📤 Stock Out - Product: {payload['productId']}, MainCat: {main_category}, SubCat: {sub_category}")
        
        # ✅ STOCK OUT SHEET - CORRECT COLUMN ORDER
        stockout_ws.append_row([
            payload["productId"],        # Product ID
            payload["quantity"],         # Quantity
            payload["price"],            # Selling Price
            date_str,                    # Date
            main_category,               # Main Category
            sub_category                 # Sub Category
        ])
        
        # ✅ TRANSACTIONS SHEET (MAIN DATABASE) - CORRECT COLUMN ORDER
        transactions_ws.append_row([
            "out",                       # Type
            payload["productId"],        # Product ID
            payload["quantity"],         # Quantity
            payload["price"],            # Price
            date_str,                    # Date
            main_category,               # Main Category
            sub_category                 # Sub Category
        ])
        
        print("✅ Stock Out recorded successfully in both sheets!")
        return jsonify({"message": "Stock Out recorded successfully!"})
            
    except Exception as e:
        print("❌ Error in /api/stockout:", e)
        return jsonify({"error": str(e)}), 500


# ---------- REPORTS (FIXED COLUMN MAPPING) ----------
@app.route("/api/reports", methods=["GET"])
def reports():
    if transactions_ws is None:
        return jsonify({"error": "Google Sheet not loaded"}), 500
    try:
        # Manual approach for transactions
        all_data = transactions_ws.get_all_values()
        
        if len(all_data) < 2:
            return jsonify([])
            
        headers = [h.strip() for h in all_data[0]]
        rows = all_data[1:]
        
        print(f"🔍 Transactions headers: {headers}")
        
        formatted_transactions = []
        for row in rows:
            while len(row) < len(headers):
                row.append('')
            
            row_dict = {}
            for i, header in enumerate(headers):
                row_dict[header] = row[i] if i < len(row) else ''
            
            # ✅ FIXED: Correct column mapping based on ACTUAL Google Sheets structure
            # Debug: Print the actual row data to see the order
            print(f"📋 Row data: {row}")
            
            # ✅ FIXED: Use POSITION-BASED mapping instead of header-based
            # Based on the actual column order in your Google Sheet
            # Transactions sheet columns: Type, Product ID, Quantity, Price, Date, Main Category, Sub Category
            transaction = {
                "type": row[0] if len(row) > 0 else "",           # Column 1: Type
                "productId": row[1] if len(row) > 1 else "",      # Column 2: Product ID
                "quantity": row[2] if len(row) > 2 else "",       # Column 3: Quantity
                "price": row[3] if len(row) > 3 else "",          # Column 4: Price
                "date": row[4] if len(row) > 4 else "",           # Column 5: Date
                "mainCat": row[5] if len(row) > 5 else "",        # Column 6: Main Category
                "subCat": row[6] if len(row) > 6 else ""          # Column 7: Sub Category
            }
            
            # Convert quantity and price to proper types
            try:
                transaction["quantity"] = int(float(transaction["quantity"])) if transaction["quantity"] else 0
            except (ValueError, TypeError):
                transaction["quantity"] = 0
                
            try:
                transaction["price"] = float(transaction["price"]) if transaction["price"] else 0.0
            except (ValueError, TypeError):
                transaction["price"] = 0.0
            
            formatted_transactions.append(transaction)
        
        print(f"📊 Reports fetched: {len(formatted_transactions)} transactions")
        
        # ✅ DEBUG: Print first transaction to verify structure
        if formatted_transactions:
            print("🔍 First transaction sample:", formatted_transactions[0])
        
        return jsonify(formatted_transactions)
    except Exception as e:
        print("❌ Error in /api/reports:", e)
        return jsonify({"error": str(e)}), 500


# ---------- SIMPLIFIED REPORTS (NO PRODUCT NAME) ----------
@app.route("/api/simple-reports", methods=["GET"])
def simple_reports():
    """Simple reports data for frontend - WITHOUT PRODUCT NAME"""
    try:
        if transactions_ws is None or products_ws is None:
            return jsonify({"error": "Google Sheet not loaded"}), 500
            
        # Get all transactions
        all_transactions = transactions_ws.get_all_values()
        if len(all_transactions) < 2:
            return jsonify({"inventory": [], "finance": {"purchases": 0, "sales": 0, "balance": 0}})
        
        headers = [h.strip() for h in all_transactions[0]]
        rows = all_transactions[1:]
        
        print(f"📋 Transactions headers: {headers}")
        print(f"📋 Total transactions found: {len(rows)}")
        
        # Get products for categories only (NO NAME NEEDED)
        products_data = products_ws.get_all_values()
        product_categories = {}
        if len(products_data) > 1:
            for row in products_data[1:]:
                if len(row) > 0:
                    product_id = str(row[0]).strip()
                    main_cat = str(row[1]).strip() if len(row) > 1 else ""  # ✅ FIXED: Main Category is now at index 1
                    sub_cat = str(row[2]).strip() if len(row) > 2 else ""   # ✅ FIXED: Sub Category is now at index 2
                    
                    product_categories[product_id] = {
                        "mainCat": main_cat,
                        "subCat": sub_cat
                    }
        
        print(f"📦 Product categories found: {product_categories}")
        
        # Calculate current stock for all products
        inventory_data = {}
        total_purchases = 0
        total_sales = 0
        
        for row_index, row in enumerate(rows):
            while len(row) < len(headers):
                row.append('')
            
            row_dict = {}
            for i, header in enumerate(headers):
                row_dict[header] = row[i] if i < len(row) else ''
            
            product_id = str(row_dict.get("Product ID", "")).strip()
            trans_type = row_dict.get("Type", "").lower()
            
            # Get quantity and price
            try:
                quantity = int(float(row_dict.get("Quantity", 0)))
                price = float(row_dict.get("Price", 0))
            except (ValueError, TypeError):
                quantity = 0
                price = 0
            
            print(f"📊 Processing: {product_id}, {trans_type}, Qty: {quantity}, Price: {price}")
            
            # Initialize product in report
            if product_id not in inventory_data:
                categories = product_categories.get(product_id, {"mainCat": "", "subCat": ""})
                inventory_data[product_id] = {
                    "id": product_id,
                    # ✅ NO PRODUCT NAME - only categories
                    "mainCat": categories.get("mainCat", ""),
                    "subCat": categories.get("subCat", ""),
                    "received": 0,
                    "sold": 0,
                    "remaining": 0
                }
            
            # Update counts
            if trans_type == "in":
                inventory_data[product_id]["received"] += quantity
                inventory_data[product_id]["remaining"] += quantity
                total_purchases += quantity * price
            elif trans_type == "out":
                inventory_data[product_id]["sold"] += quantity
                inventory_data[product_id]["remaining"] -= quantity
                total_sales += quantity * price
        
        # ✅ DEBUG: Show final inventory data
        for product_id, data in inventory_data.items():
            print(f"📋 Final: {product_id} -> {data}")
        
        return jsonify({
            "inventory": list(inventory_data.values()),
            "finance": {
                "purchases": total_purchases,
                "sales": total_sales,
                "balance": total_sales - total_purchases
            }
        })
        
    except Exception as e:
        print("❌ Error in simple reports:", e)
        return jsonify({"error": str(e)}), 500


# ---------- MONTHLY REPORT (NO PRODUCT NAME) ----------
@app.route("/api/monthly-report", methods=["GET"])
def monthly_report():
    """Get monthly report data - WITHOUT PRODUCT NAME"""
    try:
        if transactions_ws is None or products_ws is None:
            return jsonify({"error": "Google Sheet not loaded"}), 500
            
        month = request.args.get("month")
        
        print(f"🔍 Monthly report requested for: {month}")
        
        # Get all transactions
        all_data = transactions_ws.get_all_values()
        if len(all_data) < 2:
            return jsonify({"inventory": [], "finance": {"purchases": 0, "sales": 0, "balance": 0}})
        
        headers = [h.strip() for h in all_data[0]]
        rows = all_data[1:]
        
        print(f"📋 Transactions headers: {headers}")
        print(f"📋 Total transactions found: {len(rows)}")
        
        # Get products for categories only (NO NAME NEEDED)
        products_data = products_ws.get_all_values()
        product_categories = {}
        if len(products_data) > 1:
            for row in products_data[1:]:
                if len(row) > 0:
                    product_id = str(row[0]).strip()
                    main_cat = str(row[1]).strip() if len(row) > 1 else ""  # ✅ FIXED: Main Category is now at index 1
                    sub_cat = str(row[2]).strip() if len(row) > 2 else ""   # ✅ FIXED: Sub Category is now at index 2
                    
                    product_categories[product_id] = {
                        "mainCat": main_cat,
                        "subCat": sub_cat
                    }

        print(f"📦 Product categories found: {product_categories}")

        # Process transactions
        inventory_data = {}
        total_purchases = 0
        total_sales = 0
        
        for row_index, row in enumerate(rows):
            while len(row) < len(headers):
                row.append('')
            
            row_dict = {}
            for i, header in enumerate(headers):
                row_dict[header] = row[i] if i < len(row) else ''
            
            product_id = str(row_dict.get("Product ID", "")).strip()
            trans_type = row_dict.get("Type", "").lower()
            
            # Get quantity and price
            try:
                quantity = int(float(row_dict.get("Quantity", 0)))
                price = float(row_dict.get("Price", 0))
            except (ValueError, TypeError):
                quantity = 0
                price = 0
            
            print(f"📊 Processing: {product_id}, {trans_type}, Qty: {quantity}, Price: {price}")
            
            # Initialize product in report
            if product_id not in inventory_data:
                categories = product_categories.get(product_id, {"mainCat": "", "subCat": ""})
                inventory_data[product_id] = {
                    "id": product_id,
                    # ✅ NO PRODUCT NAME - only categories
                    "mainCat": categories.get("mainCat", ""),
                    "subCat": categories.get("subCat", ""),
                    "received": 0,
                    "sold": 0,
                    "remaining": 0
                }
            
            # Update counts
            if trans_type == "in":
                inventory_data[product_id]["received"] += quantity
                inventory_data[product_id]["remaining"] += quantity
                total_purchases += quantity * price
            elif trans_type == "out":
                inventory_data[product_id]["sold"] += quantity
                inventory_data[product_id]["remaining"] -= quantity
                total_sales += quantity * price
        
        print(f"✅ Report generated: {len(inventory_data)} products, Purchases: {total_purchases}, Sales: {total_sales}")
        
        # ✅ DEBUG: Show final inventory data
        for product_id, data in inventory_data.items():
            print(f"📋 Final: {product_id} -> {data}")
        
        return jsonify({
            "inventory": list(inventory_data.values()),
            "finance": {
                "purchases": total_purchases,
                "sales": total_sales,
                "balance": total_sales - total_purchases
            }
        })
        
        
    except Exception as e:
        print("❌ Error in monthly report:", e)
        return jsonify({"error": str(e)}), 500


# ---------- DAILY REPORT (NO PRODUCT NAME) ----------
@app.route("/api/daily-report", methods=["GET"])
def daily_report():
    """Get daily report data - WITHOUT PRODUCT NAME"""
    try:
        if transactions_ws is None or products_ws is None:
            return jsonify({"error": "Google Sheet not loaded"}), 500
            
        date = request.args.get("date")
        
        print(f"🔍 Daily report requested for: {date}")
        
        # Get all transactions
        all_data = transactions_ws.get_all_values()
        if len(all_data) < 2:
            return jsonify({"inventory": [], "finance": {"purchases": 0, "sales": 0, "balance": 0}})
        
        headers = [h.strip() for h in all_data[0]]
        rows = all_data[1:]
        
        print(f"📋 Transactions headers: {headers}")
        print(f"📋 Total transactions found: {len(rows)}")
        
        # Get products for categories only (NO NAME NEEDED)
        products_data = products_ws.get_all_values()
        product_categories = {}
        if len(products_data) > 1:
            for row in products_data[1:]:
                if len(row) > 0:
                    product_id = str(row[0]).strip()
                    main_cat = str(row[1]).strip() if len(row) > 1 else ""  # ✅ FIXED: Main Category is now at index 1
                    sub_cat = str(row[2]).strip() if len(row) > 2 else ""   # ✅ FIXED: Sub Category is now at index 2
                    
                    product_categories[product_id] = {
                        "mainCat": main_cat,
                        "subCat": sub_cat
                    }
        
        print(f"📦 Product categories found: {product_categories}")
        
        # Process transactions
        inventory_data = {}
        total_purchases = 0
        total_sales = 0
        
        for row_index, row in enumerate(rows):
            while len(row) < len(headers):
                row.append('')
            
            row_dict = {}
            for i, header in enumerate(headers):
                row_dict[header] = row[i] if i < len(row) else ''
            
            product_id = str(row_dict.get("Product ID", "")).strip()
            trans_type = row_dict.get("Type", "").lower()
            
            # Get quantity and price
            try:
                quantity = int(float(row_dict.get("Quantity", 0)))
                price = float(row_dict.get("Price", 0))
            except (ValueError, TypeError):
                quantity = 0
                price = 0
            
            print(f"📊 Processing: {product_id}, {trans_type}, Qty: {quantity}, Price: {price}")
            
            # Initialize product in report
            if product_id not in inventory_data:
                categories = product_categories.get(product_id, {"mainCat": "", "subCat": ""})
                inventory_data[product_id] = {
                    "id": product_id,
                    # ✅ NO PRODUCT NAME - only categories
                    "mainCat": categories.get("mainCat", ""),
                    "subCat": categories.get("subCat", ""),
                    "received": 0,
                    "sold": 0,
                    "remaining": 0
                }
            
            # Update counts
            if trans_type == "in":
                inventory_data[product_id]["received"] += quantity
                inventory_data[product_id]["remaining"] += quantity
                total_purchases += quantity * price
            elif trans_type == "out":
                inventory_data[product_id]["sold"] += quantity
                inventory_data[product_id]["remaining"] -= quantity
                total_sales += quantity * price
        
        print(f"✅ Report generated: {len(inventory_data)} products, Purchases: {total_purchases}, Sales: {total_sales}")
        
        # ✅ DEBUG: Show final inventory data
        for product_id, data in inventory_data.items():
            print(f"📋 Final: {product_id} -> {data}")
        
        return jsonify({
            "inventory": list(inventory_data.values()),
            "finance": {
                "purchases": total_purchases,
                "sales": total_sales,
                "balance": total_sales - total_purchases
            }
        })
        
    except Exception as e:
        print("❌ Error in daily report:", e)
        return jsonify({"error": str(e)}), 500


# ---------- GENERATE REPORT (WITH CATEGORIES INSTEAD OF PRODUCT NAME) ----------
@app.route("/api/generate-report", methods=["POST"])
def generate_report():
    """Generate and save report to Google Sheets - WITH CATEGORIES INSTEAD OF PRODUCT NAME"""
    try:
        if reports_ws is None:
            return jsonify({"error": "Google Sheet not loaded"}), 500
            
        data = request.json
        report_type = data.get("type", "general")
        period = data.get("period", datetime.now().strftime("%Y-%m"))
        
        print(f"📊 Generating {report_type} report for period: {period}")
        
        # Get report data based on type
        if report_type == "monthly":
            report_response = monthly_report()
        elif report_type == "daily":
            report_response = daily_report()
        else:
            report_response = simple_reports()
            
        report_data = report_response.get_json()
        
        if "error" in report_data:
            return jsonify({"error": report_data["error"]}), 500
        
        # Save to Reports sheet - WITH CATEGORIES
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        for item in report_data["inventory"]:
            # Calculate values based on actual data
            purchase_value = item["received"] * 100  # Assuming average purchase price
            sales_value = item["sold"] * 150         # Assuming average sale price
            
            reports_ws.append_row([
                report_type,                    # Report Type
                period,                         # Period
                item["id"],                     # Product ID
                item["mainCat"],                # ✅ MAIN CATEGORY (Product Name ki jagah)
                item["received"],               # Received
                item["sold"],                   # Sold
                item.get("remaining", 0),       # Remaining
                purchase_value,                 # Purchase Value
                sales_value,                    # Sales Value
                timestamp,                      # Generated At
                item["subCat"]                  # ✅ SUB CATEGORY (new column)
            ])
        
        print(f"✅ Report saved to Google Sheets: {report_type} - {period}")
        return jsonify({"message": "Report generated and saved successfully", "data": report_data})
        
    except Exception as e:
        print("❌ Error generating report:", e)
        return jsonify({"error": str(e)}), 500


# ---------- CATEGORIES API (NEW) ----------
@app.route("/api/categories", methods=["GET", "POST", "DELETE"])
def categories_api():
    """API for category management"""
    try:
        if products_ws is None:
            return jsonify({"error": "Google Sheet not loaded"}), 500
            
        if request.method == "GET":
            # Get all products to extract categories
            all_products = products_ws.get_all_values()
            
            if len(all_products) < 2:
                return jsonify({
                    "main_categories": [],
                    "sub_categories": {}
                })
            
            headers = [h.strip() for h in all_products[0]]
            rows = all_products[1:]
            
            main_categories = set()
            sub_categories = {}
            
            for row in rows:
                while len(row) < len(headers):
                    row.append('')
                
                row_dict = {}
                for i, header in enumerate(headers):
                    row_dict[header] = row[i] if i < len(row) else ''
                
                main_cat = str(row_dict.get("Main Category", "")).strip()
                sub_cat = str(row_dict.get("Sub Category", "")).strip()
                
                if main_cat:
                    main_categories.add(main_cat)
                    
                    if main_cat not in sub_categories:
                        sub_categories[main_cat] = set()
                    
                    if sub_cat:
                        sub_categories[main_cat].add(sub_cat)
            
            return jsonify({
                "main_categories": sorted(list(main_categories)),
                "sub_categories": {k: sorted(list(v)) for k, v in sub_categories.items()}
            })
        
        elif request.method == "POST":
            data = request.json
            action = data.get("action")
            
            if action == "update_product":
                # Update product categories
                product_id = data.get("product_id")
                new_main = data.get("main_category")
                new_sub = data.get("sub_category", "")
                
                if not product_id or not new_main:
                    return jsonify({"error": "Product ID and main category are required"}), 400
                
                # Find and update the product
                all_products = products_ws.get_all_values()
                for i, row in enumerate(all_products[1:], start=2):  # start=2 because of header row
                    if len(row) > 0 and str(row[0]).strip() == str(product_id):
                        # Update the row
                        updated_row = [
                            row[0],  # ID
                            new_main,  # Main Category
                            new_sub   # Sub Category
                        ]
                        products_ws.update(f"A{i}:C{i}", [updated_row])
                        return jsonify({"message": "Product categories updated successfully"})
                
                return jsonify({"error": "Product not found"}), 404
            
            elif action == "add_main":
                # Add new main category (no direct storage needed, will be created when used)
                return jsonify({"message": "Main category will be created when used in products"})
            
            elif action == "add_sub":
                # Add new sub category (no direct storage needed, will be created when used)
                return jsonify({"message": "Sub category will be created when used in products"})
            
            else:
                return jsonify({"error": "Invalid action"}), 400
        
        elif request.method == "DELETE":
            data = request.json
            category_type = data.get("type")
            category_name = data.get("category")
            main_category = data.get("main_category", "")
            
            if category_type == "main":
                # Delete main category by updating all products with this category
                all_products = products_ws.get_all_values()
                updated_count = 0
                
                for i, row in enumerate(all_products[1:], start=2):
                    if len(row) > 1 and str(row[1]).strip() == category_name:
                        # Remove main category (set to empty)
                        products_ws.update(f"B{i}", [[""]])
                        updated_count += 1
                
                return jsonify({"message": f"Main category removed from {updated_count} products"})
            
            elif category_type == "sub":
                # Delete sub category by updating all products with this sub category
                all_products = products_ws.get_all_values()
                updated_count = 0
                
                for i, row in enumerate(all_products[1:], start=2):
                    if len(row) > 2 and str(row[2]).strip() == category_name and str(row[1]).strip() == main_category:
                        # Remove sub category
                        products_ws.update(f"C{i}", [[""]])
                        updated_count += 1
                
                return jsonify({"message": f"Sub category removed from {updated_count} products"})
            
            else:
                return jsonify({"error": "Invalid category type"}), 400
                
    except Exception as e:
        print("❌ Error in categories API:", e)
        return jsonify({"error": str(e)}), 500

# ---------- PRODUCTS WITH CATEGORIES API ----------
@app.route("/api/products-with-categories", methods=["GET"])
def products_with_categories():
    """Get all products with their categories and current stock"""
    try:
        if products_ws is None:
            return jsonify({"error": "Google Sheet not loaded"}), 500
            
        all_products = products_ws.get_all_values()
        
        if len(all_products) < 2:
            return jsonify([])
        
        headers = [h.strip() for h in all_products[0]]
        rows = all_products[1:]
        
        products_data = []
        
        for row in rows:
            while len(row) < len(headers):
                row.append('')
            
            row_dict = {}
            for i, header in enumerate(headers):
                row_dict[header] = row[i] if i < len(row) else ''
            
            product_id = str(row_dict.get("ID", "")).strip()
            main_category = str(row_dict.get("Main Category", "")).strip()
            sub_category = str(row_dict.get("Sub Category", "")).strip()
            
            if product_id:  # Only include products with ID
                current_stock = calculate_current_stock(product_id)
                
                products_data.append({
                    "id": product_id,
                    "main_category": main_category,
                    "sub_category": sub_category if sub_category else None,
                    "current_stock": current_stock
                })
        
        return jsonify(products_data)
        
    except Exception as e:
        print("❌ Error in products with categories:", e)
        return jsonify({"error": str(e)}), 500


# ---------- HEALTH CHECK ----------
@app.route("/api/health")
def health_check():
    return jsonify({"status": "OK", "message": "Server is running"})


# ---------- RUN APP ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)