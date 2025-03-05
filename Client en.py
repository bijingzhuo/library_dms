import ctypes
import tkinter as tk
from tkinter import messagebox, ttk, simpledialog
import requests
import ctypes


# --------------------- Server API URL ---------------------
API_URL = "http://127.0.0.1:8080"

# --------------------- Initialize Main Window ---------------------
root = tk.Tk()
root.title("Library Management System")
root.geometry("1000x700")
root.resizable(False, False)
root.configure(bg="#F0F8FF")

# --------------------- Global Variables ---------------------
user_role = None
user_id = None

# --------------------- Clear Window ---------------------
def clear_window():
    for widget in root.winfo_children():
        widget.destroy()

# --------------------- Bottom Navigation Buttons ---------------------
def add_nav_buttons(parent, back_callback):
    nav_frame = ttk.Frame(parent)
    nav_frame.pack(side="bottom", fill="x", pady=10, padx=20)
    ttk.Button(nav_frame, text="Back", command=back_callback).pack(side="left", padx=10)
    ttk.Button(nav_frame, text="Exit", command=show_welcome_page).pack(side="right", padx=10)

# --------------------- Welcome Page ---------------------
def show_welcome_page():
    clear_window()
    frame = ttk.Frame(root)
    frame.pack(expand=True)
    ttk.Label(frame, text="Welcome to the Library Management System", font=("Helvetica", 28)).pack(pady=30)
    ttk.Button(frame, text="Enter System", command=show_identity_page, width=20).pack(pady=20)

# --------------------- Identity Selection Page ---------------------
def show_identity_page():
    clear_window()
    frame = ttk.Frame(root)
    frame.pack(expand=True)
    ttk.Label(frame, text="Please choose an identity:", font=("Helvetica", 24)).pack(pady=30)
    ttk.Button(frame, text="Employee", command=lambda: show_login_page("employee"), width=20).pack(pady=10)
    ttk.Button(frame, text="Member", command=lambda: show_login_page("member"), width=20).pack(pady=10)
    add_nav_buttons(frame, show_welcome_page)

# --------------------- Login Page ---------------------
def show_login_page(role):
    clear_window()
    frame = ttk.Frame(root)
    frame.pack(expand=True)
    ttk.Label(frame, text=f"{role} Login", font=("Helvetica", 24)).pack(pady=20)
    
    ttk.Label(frame, text="ID:").pack()
    entry_id = ttk.Entry(frame, width=30)
    entry_id.pack(pady=5)
    ttk.Label(frame, text="Password:").pack()
    entry_pw = ttk.Entry(frame, width=30, show="*")
    entry_pw.pack(pady=5)
    
    def attempt_login():
        global user_role, user_id
        user_id = entry_id.get().strip()
        password = entry_pw.get().strip()
        try:
            response = requests.post(f"{API_URL}/login", json={"user_id": user_id, "password": password, "role": role})
            if response.status_code == 200:
                data = response.json()
                messagebox.showinfo("Login Successful", f"Welcome {data['name']}!")
                user_role = role
                show_main_page()
            else:
                messagebox.showerror("Login Failed", response.json().get("message", "ID or password incorrect"))
        except Exception as e:
            messagebox.showerror("Network Error", str(e))
    
    ttk.Button(frame, text="Login", command=attempt_login, width=20).pack(pady=20)
    add_nav_buttons(frame, show_identity_page)

# --------------------- Main Page (Different menus based on role) ---------------------
def show_main_page():
    clear_window()
    if user_role == "employee":
        show_employee_main_menu()
    elif user_role == "member":
        show_member_main_menu()

# ==================== Employee Interface Page ====================
def show_employee_main_menu():
    clear_window()
    frame = ttk.Frame(root)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Employee Operations Menu", font=("Helvetica", 24)).pack(pady=20)
    
    # Place function buttons inside a Frame (using grid or vertical layout)
    btn_frame = ttk.Frame(frame)
    btn_frame.pack(pady=10)
    ttk.Button(btn_frame, text="Browse Books", width=20, command=employee_browse_books).grid(row=0, column=0, padx=10, pady=10)
    ttk.Button(btn_frame, text="Add New Book", width=20, command=employee_add_book).grid(row=1, column=0, padx=10, pady=10)
    ttk.Button(btn_frame, text="Update Book Information", width=20, command=employee_update_book).grid(row=0, column=1, padx=10, pady=10)
    ttk.Button(btn_frame, text="Delete Book Copy", width=20, command=employee_delete_book_copy).grid(row=1, column=1, padx=10, pady=10)
    ttk.Button(btn_frame, text="View Borrow Records", width=20, command=employee_view_borrow_records).grid(row=2, column=0, padx=10, pady=10)
    ttk.Button(btn_frame, text="View Reservation Records", width=20, command=employee_view_reservation_records).grid(row=2, column=1, padx=10, pady=10)
    
    add_nav_buttons(frame, show_identity_page)

