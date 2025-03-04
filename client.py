import tkinter as tk
from tkinter import messagebox, ttk
import requests
from PIL import Image, ImageTk

# --------------------- 服务器 API 地址 ---------------------
API_URL = "http://127.0.0.1:5000"

# --------------------- 初始化主窗口 ---------------------
root = tk.Tk()
root.title("图书馆管理系统")
root.geometry("800x600")
root.resizable(False, False)
root.configure(bg="#F0F8FF")  # 设置背景色

# --------------------- 变量 ---------------------
user_role = None
user_id = None

# --------------------- 清空窗口 ---------------------
def clear_window():
    for widget in root.winfo_children():
        widget.destroy()

# --------------------- 底部导航按钮 ---------------------
def add_nav_buttons(parent, back_callback):
    """
    在 parent（当前页面）底部添加 ‘返回’ 和 ‘退出’ 按钮
    back_callback: 返回上一个界面的函数
    """
    nav_frame = ttk.Frame(parent)
    nav_frame.pack(side="bottom", fill="x", pady=15, padx=20)

    btn_back = ttk.Button(nav_frame, text="返回", command=back_callback)
    btn_back.pack(side="left", padx=10)

    btn_exit = ttk.Button(nav_frame, text="退出", command=show_welcome_page)
    btn_exit.pack(side="right", padx=10)

# --------------------- 欢迎页面 ---------------------
def show_welcome_page():
    clear_window()
    frame = ttk.Frame(root)
    frame.pack(expand=True)

    label = ttk.Label(frame, text="欢迎使用图书馆管理系统", font=("Helvetica", 24))
    label.pack(pady=20)

    btn_enter = ttk.Button(frame, text="进入系统", command=show_identity_page)
    btn_enter.pack(pady=20)

# --------------------- 身份选择页面 ---------------------
def show_identity_page():
    clear_window()
    frame = ttk.Frame(root)
    frame.pack(expand=True)

    label = ttk.Label(frame, text="请选择身份：", font=("Helvetica", 20))
    label.pack(pady=20)

    btn_employee = ttk.Button(frame, text="员工", command=lambda: show_login_page("employee"))
    btn_employee.pack(pady=10)
    btn_member = ttk.Button(frame, text="会员", command=lambda: show_login_page("member"))
    btn_member.pack(pady=10)

    add_nav_buttons(frame, show_welcome_page)

# --------------------- 登录页面 ---------------------
def show_login_page(role):
    clear_window()
    frame = ttk.Frame(root)
    frame.pack(expand=True)

    ttk.Label(frame, text=f"{role} 登录", font=("Helvetica", 20)).pack(pady=10)
    
    ttk.Label(frame, text="ID:").pack()
    entry_id = ttk.Entry(frame, width=30)
    entry_id.pack()

    ttk.Label(frame, text="密码:").pack()
    entry_pw = ttk.Entry(frame, width=30, show="*")
    entry_pw.pack()

    def attempt_login():
        global user_role, user_id
        user_id = entry_id.get().strip()
        password = entry_pw.get().strip()
        
        response = requests.post(f"{API_URL}/login", json={"user_id": user_id, "password": password, "role": role})
        if response.status_code == 200:
            data = response.json()
            messagebox.showinfo("登录成功", f"欢迎 {data['name']}!")
            user_role = role
            show_main_page()
        else:
            messagebox.showerror("登录失败", "ID或密码错误")

    ttk.Button(frame, text="登录", command=attempt_login).pack(pady=20)

    add_nav_buttons(frame, show_identity_page)

# --------------------- 主页面 ---------------------
def show_main_page():
    clear_window()
    
    frame = ttk.Frame(root)
    frame.pack(fill="both", expand=True)

    search_frame = ttk.Frame(frame)
    search_frame.pack(pady=15, padx=20, fill="x")

    ttk.Label(search_frame, text="搜索:").pack(side="left")
    search_var = tk.StringVar()
    search_entry = ttk.Entry(search_frame, textvariable=search_var, width=40)
    search_entry.pack(side="left", padx=5)

    ttk.Button(search_frame, text="搜索", command=lambda: search_books(search_var.get())).pack(side="left", padx=5)

    result_frame = ttk.Frame(frame)
    result_frame.pack(pady=10, padx=20, fill="both", expand=True)

    columns = ('ISBN', 'Title', 'Year', 'Status')
    tree = ttk.Treeview(result_frame, columns=columns, show='headings', height=10)
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=140, anchor="center")
    tree.pack(fill="both", expand=True)

    def search_books(keyword):
        try:
            response = requests.get(f"{API_URL}/books")
            if response.status_code == 200:
                books = response.json()
                tree.delete(*tree.get_children())  
                for book in books:
                    if keyword.lower() in book["title"].lower() or keyword in book["isbn"]:
                        tree.insert("", "end", values=(book["isbn"], book["title"], book["year"], book["status"]))
            else:
                messagebox.showerror("错误", "无法获取书籍数据")
        except Exception as e:
            messagebox.showerror("网络错误", str(e))

    if user_role == "member":
        action_frame = ttk.Frame(frame)
        action_frame.pack(pady=10)
        ttk.Button(action_frame, text="借阅书籍", command=lambda: borrow_book(tree)).pack(side="left", padx=5)
        ttk.Button(action_frame, text="归还书籍", command=lambda: return_book()).pack(side="left", padx=5)

    add_nav_buttons(frame, show_identity_page)

# --------------------- 借阅书籍 ---------------------
def borrow_book(tree):
    selected_item = tree.selection()
    if not selected_item:
        messagebox.showwarning("提示", "请选择一本书")
        return

    book_isbn = tree.item(selected_item, "values")[0]

    response = requests.post(f"{API_URL}/borrow", json={"member_id": user_id, "isbn": book_isbn})
    if response.status_code == 200:
        messagebox.showinfo("成功", "借阅成功！")
        show_main_page()
    else:
        messagebox.showerror("失败", response.json()["message"])

# --------------------- 归还书籍 ---------------------
def return_book():
    borrow_id = tk.simpledialog.askstring("归还书籍", "请输入借阅 ID:")
    if not borrow_id:
        return

    response = requests.post(f"{API_URL}/return", json={"borrow_id": borrow_id})
    if response.status_code == 200:
        messagebox.showinfo("成功", "归还成功！")
        show_main_page()
    else:
        messagebox.showerror("失败", response.json()["message"])

# --------------------- 启动应用 ---------------------
show_welcome_page()
root.mainloop()