def employee_browse_books():
    clear_window()
    frame = ttk.Frame(root)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Browse Books", font=("Helvetica", 24)).pack(pady=20)
    
    # ====================== Add Search Filter Components ======================
    search_frame = ttk.Frame(frame)
    search_frame.pack(pady=10)
    
    # Search Type Dropdown
    ttk.Label(search_frame, text="Search Type:").pack(side="left")
    search_type = ttk.Combobox(search_frame, 
                             values=["All", "Title", "ISBN", "Author", "Category", "Year"], 
                             state="readonly",
                             width=8)
    search_type.set("All")
    search_type.pack(side="left", padx=5)
    
    # Keyword Input Box
    ttk.Label(search_frame, text="Keyword:").pack(side="left")
    search_var = tk.StringVar()
    search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
    search_entry.pack(side="left", padx=5)
    
    # Search Button
    ttk.Button(search_frame, text="Search", command=lambda: load_books(search_type.get(), search_var.get())).pack(side="left", padx=5)
    # ============================================================
    
    # Treeview with Scrollbar
    tree_frame = ttk.Frame(frame)
    tree_frame.pack(pady=10, fill="both", expand=True)
    
    scroll_y = ttk.Scrollbar(tree_frame)
    scroll_y.pack(side="right", fill="y")
    
    columns = ('ISBN', 'Title', 'Year', 'Status', 'Authors', 'Categories')
    tree = ttk.Treeview(
        tree_frame, 
        columns=columns, 
        show='headings',
        yscrollcommand=scroll_y.set
    )
    scroll_y.config(command=tree.yview)
    
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=120, anchor="center")
    tree.pack(fill="both", expand=True)
    
    # Double-click to view copy status (employee-only feature)
    def on_item_double_click(event):
        selected_item = tree.selection()
        if selected_item:
            isbn = tree.item(selected_item, "values")[0]
            show_copy_status(isbn)  # Display copy status
    
    tree.bind("<Double-1>", on_item_double_click)
    
    # ====================== Unified Book Loading Method ======================
    def load_books(search_type_name, keyword):
        try:
            # Map search type to API parameter
            type_mapping = {
                "All": "5", 
                "Title": "1", 
                "ISBN": "5", 
                "Author": "4", 
                "Category": "2", 
                "Year": "3"
            }
            params = {
                "keyword": keyword.strip(),
                "search_type": type_mapping.get(search_type_name, "5")
            }
            
            response = requests.get(f"{API_URL}/searchBooks", params=params)
            if response.status_code == 200:
                books = response.json()
                tree.delete(*tree.get_children())
                for book in books:
                    tree.insert("", "end", values=(
                        book["isbn"], 
                        book["title"], 
                        book["publishyear"], 
                        book["status"],
                        book["authors"], 
                        book["categories"]
                    ))
            else:
                messagebox.showerror("Error", response.json().get("message", "Search failed"))
        except Exception as e:
            messagebox.showerror("Network Error", str(e))
    # ============================================================
    
    # Initially load all data
    load_books("All", "")
    add_nav_buttons(frame, show_employee_main_menu)

# ====================== Function to View Copy Status (Employee Only) ======================
def show_copy_status(isbn):
    copy_window = tk.Toplevel()
    copy_window.title(f"Copy Status - ISBN: {isbn}")
    copy_window.geometry("800x400")
    
    try:
        response = requests.get(f"{API_URL}/bookCopies", params={"isbn": isbn})
        if response.status_code != 200:
            raise ValueError("Failed to retrieve copy data")
        copies = response.json()
    except Exception as e:
        messagebox.showerror("Error", str(e))
        copy_window.destroy()
        return
    
    # Create Treeview component
    tree_frame = ttk.Frame(copy_window)
    tree_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    scroll_y = ttk.Scrollbar(tree_frame)
    scroll_y.pack(side="right", fill="y")
    
    columns = ("CopyID", "Status", "CreatedAt", "UpdatedAt")
    copy_tree = ttk.Treeview(
        tree_frame,
        columns=columns,
        show="headings",
        yscrollcommand=scroll_y.set
    )
    scroll_y.config(command=copy_tree.yview)
    
    # Configure columns
    for col in columns:
        copy_tree.heading(col, text=col)
        copy_tree.column(col, width=150, anchor="center")
    copy_tree.pack(fill="both", expand=True)
    
    # Populate data
    for copy in copies:
        copy_tree.insert("", "end", values=(
            copy["copyid"],
            copy["status"],
            copy["createdat"],
            copy["updatedat"]
        ))
        
    ttk.Button(copy_window, text="Close", command=copy_window.destroy).pack(pady=10)

# Member functions remain unchanged for employee_add_book
def employee_add_book():
    clear_window()
    frame = ttk.Frame(root)
    frame.pack(pady=20)
    
    ttk.Label(frame, text="Add New Book / Add Book Copy", font=("Helvetica", 24)).pack(pady=10)
    
    # Step 1: Enter ISBN
    isbn_frame = ttk.Frame(frame)
    isbn_frame.pack(pady=5)
    ttk.Label(isbn_frame, text="ISBN:").pack(side="left")
    isbn_entry = ttk.Entry(isbn_frame, width=40)
    isbn_entry.pack(side="left", padx=5)
    
    # Flag to store existence, using list for mutability in closure
    book_exists = [False]
    
    # Frame to store detailed info (initially hidden)
    details_frame = ttk.Frame(frame)
    
    # Show different input items based on whether it is a new book
    def show_details():
        # Clear existing widgets in details_frame
        for widget in details_frame.winfo_children():
            widget.destroy()
        if not book_exists[0]:
            # New book: show Title, Publication Year, Author, Category
            title_row = ttk.Frame(details_frame)
            title_row.pack(pady=5, fill="x", padx=20)
            ttk.Label(title_row, text="Title:", width=20, anchor="w").pack(side="left")
            title_entry = ttk.Entry(title_row, width=40)
            title_entry.pack(side="left")
            details_frame.title_entry = title_entry

            publish_row = ttk.Frame(details_frame)
            publish_row.pack(pady=5, fill="x", padx=20)
            ttk.Label(publish_row, text="Publication Year:", width=20, anchor="w").pack(side="left")
            publish_entry = ttk.Entry(publish_row, width=40)
            publish_entry.pack(side="left")
            details_frame.publish_entry = publish_entry

            authors_row = ttk.Frame(details_frame)
            authors_row.pack(pady=5, fill="x", padx=20)
            ttk.Label(authors_row, text="Author(s) (comma-separated):", width=20, anchor="w").pack(side="left")
            authors_entry = ttk.Entry(authors_row, width=40)
            authors_entry.pack(side="left")
            details_frame.authors_entry = authors_entry

            categories_row = ttk.Frame(details_frame)
            categories_row.pack(pady=5, fill="x", padx=20)
            ttk.Label(categories_row, text="Category(ies) (comma-separated):", width=20, anchor="w").pack(side="left")
            categories_entry = ttk.Entry(categories_row, width=40)
            categories_entry.pack(side="left")
            details_frame.categories_entry = categories_entry
        
        # Regardless of new or existing book, need to input number of copies
        copies_row = ttk.Frame(details_frame)
        copies_row.pack(pady=5, fill="x", padx=20)
        ttk.Label(copies_row, text="Number of Copies:", width=20, anchor="w").pack(side="left")
        copies_entry = ttk.Entry(copies_row, width=40)
        copies_entry.pack(side="left")
        details_frame.copies_entry = copies_entry
        
        details_frame.pack(pady=10)
        ttk.Button(details_frame, text="Submit", command=submit_add, width=20).pack(pady=20)
    
    # Check if ISBN already exists (assume backend returns 200 if exists)
    def check_isbn():
        isbn = isbn_entry.get().strip()
        if not isbn:
            messagebox.showerror("Error", "ISBN cannot be empty")
            return
        try:
            response = requests.get(f"{API_URL}/books/{isbn}")
            if response.status_code == 200:
                book_exists[0] = True
                messagebox.showinfo("Notice", "This book already exists, you only need to enter the number of copies")
            else:
                book_exists[0] = False
                messagebox.showinfo("Notice", "This is a new book, please fill in all information")
        except Exception as e:
            # If query fails, default to treating as new book
            book_exists[0] = False
        show_details()
    
    # Submit handler
    def submit_add():
        isbn = isbn_entry.get().strip()
        copies_str = details_frame.copies_entry.get().strip()
        try:
            copies = int(copies_str)
            if copies < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "The number of copies must be an integer greater than 0")
            return
        
        if book_exists[0]:
            # Existing book, submit only ISBN and number of copies
            payload = {
                "employee_id": user_id,
                "isbn": isbn,
                "copies": copies
            }
            try:
                response = requests.post(f"{API_URL}/addBook", json=payload)
                if response.status_code == 200:
                    data = response.json()
                    messagebox.showinfo("Success", data["message"])
                    show_employee_main_menu()
                else:
                    messagebox.showerror("Failed", response.json().get("message", "Addition failed"))
            except Exception as e:
                messagebox.showerror("Network Error", str(e))
        else:
            # New book: need to submit full information
            title = details_frame.title_entry.get().strip()
            publishyear = details_frame.publish_entry.get().strip()
            authors = [a.strip() for a in details_frame.authors_entry.get().split(",") if a.strip()]
            categories = [c.strip() for c in details_frame.categories_entry.get().split(",") if c.strip()]
            if not title:
                messagebox.showerror("Error", "New book must have a title")
                return
            if not publishyear or not publishyear.isdigit():
                messagebox.showerror("Error", "Publication year must be a number")
                return
            if not authors and not categories:
                messagebox.showerror("Error", "New book must have at least one author or category")
                return
            payload = {
                "employee_id": user_id,
                "isbn": isbn,
                "title": title,
                "publishyear": publishyear,
                "authors": authors,
                "categories": categories,
                "copies": copies
            }
            try:
                response = requests.post(f"{API_URL}/addBook", json=payload)
                if response.status_code == 200:
                    data = response.json()
                    messagebox.showinfo("Success", data["message"])
                    show_employee_main_menu()
                else:
                    messagebox.showerror("Failed", response.json().get("message", "Addition failed"))
            except Exception as e:
                messagebox.showerror("Network Error", str(e))
    
    # Check ISBN Button
    ttk.Button(frame, text="Check ISBN", command=check_isbn, width=20).pack(pady=10)
    add_nav_buttons(frame, show_employee_main_menu)

def employee_update_book():
    clear_window()
    frame = ttk.Frame(root)
    frame.pack(pady=20)
    ttk.Label(frame, text="Update / Delete Book", font=("Helvetica", 24)).pack(pady=10)
    
    # ISBN
    isbn_row = ttk.Frame(frame)
    isbn_row.pack(pady=5, fill="x", padx=20)
    ttk.Label(isbn_row, text="ISBN:", width=20, anchor="w").pack(side="left")
    isbn_entry = ttk.Entry(isbn_row, width=40)
    isbn_entry.pack(side="left")

    # Title
    title_row = ttk.Frame(frame)
    title_row.pack(pady=5, fill="x", padx=20)
    ttk.Label(title_row, text="New Title:", width=20, anchor="w").pack(side="left")
    title_entry = ttk.Entry(title_row, width=40)
    title_entry.pack(side="left")

    # Publish Year
    year_row = ttk.Frame(frame)
    year_row.pack(pady=5, fill="x", padx=20)
    ttk.Label(year_row, text="New Publish Year:", width=20, anchor="w").pack(side="left")
    year_entry = ttk.Entry(year_row, width=40)
    year_entry.pack(side="left")

    # ============ 更新按钮 ============ 
    def submit_update():
        isbn = isbn_entry.get().strip()
        new_title = title_entry.get().strip()
        new_publishyear = year_entry.get().strip()
        payload = {
            "employee_id": user_id,  # 全局保存的当前登录员工ID
            "isbn": isbn,
            "title": new_title,
            "publishyear": new_publishyear
        }
        try:
            response = requests.put(f"{API_URL}/updateBook", json=payload)
            if response.status_code == 200:
                messagebox.showinfo("Success", response.json()["message"])
                show_employee_main_menu()
            else:
                messagebox.showerror("Failed", response.json().get("message", "Update failed"))
        except Exception as e:
            messagebox.showerror("Network Error", str(e))

    ttk.Button(frame, text="Update Book", command=submit_update, width=20).pack(pady=10)

    # ============ 删除按钮 ============ 
    def submit_delete():
        isbn = isbn_entry.get().strip()
        if not isbn:
            messagebox.showwarning("Warning", "Please enter ISBN to delete.")
            return
        # 二次确认
        if not messagebox.askyesno("Confirm", f"Do you really want to delete the book (ISBN={isbn})?"):
            return
        payload = {
            "employee_id": user_id,
            "isbn": isbn
        }
        try:
            # DELETE 方法
            response = requests.delete(f"{API_URL}/deleteBook", json=payload)
            if response.status_code == 200:
                data = response.json()
                if data["status"] == "success":
                    messagebox.showinfo("Success", data["message"])
                    show_employee_main_menu()
                else:
                    messagebox.showerror("Failed", data.get("message", "Delete failed"))
            else:
                # 处理非200的错误信息
                err_data = response.json()
                messagebox.showerror("Failed", err_data.get("message", "Delete failed"))
        except Exception as e:
            messagebox.showerror("Network Error", str(e))

    ttk.Button(frame, text="Delete Book", command=submit_delete, width=20).pack(pady=10)

    add_nav_buttons(frame, show_employee_main_menu)


def employee_delete_book_copy():
    clear_window()
    frame = ttk.Frame(root)
    frame.pack(pady=20)
    ttk.Label(frame, text="Delete Book Copy", font=("Helvetica", 24)).pack(pady=10)
    
    # Step 1: Enter ISBN and Query Book Copies Button
    isbn_frame = ttk.Frame(frame)
    isbn_frame.pack(pady=5, fill="x", padx=20)
    ttk.Label(isbn_frame, text="ISBN:", width=25, anchor="w").pack(side="left")
    isbn_entry = ttk.Entry(isbn_frame, width=40)
    isbn_entry.pack(side="left")
    
    # Frame to display queried book copy information
    results_frame = ttk.Frame(frame)
    results_frame.pack(pady=10, fill="both", expand=True, padx=20)
    tree = ttk.Treeview(results_frame, columns=("CopyID", "Status"), show="headings", height=5)
    tree.heading("CopyID", text="Copy ID")
    tree.heading("Status", text="Status")
    tree.pack(side="left", fill="both", expand=True)
    scrollbar = ttk.Scrollbar(results_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    
    def query_copies():
        isbn = isbn_entry.get().strip()
        if not isbn:
            messagebox.showerror("Error", "Please enter ISBN")
            return
        try:
            response = requests.get(f"{API_URL}/bookCopies", params={"isbn": isbn})
            if response.status_code == 200:
                copies = response.json()
                tree.delete(*tree.get_children())
                if copies:
                    for copy in copies:
                        tree.insert("", "end", values=(copy["copyid"], copy["status"]))
                else:
                    messagebox.showinfo("Notice", "No book copies found under this ISBN")
            else:
                messagebox.showerror("Error", response.json().get("message", "Query failed"))
        except Exception as e:
            messagebox.showerror("Network Error", str(e))
    
    ttk.Button(frame, text="Query Book Copies", command=query_copies, width=20).pack(pady=5)
    
    # Step 2: Select Copy ID and Submit Deletion
    selection_frame = ttk.Frame(frame)
    selection_frame.pack(pady=5, fill="x", padx=20)
    ttk.Label(selection_frame, text="Select the Copy ID to delete:", width=25, anchor="w").pack(side="left")
    copyid_entry = ttk.Entry(selection_frame, width=40)
    copyid_entry.pack(side="left")
    
    def submit_delete():
        isbn = isbn_entry.get().strip()
        copy_id = copyid_entry.get().strip()
        if not isbn or not copy_id:
            messagebox.showerror("Error", "Please ensure both ISBN and Copy ID are filled")
            return
        try:
            # Wrap single copy ID into a list
            payload = {
                "employee_id": user_id,
                "isbn": isbn,
                "copy_ids": [int(copy_id)]
            }
        except Exception:
            messagebox.showerror("Input Error", "Copy ID should be a number")
            return
        
        try:
            response = requests.delete(f"{API_URL}/deleteBookCopy", json=payload)
            if response.status_code == 200:
                data = response.json()
                msg = f"Updated successfully: {data['updated']}\nSkipped: {data['skipped']}"
                messagebox.showinfo("Result", msg)
                show_employee_main_menu()
            else:
                messagebox.showerror("Failed", response.json().get("message", "Deletion failed"))
        except Exception as e:
            messagebox.showerror("Network Error", str(e))
    
    ttk.Button(frame, text="Submit Deletion", command=submit_delete, width=20).pack(pady=20)
    add_nav_buttons(frame, show_employee_main_menu)


def employee_view_borrow_records():
    clear_window()
    frame = ttk.Frame(root)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Borrow Records", font=("Helvetica", 24)).pack(pady=10)
    
    # Add search filter components
    search_frame = ttk.Frame(frame)
    search_frame.pack(pady=10)
    ttk.Label(search_frame, text="Filter Type:").pack(side="left")
    search_type = ttk.Combobox(search_frame, 
                             values=["All", "Borrow ID", "ISBN", "Member ID"], 
                             state="readonly",
                             width=8)
    search_type.set("All")
    search_type.pack(side="left", padx=5)
    ttk.Label(search_frame, text="Keyword:").pack(side="left")
    filter_var = tk.StringVar()
    search_entry = ttk.Entry(search_frame, textvariable=filter_var, width=30)
    search_entry.pack(side="left", padx=5)
    ttk.Button(search_frame, text="Query", command=lambda: load_borrow_records(search_type.get(), filter_var.get())).pack(side="left", padx=5)
    
    tree_frame = ttk.Frame(frame)
    tree_frame.pack(fill="both", expand=True, padx=20, pady=10)
    columns = ("BorrowID", "MemberID", "ISBN", "BorrowDate", "DueDate", "ReturnDate", "CopyID")
    tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=120, anchor="center")
    tree.pack(fill="both", expand=True)
    
    def load_borrow_records(search_type_value, keyword):
        try:
            params = {}
            if keyword:
                type_mapping = {
                    "Borrow ID": "borrowid",
                    "ISBN": "isbn",
                    "Member ID": "memberid"
                }
                if search_type_value != "All":
                    params["filter_type"] = type_mapping.get(search_type_value, "borrowid")
                    params["filter_value"] = keyword.strip()
                else:
                    # For "All", backend may implement fuzzy matching on multiple fields or choose a default rule
                    params["filter_type"] = "all"
                    params["filter_value"] = keyword.strip()
            response = requests.get(f"{API_URL}/borrowRecords", params=params)
            if response.status_code == 200:
                records = response.json()
                tree.delete(*tree.get_children())
                for r in records:
                    tree.insert("", "end", values=(r["borrowid"], r["memberid"], r["isbn"], r["borrowdate"], r["duedate"], r["returndate"], r["copyid"]))
            else:
                messagebox.showerror("Error", response.json().get("message", "Query failed"))
        except Exception as e:
            messagebox.showerror("Network Error", str(e))
    
    load_borrow_records("All", "")
    add_nav_buttons(frame, show_employee_main_menu)


def employee_view_reservation_records():
    clear_window()
    frame = ttk.Frame(root)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Reservation Records", font=("Helvetica", 24)).pack(pady=10)
    
    # Add search filter components
    search_frame = ttk.Frame(frame)
    search_frame.pack(pady=10)
    ttk.Label(search_frame, text="Filter Type:").pack(side="left")
    search_type = ttk.Combobox(search_frame, 
                             values=["All", "Reservation ID", "ISBN", "Member ID"], 
                             state="readonly",
                             width=8)
    search_type.set("All")
    search_type.pack(side="left", padx=5)
    ttk.Label(search_frame, text="Keyword:").pack(side="left")
    filter_var = tk.StringVar()
    search_entry = ttk.Entry(search_frame, textvariable=filter_var, width=30)
    search_entry.pack(side="left", padx=5)
    ttk.Button(search_frame, text="Query", command=lambda: load_reservation_records(search_type.get(), filter_var.get())).pack(side="left", padx=5)
    
    tree_frame = ttk.Frame(frame)
    tree_frame.pack(fill="both", expand=True, padx=20, pady=10)
    columns = ("ReservationID", "MemberID", "ISBN", "ReservationDate", "Status", "QueueNumber", "PickupDeadline")
    tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=120, anchor="center")
    tree.pack(fill="both", expand=True)
    
    def load_reservation_records(search_type_value, keyword):
        try:
            params = {}
            if keyword:
                type_mapping = {
                    "Reservation ID": "reservationid",
                    "ISBN": "isbn",
                    "Member ID": "memberid"
                }
                if search_type_value != "All":
                    params["filter_type"] = type_mapping.get(search_type_value, "reservationid")
                    params["filter_value"] = keyword.strip()
                else:
                    params["filter_type"] = "all"
                    params["filter_value"] = keyword.strip()
            response = requests.get(f"{API_URL}/reservationRecords", params=params)
            if response.status_code == 200:
                records = response.json()
                tree.delete(*tree.get_children())
                for r in records:
                    tree.insert("", "end", values=(r["reservationid"], r["memberid"], r["isbn"], r["reservationdate"], r["status"], r["queuenumber"], r["pickupdeadline"]))
            else:
                messagebox.showerror("Error", response.json().get("message", "Query failed"))
        except Exception as e:
            messagebox.showerror("Network Error", str(e))
    
    load_reservation_records("All", "")
    add_nav_buttons(frame, show_employee_main_menu)

# ==================== Member Interface Page ====================
def show_member_main_menu():
    clear_window()
    frame = ttk.Frame(root)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Member Operations Menu", font=("Helvetica", 24)).pack(pady=20)
    
    btn_frame = ttk.Frame(frame)
    btn_frame.pack(pady=10)
    ttk.Button(btn_frame, text="Borrow Book", width=20, command=member_borrow_book).grid(row=0, column=0, padx=10, pady=10)
    ttk.Button(btn_frame, text="Return Book", width=20, command=member_return_book).grid(row=0, column=1, padx=10, pady=10)
    ttk.Button(btn_frame, text="Reserve Book", width=20, command=member_reserve_book).grid(row=1, column=0, padx=10, pady=10)
    ttk.Button(btn_frame, text="Cancel Reservation", width=20, command=member_cancel_reservation).grid(row=1, column=1, padx=10, pady=10)
    ttk.Button(btn_frame, text="My Borrow Records", width=20, command=member_view_borrow_records).grid(row=2, column=0, padx=10, pady=10)
    ttk.Button(btn_frame, text="My Reservation Records", width=20, command=member_view_reservation_records).grid(row=2, column=1, padx=10, pady=10)
    
    add_nav_buttons(frame, show_identity_page)



def member_borrow_book():
    clear_window()
    frame = ttk.Frame(root)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Select Book to Borrow", font=("Helvetica", 24)).pack(pady=20)
    
    # Add search filter components (same as browse books page)
    search_frame = ttk.Frame(frame)
    search_frame.pack(pady=10)
    ttk.Label(search_frame, text="Search Type:").pack(side="left")
    search_type = ttk.Combobox(search_frame, values=["All", "Title", "ISBN", "Author", "Category", "Year"], state="readonly")
    search_type.set("All")
    search_type.pack(side="left", padx=5)
    ttk.Label(search_frame, text="Keyword:").pack(side="left")
    search_var = tk.StringVar()
    search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
    search_entry.pack(side="left", padx=5)
    ttk.Button(search_frame, text="Search", command=lambda: load_books(search_type.get(), search_var.get())).pack(side="left", padx=5)
    
    tree_frame = ttk.Frame(frame)
    tree_frame.pack(pady=10, fill="both", expand=True)
    columns = ('ISBN', 'Title', 'Year', 'Status')
    tree = ttk.Treeview(tree_frame, columns=columns, show='headings')
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=150, anchor="center")
    tree.pack(fill="both", expand=True)
    
    def load_books(search_type_value, keyword):
        try:
            # Map search type to corresponding API parameter (same as browse books page)
            mapping = {
                "All": "5", 
                "Title": "1", 
                "ISBN": "5", 
                "Author": "4", 
                "Category": "2", 
                "Year": "3"
            }
            params = {
                "keyword": keyword.strip(),
                "search_type": mapping.get(search_type_value, "5")
            }
            response = requests.get(f"{API_URL}/searchBooks", params=params)
            if response.status_code == 200:
                books = response.json()
                tree.delete(*tree.get_children())
                for book in books:
                    tree.insert("", "end", values=(
                        book["isbn"], 
                        book["title"], 
                        book["publishyear"], 
                        book["status"]
                    ))
            else:
                messagebox.showerror("Error", response.json().get("message", "Search failed"))
        except Exception as e:
            messagebox.showerror("Network Error", str(e))
    
    load_books("All", "")
    
    def submit_borrow():
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("Notice", "Please select a book")
            return
        book_isbn = tree.item(selected, "values")[0]
        try:
            response = requests.post(f"{API_URL}/borrow", json={"member_id": user_id, "isbn": book_isbn})
            if response.status_code == 200:
                data = response.json()
                messagebox.showinfo("Success", f"Borrow successful! Borrow ID: {data['borrow_id']}\nAssigned Copy: {data['assigned_copy']}")
                show_member_main_menu()
            else:
                messagebox.showerror("Failed", response.json().get("message", "Borrow failed"))
        except Exception as e:
            messagebox.showerror("Network Error", str(e))
    
    ttk.Button(frame, text="Borrow Selected Book", command=submit_borrow, width=20).pack(pady=10)
    add_nav_buttons(frame, show_member_main_menu)

def member_return_book():
    clear_window()
    frame = ttk.Frame(root)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Return Book", font=("Helvetica", 24)).pack(pady=20)
    
    # Add search filter components
    search_frame = ttk.Frame(frame)
    search_frame.pack(pady=10)
    ttk.Label(search_frame, text="Filter Type:").pack(side="left")
    search_type = ttk.Combobox(search_frame, 
                             values=["All", "Borrow ID", "ISBN"], 
                             state="readonly", width=8)
    search_type.set("All")
    search_type.pack(side="left", padx=5)
    ttk.Label(search_frame, text="Keyword:").pack(side="left")
    filter_var = tk.StringVar()
    search_entry = ttk.Entry(search_frame, textvariable=filter_var, width=30)
    search_entry.pack(side="left", padx=5)
    ttk.Button(search_frame, text="Query", 
               command=lambda: load_my_borrows(search_type.get(), filter_var.get())
              ).pack(side="left", padx=5)
    
    # Create Treeview to display borrow records
    tree_frame = ttk.Frame(frame)
    tree_frame.pack(pady=10, fill="both", expand=True)
    columns = ("BorrowID", "ISBN", "CopyID", "BorrowDate", "DueDate")
    tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=120, anchor="center")
    tree.pack(fill="both", expand=True)
    
    def load_my_borrows(search_type_value, keyword):
        try:
            params = {}
            if keyword:
                type_mapping = {
                    "Borrow ID": "borrowid",
                    "ISBN": "isbn"
                }
                if search_type_value != "All":
                    params["filter_type"] = type_mapping.get(search_type_value, "borrowid")
                    params["filter_value"] = keyword.strip()
                else:
                    params["filter_type"] = "all"
                    params["filter_value"] = keyword.strip()
            response = requests.get(f"{API_URL}/borrowRecords", params=params)
            if response.status_code == 200:
                records = response.json()
                tree.delete(*tree.get_children())
                for r in records:
                    # Only display records for the current member that have not been returned
                    if str(r["memberid"]) == user_id and r["returndate"] is None:
                        tree.insert("", "end", values=(
                            r["borrowid"], r["isbn"], r["copyid"], r["borrowdate"], r["duedate"]
                        ))
            else:
                messagebox.showerror("Error", response.json().get("message", "Query failed"))
        except Exception as e:
            messagebox.showerror("Network Error", str(e))
    
    load_my_borrows("All", "")
    
    def submit_return():
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("Notice", "Please select a borrow record")
            return
        borrow_id = tree.item(selected, "values")[0]
        try:
            response = requests.post(f"{API_URL}/return", json={"borrow_id": borrow_id})
            if response.status_code == 200:
                messagebox.showinfo("Success", "Return successful")
                show_member_main_menu()
            else:
                messagebox.showerror("Failed", response.json().get("message", "Return failed"))
        except Exception as e:
            messagebox.showerror("Network Error", str(e))
    
    ttk.Button(frame, text="Return Selected Book", command=submit_return, width=20).pack(pady=10)
    add_nav_buttons(frame, show_member_main_menu)


def member_reserve_book():
    clear_window()
    frame = ttk.Frame(root)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Reserve Book", font=("Helvetica", 24)).pack(pady=20)
    
    # Add search filter components, same as browse books page
    search_frame = ttk.Frame(frame)
    search_frame.pack(pady=10)
    ttk.Label(search_frame, text="Search Type:").pack(side="left")
    search_type = ttk.Combobox(search_frame, 
                               values=["All", "Title", "ISBN", "Author", "Category", "Year"],
                               state="readonly", width=8)
    search_type.set("All")
    search_type.pack(side="left", padx=5)
    ttk.Label(search_frame, text="Keyword:").pack(side="left")
    search_var = tk.StringVar()
    search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
    search_entry.pack(side="left", padx=5)
    ttk.Button(search_frame, text="Search", 
               command=lambda: load_books(search_type.get(), search_var.get())
              ).pack(side="left", padx=5)
    
    # Create Treeview to display book information
    tree_frame = ttk.Frame(frame)
    tree_frame.pack(pady=10, fill="both", expand=True)
    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical")
    scrollbar.pack(side="right", fill="y")
    columns = ('ISBN', 'Title', 'Year', 'Status', 'Authors', 'Categories')
    tree = ttk.Treeview(tree_frame, columns=columns, show='headings', yscrollcommand=scrollbar.set)
    scrollbar.config(command=tree.yview)
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=120, anchor="center")
    tree.pack(fill="both", expand=True)
    
    # Function to load book data based on search criteria
    def load_books(search_type_value, keyword):
        try:
            # Map search type to API parameter value (same as browse books page)
            type_mapping = {"All": "5", "Title": "1", "ISBN": "5", "Author": "4", "Category": "2", "Year": "3"}
            params = {
                "keyword": keyword.strip(),
                "search_type": type_mapping.get(search_type_value, "5")
            }
            response = requests.get(f"{API_URL}/searchBooks", params=params)
            if response.status_code == 200:
                books = response.json()
                tree.delete(*tree.get_children())
                for book in books:
                    tree.insert("", "end", values=(
                        book["isbn"],
                        book["title"],
                        book["publishyear"],
                        book["status"],
                        book["authors"],
                        book["categories"]
                    ))
            else:
                messagebox.showerror("Error", response.json().get("message", "Search failed"))
        except Exception as e:
            messagebox.showerror("Network Error", str(e))
    
    # Initially load all books
    load_books("All", "")
    
    # Function to submit a reservation: select a book then call the reservation API
    def submit_reservation():
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("Notice", "Please select a book to reserve")
            return
        # Retrieve ISBN from the first column of the selected row
        selected_book = tree.item(selected, "values")
        isbn = selected_book[0]
        try:
            response = requests.post(f"{API_URL}/reserve", json={"member_id": user_id, "isbn": isbn})
            if response.status_code == 200:
                queue_number = response.json().get("queue_number", "Unknown")
                messagebox.showinfo("Success", f"Reservation successful!")
                show_member_main_menu()
            else:
                messagebox.showerror("Failed", response.json().get("message", "Reservation failed"))
        except Exception as e:
            messagebox.showerror("Network Error", str(e))
    
    ttk.Button(frame, text="Reserve Selected Book", command=submit_reservation, width=20).pack(pady=10)
    add_nav_buttons(frame, show_member_main_menu)

def member_cancel_reservation():
    clear_window()
    frame = ttk.Frame(root)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Cancel Reservation", font=("Helvetica", 24)).pack(pady=20)
    
    # Add search filter components
    search_frame = ttk.Frame(frame)
    search_frame.pack(pady=10)
    ttk.Label(search_frame, text="Filter Type:").pack(side="left")
    search_type = ttk.Combobox(search_frame, 
                               values=["All", "Reservation ID", "ISBN"], 
                               state="readonly", width=8)
    search_type.set("All")
    search_type.pack(side="left", padx=5)
    ttk.Label(search_frame, text="Keyword:").pack(side="left")
    filter_var = tk.StringVar()
    search_entry = ttk.Entry(search_frame, textvariable=filter_var, width=30)
    search_entry.pack(side="left", padx=5)
    ttk.Button(search_frame, text="Query", 
               command=lambda: load_my_reservations(search_type.get(), filter_var.get())
              ).pack(side="left", padx=5)
    
    # Create Treeview to display current member's active reservations
    tree_frame = ttk.Frame(frame)
    tree_frame.pack(pady=10, fill="both", expand=True)
    columns = ("ReservationID", "ISBN", "ReservationDate", "QueueNumber")
    tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=120, anchor="center")
    tree.pack(fill="both", expand=True)
    
    def load_my_reservations(search_type_value, keyword):
        try:
            params = {}
            if keyword:
                type_mapping = {
                    "Reservation ID": "reservationid",
                    "ISBN": "isbn"
                }
                if search_type_value != "All":
                    params["filter_type"] = type_mapping.get(search_type_value, "reservationid")
                    params["filter_value"] = keyword.strip()
                else:
                    params["filter_type"] = "all"
                    params["filter_value"] = keyword.strip()
            response = requests.get(f"{API_URL}/reservationRecords", params=params)
            if response.status_code == 200:
                records = response.json()
                tree.delete(*tree.get_children())
                # Only display current member's active reservations
                for r in records:
                    if str(r["memberid"]) == user_id and r["status"] == "Active":
                        tree.insert("", "end", values=(
                            r["reservationid"], r["isbn"], r["reservationdate"], r["queuenumber"]
                        ))
            else:
                messagebox.showerror("Error", response.json().get("message", "Query failed"))
        except Exception as e:
            messagebox.showerror("Network Error", str(e))
    
    load_my_reservations("All", "")
    
    def submit_cancel():
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("Notice", "Please select a reservation record")
            return
        reservation_id = tree.item(selected, "values")[0]
        try:
            response = requests.post(f"{API_URL}/cancelReservation", 
                                     json={"member_id": user_id, "reservation_id": reservation_id})
            if response.status_code == 200:
                messagebox.showinfo("Success", "Reservation cancelled successfully")
                show_member_main_menu()
            else:
                messagebox.showerror("Failed", response.json().get("message", "Cancellation failed"))
        except Exception as e:
            messagebox.showerror("Network Error", str(e))
    
    ttk.Button(frame, text="Cancel Selected Reservation", command=submit_cancel, width=20).pack(pady=10)
    add_nav_buttons(frame, show_member_main_menu)

def member_view_borrow_records():
    clear_window()
    frame = ttk.Frame(root)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="My Borrow Records", font=("Helvetica", 24)).pack(pady=20)
    
    # Add search filter components
    search_frame = ttk.Frame(frame)
    search_frame.pack(pady=10)
    ttk.Label(search_frame, text="Filter Type:").pack(side="left")
    search_type = ttk.Combobox(search_frame,
                               values=["All", "Borrow ID", "ISBN"],
                               state="readonly", width=8)
    search_type.set("All")
    search_type.pack(side="left", padx=5)
    ttk.Label(search_frame, text="Keyword:").pack(side="left")
    filter_var = tk.StringVar()
    search_entry = ttk.Entry(search_frame, textvariable=filter_var, width=30)
    search_entry.pack(side="left", padx=5)
    ttk.Button(search_frame, text="Query",
               command=lambda: load_my_borrow_records(search_type.get(), filter_var.get())
              ).pack(side="left", padx=5)
    
    # Create Treeview to display borrow records
    tree_frame = ttk.Frame(frame)
    tree_frame.pack(pady=10, fill="both", expand=True)
    columns = ("BorrowID", "ISBN", "CopyID", "BorrowDate", "DueDate", "ReturnDate")
    tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=120, anchor="center")
    tree.pack(fill="both", expand=True)
    
    def load_my_borrow_records(search_type_value, keyword):
        try:
            params = {}
            if keyword:
                type_mapping = {
                    "Borrow ID": "borrowid",
                    "ISBN": "isbn"
                }
                if search_type_value != "All":
                    params["filter_type"] = type_mapping.get(search_type_value, "borrowid")
                    params["filter_value"] = keyword.strip()
                else:
                    params["filter_type"] = "all"
                    params["filter_value"] = keyword.strip()
            response = requests.get(f"{API_URL}/borrowRecords", params=params)
            if response.status_code == 200:
                records = response.json()
                tree.delete(*tree.get_children())
                for r in records:
                    # Only display records for the current member
                    if str(r["memberid"]) == user_id:
                        tree.insert("", "end", values=(
                            r["borrowid"], r["isbn"], r["copyid"], r["borrowdate"], r["duedate"], r["returndate"]
                        ))
            else:
                messagebox.showerror("Error", response.json().get("message", "Query failed"))
        except Exception as e:
            messagebox.showerror("Network Error", str(e))
    
    load_my_borrow_records("All", "")
    add_nav_buttons(frame, show_member_main_menu)
def member_view_reservation_records():
    clear_window()
    frame = ttk.Frame(root)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="My Reservation Records", font=("Helvetica", 24)).pack(pady=20)
    
    # Add search filter components
    search_frame = ttk.Frame(frame)
    search_frame.pack(pady=10)
    ttk.Label(search_frame, text="Filter Type:").pack(side="left")
    search_type = ttk.Combobox(search_frame,
                               values=["All", "Reservation ID", "ISBN"],
                               state="readonly", width=8)
    search_type.set("All")
    search_type.pack(side="left", padx=5)
    ttk.Label(search_frame, text="Keyword:").pack(side="left")
    filter_var = tk.StringVar()
    search_entry = ttk.Entry(search_frame, textvariable=filter_var, width=30)
    search_entry.pack(side="left", padx=5)
    ttk.Button(search_frame, text="Query",
               command=lambda: load_my_reservation_records(search_type.get(), filter_var.get())
              ).pack(side="left", padx=5)
    
    # Create Treeview to display reservation records
    tree_frame = ttk.Frame(frame)
    tree_frame.pack(pady=10, fill="both", expand=True)
    columns = ("ReservationID", "ISBN", "ReservationDate", "Status", "QueueNumber", "PickupDeadline")
    tree = ttk.Treeview(tree_frame, columns=columns, show="headings")
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=120, anchor="center")
    tree.pack(fill="both", expand=True)
    
    def load_my_reservation_records(search_type_value, keyword):
        try:
            params = {}
            if keyword:
                type_mapping = {
                    "Reservation ID": "reservationid",
                    "ISBN": "isbn"
                }
                if search_type_value != "All":
                    params["filter_type"] = type_mapping.get(search_type_value, "reservationid")
                    params["filter_value"] = keyword.strip()
                else:
                    params["filter_type"] = "all"
                    params["filter_value"] = keyword.strip()
            response = requests.get(f"{API_URL}/reservationRecords", params=params)
            if response.status_code == 200:
                records = response.json()
                tree.delete(*tree.get_children())
                # Display all reservation records for the current member
                for r in records:
                    if str(r["memberid"]) == user_id:
                        tree.insert("", "end", values=(
                            r["reservationid"], r["isbn"], r["reservationdate"], r["status"],
                            r["queuenumber"], r["pickupdeadline"]
                        ))
            else:
                messagebox.showerror("Error", response.json().get("message", "Query failed"))
        except Exception as e:
            messagebox.showerror("Network Error", str(e))
    
    load_my_reservation_records("All", "")
    add_nav_buttons(frame, show_member_main_menu)

# --------------------- Launch Application ---------------------
show_welcome_page()
root.mainloop()
