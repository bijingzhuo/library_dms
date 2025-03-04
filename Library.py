import psycopg2
DB_NAME = "Library"
DB_USER = "postgres"
DB_PASSWORD = "admin"
DB_HOST = "localhost"
DB_PORT = "5432"

def get_connection():
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        return conn
    except Exception as e:
        print("Failed to connect to the database:", e)
        exit(1)

def login(conn):
    """
    登录函数：反复提示直到输入正确的账户密码（或用户选择返回登录菜单）
    返回 (role, user_id)
    """
    while True:
        role = input("Select your role (1. Employee, 2. Member): ").strip()
        cur = conn.cursor()
        if role == "1":
            employee_id = input("Enter your Employee ID (or type 'back' to return): ").strip()
            if employee_id.lower() == "back":
                return None, None
            password = input("Enter your password: ").strip()
            query = "SELECT name FROM public.employee WHERE employeeid = %s AND password = %s"
            cur.execute(query, (employee_id, password))
            result = cur.fetchone()
            if result:
                print(f"Welcome, {result[0]} (Employee)!")
                return "employee", employee_id
            else:
                print("Invalid Employee credentials. Please try again.\n")
        elif role == "2":
            member_input = input("Enter your Member ID (or type 'back' to return): ").strip()
            if member_input.lower() == "back":
                return None, None
            try:
                member_id = int(member_input)
            except ValueError:
                print("Member ID should be a number. Please try again.\n")
                continue
            password = input("Enter your password: ").strip()
            query = "SELECT name FROM public.member WHERE memberid = %s AND password = %s"
            cur.execute(query, (member_id, password))
            result = cur.fetchone()
            if result:
                print(f"Welcome, {result[0]} (Member)!")
                return "member", member_id
            else:
                print("Invalid Member credentials. Please try again.\n")
        else:
            print("Invalid role selected. Please try again.\n")


def browse_books(conn):
    cur = conn.cursor()
    query = "SELECT isbn, title, publishyear, status FROM public.book"
    cur.execute(query)
    rows = cur.fetchall()
    print("\n=== Books List ===")
    for row in rows:
        isbn, title, publishyear, status = row
        print(f"ISBN: {isbn}, Title: {title}, Year: {publishyear}, Status: {status}")
    print()

def get_or_create_author(conn, cur, author_name, employee_id):
    """
    检查指定的作者名称是否存在（不区分大小写），
    如果存在则返回其authorid，否则插入新记录并返回新生成的authorid。
    """
    cur.execute("SELECT authorid FROM public.author WHERE lower(name) = lower(%s)", (author_name,))
    result = cur.fetchone()
    if result:
        return result[0]
    else:
        cur.execute(
            "INSERT INTO public.author (name, employeeid) VALUES (%s, %s) RETURNING authorid",
            (author_name, employee_id)
        )
        return cur.fetchone()[0]

def get_or_create_category(conn, cur, category_name, employee_id):
    """
    检查指定的类别名称是否存在（不区分大小写），
    如果存在则返回其categoryid，否则插入新记录并返回新生成的categoryid。
    """
    cur.execute("SELECT categoryid FROM public.category WHERE lower(name) = lower(%s)", (category_name,))
    result = cur.fetchone()
    if result:
        return result[0]
    else:
        cur.execute(
            "INSERT INTO public.category (name, employeeid) VALUES (%s, %s) RETURNING categoryid",
            (category_name, employee_id)
        )
        return cur.fetchone()[0]

def add_book(conn, employee_id):
    cur = conn.cursor()
    print("\n=== Add a New Book or Add Copies ===")
    isbn = input("Enter ISBN: ").strip()
    
    # 检查该书是否已存在
    cur.execute("SELECT isbn FROM public.book WHERE isbn = %s", (isbn,))
    existing_book = cur.fetchone()
    
    if existing_book:
        print("This book already exists.")
        add_choice = input("Do you want to add new copies to the existing book? (y/n): ").strip().lower()
        if add_choice != "y":
            print("Operation cancelled.")
            return
    else:
        # 如果书不存在，则输入书籍信息，并插入新书记录
        title = input("Enter Title: ").strip()
        publishyear = input("Enter Publish Year: ").strip()
        area = input("Enter Area: ").strip()
        status = "Available"  # 新书默认状态为 Available
        try:
            cur.execute("""
                INSERT INTO public.book (isbn, title, publishyear, area, status, employeeid, createdat, updatedat)
                VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (isbn, title, publishyear, area, status, employee_id))
        except Exception as e:
            conn.rollback()
            print("Failed to add new book:", e)
            return
        
        # 要求添加至少一个作者或类别
        print("Please provide at least one author or category for the book.")
        authors = input("Enter author names (comma separated), or leave empty if none: ").strip()
        categories = input("Enter category names (comma separated), or leave empty if none: ").strip()
        if not authors and not categories:
            print("Error: Each book must have at least one author or category!")
            conn.rollback()
            return
        
        if authors:
            for author in authors.split(","):
                author = author.strip()
                try:
                    authorid = get_or_create_author(conn, cur, author, employee_id)
                    cur.execute("INSERT INTO public.book_author (isbn, authorid) VALUES (%s, %s)", (isbn, authorid))
                except Exception as e:
                    conn.rollback()
                    print("Failed to add author association:", e)
                    return
        if categories:
            for category in categories.split(","):
                category = category.strip()
                try:
                    categoryid = get_or_create_category(conn, cur, category, employee_id)
                    cur.execute("INSERT INTO public.book_category (isbn, categoryid) VALUES (%s, %s)", (isbn, categoryid))
                except Exception as e:
                    conn.rollback()
                    print("Failed to add category association:", e)
                    return
    
    # 添加影本记录
    num_copies_str = input("Enter number of copies to add for this book: ").strip()
    try:
        num_copies = int(num_copies_str)
    except ValueError:
        print("Invalid number input. Defaulting to 1 copy.")
        num_copies = 1

    copy_ids = []
    try:
        for _ in range(num_copies):
            cur.execute("""
                INSERT INTO public.bookcopy (isbn, status, createdat, updatedat)
                VALUES (%s, 'Available', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                RETURNING copyid
            """, (isbn,))
            cid = cur.fetchone()[0]
            copy_ids.append(cid)
        conn.commit()
        print("New book (or copies) added successfully.")
        print("Generated copy IDs:", copy_ids)
    except Exception as e:
        conn.rollback()
        print("Failed to add copies:", e)
        return

    # 自动分配新增影本给该 ISBN 下的预约记录（按队列顺序）
    try:
        # 查询所有状态为 Active 的预约记录，按 queuenumber 和 reservationdate 排序
        cur.execute("""
            SELECT reservationid, memberid 
            FROM public.reservation 
            WHERE isbn = %s AND status = 'Active'
            ORDER BY queuenumber ASC, reservationdate ASC
        """, (isbn,))
        reservations = cur.fetchall()
        assignments = []
        # 取新增影本和预约记录中较小的数量进行分配
        count = min(len(copy_ids), len(reservations))
        for i in range(count):
            reservation_id, reserved_member_id = reservations[i]
            copyid = copy_ids[i]
            # 更新预约记录：状态改为 Reserved，设置取书截止时间
            cur.execute("""
                UPDATE public.reservation
                SET status = 'Reserved',
                    pickupdeadline = CURRENT_TIMESTAMP + INTERVAL '3 days',
                    updatedat = CURRENT_TIMESTAMP
                WHERE reservationid = %s
            """, (reservation_id,))
            # 更新 bookcopy：状态改为 Reserved
            cur.execute("""
                UPDATE public.bookcopy
                SET status = 'Reserved', updatedat = CURRENT_TIMESTAMP
                WHERE copyid = %s
            """, (copyid,))
            assignments.append((reservation_id, copyid))
        conn.commit()
        if assignments:
            print("The following assignments have been made to queued reservations:")
            for res_id, cid in assignments:
                print(f"ReservationID: {res_id} is assigned CopyID: {cid}")
        else:
            print("No active reservations to assign new copies.")
    except Exception as e:
        conn.rollback()
        print("Failed to auto-assign reservations:", e)

def employee_menu(conn, employee_id):
    while True:
        print("\nEmployee Menu:")
        print("1. Browse Books")
        print("2. Add New Book")
        print("3. Search Books")
        print("4. Delete a Book Copy")
        print("5. Browse Borrow Records")
        print("6. Browse Reservation Records")
        print("7. Browse Book Copies")
        # 去除了取消预约的功能
        print("8. Logout")
        choice = input("Enter your choice: ").strip()
        if choice == "1":
            browse_books(conn)
        elif choice == "2":
            add_book(conn, employee_id)
        elif choice == "3":
            search_books(conn)
        elif choice == "4":
            delete_book_copy(conn, employee_id)
        elif choice == "5":
            browse_borrow_records(conn)
        elif choice == "6":
            browse_reservation_records(conn)
        elif choice == "7":
            browse_book_copies(conn)
        elif choice == "8":
            print("Logging out...\n")
            break
        else:
            print("Invalid choice. Please try again.")



def reserve_book(conn, member_id):
    cur = conn.cursor()
    print("\n=== Reserve a Book ===")
    isbn = input("Enter ISBN of the book to reserve: ").strip()
    
    # 检查会员当前处于 Active 或 Reserved 状态的预约数量是否达到10本
    cur.execute("""
        SELECT COUNT(*)
        FROM public.reservation
        WHERE memberid = %s AND status IN ('Active', 'Reserved')
    """, (member_id,))
    current_count = cur.fetchone()[0]
    if current_count >= 10:
        print("You have reached the maximum reservation limit of 10 books.")
        return

    # 检查会员是否已预约了该ISBN的书
    cur.execute("""
        SELECT 1
        FROM public.reservation
        WHERE memberid = %s AND isbn = %s AND status IN ('Active', 'Reserved')
    """, (member_id, isbn))
    if cur.fetchone() is not None:
        print(f"You already have a reservation for ISBN {isbn}.")
        return

    # 检查书籍是否存在
    cur.execute("SELECT status FROM public.book WHERE isbn = %s", (isbn,))
    book = cur.fetchone()
    if not book:
        print("Book does not exist.")
        return
    
    # 只有在没有可借副本（即 status = 'Unavailable'）的情况下才允许预约
    if book[0] != "Unavailable":
        print("Reservation is only allowed for books that have no available copies (i.e., 'Unavailable').")
        return
    
    # 查询该书当前所有 'Active' 状态的预约记录，计算下一个队列号
    cur.execute("""
        SELECT COALESCE(MAX(queuenumber), 0)
        FROM public.reservation
        WHERE isbn = %s AND status = 'Active'
    """, (isbn,))
    max_queue = cur.fetchone()[0]
    next_queue = max_queue + 1
    
    # 插入新的预约记录
    try:
        cur.execute("""
            INSERT INTO public.reservation
            (memberid, isbn, reservationdate, status, queuenumber, pickupdeadline, createdat, updatedat)
            VALUES (%s, %s, CURRENT_TIMESTAMP, 'Active', %s, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (member_id, isbn, next_queue))
        conn.commit()
        print(f"Book reserved successfully. Your queue number is: {next_queue}")
    except Exception as e:
        conn.rollback()
        print("Failed to reserve book:", e)

def cancel_reservation(conn, member_id):
    cur = conn.cursor()
    print("\n=== Cancel a Reservation ===")
    # 显示该会员所有状态为 'Active' 的预约记录
    cur.execute("""
        SELECT reservationid, isbn, reservationdate, queuenumber 
        FROM public.reservation 
        WHERE memberid = %s AND status = 'Active'
    """, (member_id,))
    reservations = cur.fetchall()
    if not reservations:
        print("You have no active reservations to cancel.")
        return
    print("Your active reservations:")
    for res in reservations:
        print(f"Reservation ID: {res[0]}, ISBN: {res[1]}, Date: {res[2]}, Queue Number: {res[3]}")
    
    res_id = input("Enter the Reservation ID you want to cancel: ").strip()
    try:
        cur.execute("""
            UPDATE public.reservation
            SET status = 'Canceled', updatedat = CURRENT_TIMESTAMP
            WHERE reservationid = %s AND memberid = %s
        """, (res_id, member_id))
        if cur.rowcount == 0:
            print("Reservation not found or you are not authorized to cancel it.")
        else:
            conn.commit()
            print("Reservation canceled successfully.")
    except Exception as e:
        conn.rollback()
        print("Failed to cancel reservation:", e)

def borrow_book(conn, member_id):
    cur = conn.cursor()
    print("\n=== Borrow a Book ===")
    
    isbn = input("Enter ISBN of the book you want to borrow: ").strip()
    
    # 新增检查：判断该会员是否已经借阅该ISBN且未归还
    cur.execute("""
        SELECT 1
        FROM public.borrow
        WHERE memberid = %s AND isbn = %s AND returndate IS NULL
    """, (member_id, isbn))
    if cur.fetchone() is not None:
        print("You have already borrowed this book and have not returned it yet.")
        return
    
    # 检查会员当前未归还的借阅数量
    cur.execute("""
        SELECT COUNT(borrowid)
        FROM public.borrow 
        WHERE memberid = %s AND returndate IS NULL
    """, (member_id,))
    active_borrow_count = cur.fetchone()[0]
    if active_borrow_count >= 5:
        print("You already have 5 active borrowed books. Please return some books before borrowing more.")
        return

    # 检查书籍是否存在
    cur.execute("SELECT status FROM public.book WHERE isbn = %s", (isbn,))
    book = cur.fetchone()
    if not book:
        print("Book does not exist.")
        return
    
    # 如果书籍处于不可借状态，则检查预约情况
    if book[0] == "Unavailable":
        cur.execute("""
            SELECT memberid
            FROM public.reservation
            WHERE isbn = %s AND status = 'Reserved' 
              AND pickupdeadline IS NOT NULL AND pickupdeadline > CURRENT_TIMESTAMP
            ORDER BY queuenumber ASC
            LIMIT 1
        """, (isbn,))
        res = cur.fetchone()
        if res is None or res[0] != member_id:
            print("Book is reserved for another member.")
            return
    
    try:
        # 插入借阅记录，并利用触发器自动分配一个可用影本
        cur.execute("""
            INSERT INTO public.borrow 
            (memberid, isbn, borrowdate, duedate, returndate, createdat, updatedat)
            VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_DATE + 30, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING borrowid, copyid
        """, (member_id, isbn))
        result = cur.fetchone()
        conn.commit()
        print(f"Book borrowed successfully. Borrow ID: {result[0]}, Assigned Copy ID: {result[1]}")
    except Exception as e:
        conn.rollback()
        print("Failed to borrow book:", e)

def return_book(conn, member_id):
    cur = conn.cursor()
    print("\n=== Return a Book ===")
    try:
        # 获取该会员所有未归还的借阅记录
        cur.execute("""
            SELECT borrowid, isbn, copyid 
            FROM public.borrow
            WHERE memberid = %s AND returndate IS NULL
        """, (member_id,))
        borrow_records = cur.fetchall()
        
        if not borrow_records:
            print("You don't have any books to return.")
            return
        
        print("Your active borrowed books:")
        for i, record in enumerate(borrow_records, 1):
            borrowid, isbn, copyid = record
            print(f"{i}. BorrowID: {borrowid}, ISBN: {isbn}, CopyID: {copyid}")
        
        choice = input("Enter the number of the book you want to return: ").strip()
        try:
            choice_index = int(choice) - 1
            if choice_index < 0 or choice_index >= len(borrow_records):
                print("Invalid selection.")
                return
        except ValueError:
            print("Invalid input.")
            return
        
        selected_record = borrow_records[choice_index]
        borrowid, isbn, copyid = selected_record
        
        # 更新借阅记录的归还时间
        cur.execute("""
            UPDATE public.borrow
            SET returndate = CURRENT_TIMESTAMP
            WHERE borrowid = %s
        """, (borrowid,))
        
        # 检查是否有该书的Active预约
        cur.execute("""
            SELECT reservationid, memberid
            FROM public.reservation
            WHERE isbn = %s 
              AND status = 'Active'
            ORDER BY queuenumber ASC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        """, (isbn,))
        first_reservation = cur.fetchone()

        if first_reservation:
            reservation_id, reserved_member_id = first_reservation
            # 将这本影本标记为Reserved，并更新预约记录
            cur.execute("""
                UPDATE public.bookcopy
                SET status = 'Reserved'
                WHERE copyid = %s
            """, (copyid,))
            cur.execute("""
                UPDATE public.reservation
                SET status = 'Reserved',
                    pickupdeadline = CURRENT_TIMESTAMP + INTERVAL '3 days',
                    updatedat = CURRENT_TIMESTAMP
                WHERE reservationid = %s
            """, (reservation_id,))
            print(f"Book reserved for member {reserved_member_id}. Must borrow within 3 days.")
        else:
            # 没有Active预约则将该影本标记为Available
            cur.execute("""
                UPDATE public.bookcopy
                SET status = 'Available'
                WHERE copyid = %s
            """, (copyid,))
            print("Book marked as available")
        
        # 根据可用副本数量更新book表状态
        cur.execute("""
            WITH status_summary AS (
                SELECT 
                    COUNT(*) FILTER (WHERE status = 'Available') AS available
                FROM public.bookcopy
                WHERE isbn = %s
            )
            UPDATE public.book
            SET status = CASE
                WHEN (SELECT available FROM status_summary) > 0 THEN 'Available'
                ELSE 'Unavailable'
            END,
            updatedat = CURRENT_TIMESTAMP
            WHERE isbn = %s
        """, (isbn, isbn))
        
        conn.commit()
        print(f"Return successful! Copy ID: {copyid}")
    
    except Exception as e:
        conn.rollback()
        print("Failed to return book:", e)

        
def member_menu(conn, member_id):
    # 登录后先显示会员的借阅和预约信息
    show_member_borrowed_books(conn, member_id)
    show_member_reservations(conn, member_id)
    
    while True:
        print("\nMember Menu:")
        print("1. Browse Books")
        print("2. Reserve a Book")
        print("3. Cancel a Reservation")
        print("4. Borrow a Book")
        print("5. Return a Book")
        print("6. Search Books")
        print("7. Logout")
        choice = input("Enter your choice: ").strip()
        if choice == "1":
            browse_books(conn)
        elif choice == "2":
            reserve_book(conn, member_id)
        elif choice == "3":
            cancel_reservation(conn, member_id)
        elif choice == "4":
            borrow_book(conn, member_id)
        elif choice == "5":
            return_book(conn, member_id)
        elif choice == "6":
            search_books(conn)
        elif choice == "7":
            print("Logging out...\n")
            break
        else:
            print("Invalid choice. Please try again.")

def search_books(conn):
    cur = conn.cursor()
    print("\n=== Search Books ===")
    keyword = input("Enter search keyword: ").strip()
    print("Select search type:")
    print("1. Title")
    print("2. Category")
    print("3. Year")
    print("4. Author")
    print("5. All (search in title, year, author and category)")
    search_type = input("Enter your choice: ").strip()

    if search_type == "1":
        query = "SELECT isbn, title, publishyear, status FROM public.book WHERE title ILIKE %s"
        params = (f"%{keyword}%",)
    elif search_type == "2":
        query = """
            SELECT DISTINCT b.isbn, b.title, b.publishyear, b.status 
            FROM public.book b 
            JOIN public.book_category bc ON b.isbn = bc.isbn 
            JOIN public.category c ON bc.categoryid = c.categoryid 
            WHERE c.name ILIKE %s
        """
        params = (f"%{keyword}%",)
    elif search_type == "3":
        query = "SELECT isbn, title, publishyear, status FROM public.book WHERE CAST(publishyear AS TEXT) ILIKE %s"
        params = (f"%{keyword}%",)
    elif search_type == "4":
        query = """
            SELECT DISTINCT b.isbn, b.title, b.publishyear, b.status 
            FROM public.book b 
            JOIN public.book_author ba ON b.isbn = ba.isbn 
            JOIN public.author a ON ba.authorid = a.authorid 
            WHERE a.name ILIKE %s
        """
        params = (f"%{keyword}%",)
    elif search_type == "5":
        query = """
            SELECT DISTINCT b.isbn, b.title, b.publishyear, b.status 
            FROM public.book b
            LEFT JOIN public.book_author ba ON b.isbn = ba.isbn
            LEFT JOIN public.author a ON ba.authorid = a.authorid
            LEFT JOIN public.book_category bc ON b.isbn = bc.isbn
            LEFT JOIN public.category c ON bc.categoryid = c.categoryid
            WHERE b.title ILIKE %s 
               OR CAST(b.publishyear AS TEXT) ILIKE %s 
               OR a.name ILIKE %s 
               OR c.name ILIKE %s
        """
        params = (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", f"%{keyword}%")
    else:
        print("Invalid search type.")
        return

    try:
        cur.execute(query, params)
        rows = cur.fetchall()
        if rows:
            print("\n=== Search Results ===")
            for row in rows:
                isbn, title, publishyear, status = row
                print(f"ISBN: {isbn}, Title: {title}, Year: {publishyear}, Status: {status}")
        else:
            print("No books found matching the search criteria.")
    except Exception as e:
        print("Search failed:", e)
    print()
def delete_book_copy(conn, employee_id):
    cur = conn.cursor()
    print("\n=== Delete a Book Copy ===")
    isbn = input("Enter ISBN for which you want to delete a copy: ").strip()
    
    # 查询该 ISBN 的所有影本及其状态
    cur.execute("SELECT copyid, status FROM public.bookcopy WHERE isbn = %s", (isbn,))
    copies = cur.fetchall()
    
    if not copies:
        print("No copies found for this ISBN.")
        return
    
    print("Copies for the book:")
    for i, (copyid, status) in enumerate(copies, 1):
        print(f"{i}. CopyID: {copyid}, Status: {status}")
    
    choice = input("Enter the number of the copy to mark as Unavailable: ").strip()
    try:
        choice_index = int(choice) - 1
        if choice_index < 0 or choice_index >= len(copies):
            print("Invalid selection.")
            return
    except ValueError:
        print("Invalid input.")
        return
    
    selected_copyid = copies[choice_index][0]
    
    try:
        # 将选中的影本状态更新为 Unavailable
        cur.execute("""
            UPDATE public.bookcopy
            SET status = 'Unavailable', updatedat = CURRENT_TIMESTAMP
            WHERE copyid = %s
        """, (selected_copyid,))
        
        # 更新 book 表状态：如果没有 Available 的影本，则更新为 Unavailable
        cur.execute("""
            WITH status_summary AS (
                SELECT COUNT(*) AS available_count
                FROM public.bookcopy
                WHERE isbn = %s AND status = 'Available'
            )
            UPDATE public.book
            SET status = CASE
                WHEN (SELECT available_count FROM status_summary) > 0 THEN 'Available'
                ELSE 'Unavailable'
            END,
            updatedat = CURRENT_TIMESTAMP
            WHERE isbn = %s
        """, (isbn, isbn))
        
        conn.commit()
        print(f"Book copy with ID {selected_copyid} marked as Unavailable.")
    except Exception as e:
        conn.rollback()
        print("Failed to update book copy:", e)


def browse_borrow_records(conn):
    cur = conn.cursor()
    print("\n=== Borrow Records ===")
    try:
        cur.execute("""
            SELECT borrowid, memberid, isbn, borrowdate, duedate, returndate, copyid
            FROM public.borrow
            ORDER BY borrowdate DESC
        """)
        records = cur.fetchall()
        if records:
            for record in records:
                borrowid, memberid, isbn, borrowdate, duedate, returndate, copyid = record
                print(f"BorrowID: {borrowid}, MemberID: {memberid}, ISBN: {isbn}, "
                      f"BorrowDate: {borrowdate}, DueDate: {duedate}, ReturnDate: {returndate}, CopyID: {copyid}")
        else:
            print("No borrow records found.")
    except Exception as e:
        print("Failed to retrieve borrow records:", e)
    print()


def browse_reservation_records(conn):
    cur = conn.cursor()
    print("\n=== Reservation Records ===")
    try:
        cur.execute("""
            SELECT reservationid, memberid, isbn, reservationdate, status, queuenumber, pickupdeadline
            FROM public.reservation
            ORDER BY reservationdate DESC
        """)
        records = cur.fetchall()
        if records:
            for record in records:
                reservationid, memberid, isbn, reservationdate, status, queuenumber, pickupdeadline = record
                print(f"ReservationID: {reservationid}, MemberID: {memberid}, ISBN: {isbn}, "
                      f"ReservationDate: {reservationdate}, Status: {status}, QueueNumber: {queuenumber}, "
                      f"PickupDeadline: {pickupdeadline}")
        else:
            print("No reservation records found.")
    except Exception as e:
        print("Failed to retrieve reservation records:", e)
    print()
def browse_book_copies(conn):
    cur = conn.cursor()
    print("\n=== Browse Book Copies ===")
    isbn_filter = input("Enter ISBN to filter copies (leave empty to show all): ").strip()
    try:
        if isbn_filter:
            cur.execute("""
                SELECT copyid, isbn, status, createdat, updatedat
                FROM public.bookcopy
                WHERE isbn = %s
                ORDER BY copyid
            """, (isbn_filter,))
        else:
            cur.execute("""
                SELECT copyid, isbn, status, createdat, updatedat
                FROM public.bookcopy
                ORDER BY isbn, copyid
            """)
        records = cur.fetchall()
        if records:
            for record in records:
                copyid, isbn, status, createdat, updatedat = record
                print(f"CopyID: {copyid}, ISBN: {isbn}, Status: {status}, CreatedAt: {createdat}, UpdatedAt: {updatedat}")
        else:
            print("No book copies found for the given ISBN.")
    except Exception as e:
        print("Failed to retrieve book copies:", e)
    print()

def browse_borrow_records(conn):
    cur = conn.cursor()
    print("\n=== Borrow Records ===")
    print("Filter options:")
    print("1. Borrow ID")
    print("2. ISBN")
    print("3. Member ID")
    print("4. No filter (show all)")
    filter_choice = input("Select filter option (1-4): ").strip()
    
    if filter_choice == "1":
        filter_value = input("Enter Borrow ID: ").strip()
        query = """
            SELECT borrowid, memberid, isbn, borrowdate, duedate, returndate, copyid
            FROM public.borrow
            WHERE CAST(borrowid AS TEXT) ILIKE %s
            ORDER BY borrowdate DESC
        """
        params = (f"%{filter_value}%",)
    elif filter_choice == "2":
        filter_value = input("Enter ISBN: ").strip()
        query = """
            SELECT borrowid, memberid, isbn, borrowdate, duedate, returndate, copyid
            FROM public.borrow
            WHERE isbn ILIKE %s
            ORDER BY borrowdate DESC
        """
        params = (f"%{filter_value}%",)
    elif filter_choice == "3":
        filter_value = input("Enter Member ID: ").strip()
        query = """
            SELECT borrowid, memberid, isbn, borrowdate, duedate, returndate, copyid
            FROM public.borrow
            WHERE CAST(memberid AS TEXT) ILIKE %s
            ORDER BY borrowdate DESC
        """
        params = (f"%{filter_value}%",)
    else:
        query = """
            SELECT borrowid, memberid, isbn, borrowdate, duedate, returndate, copyid
            FROM public.borrow
            ORDER BY borrowdate DESC
        """
        params = ()

    try:
        cur.execute(query, params)
        records = cur.fetchall()
        if records:
            for record in records:
                borrowid, memberid, isbn, borrowdate, duedate, returndate, copyid = record
                print(f"BorrowID: {borrowid}, MemberID: {memberid}, ISBN: {isbn}, "
                      f"BorrowDate: {borrowdate}, DueDate: {duedate}, ReturnDate: {returndate}, CopyID: {copyid}")
        else:
            print("No borrow records found with the given filter.")
    except Exception as e:
        print("Failed to retrieve borrow records:", e)
    print()


def browse_reservation_records(conn):
    cur = conn.cursor()
    print("\n=== Reservation Records ===")
    print("Filter options:")
    print("1. Reservation ID")
    print("2. ISBN")
    print("3. Member ID")
    print("4. No filter (show all)")
    filter_choice = input("Select filter option (1-4): ").strip()
    
    if filter_choice == "1":
        filter_value = input("Enter Reservation ID: ").strip()
        query = """
            SELECT reservationid, memberid, isbn, reservationdate, status, queuenumber, pickupdeadline
            FROM public.reservation
            WHERE CAST(reservationid AS TEXT) ILIKE %s
            ORDER BY reservationdate DESC
        """
        params = (f"%{filter_value}%",)
    elif filter_choice == "2":
        filter_value = input("Enter ISBN: ").strip()
        query = """
            SELECT reservationid, memberid, isbn, reservationdate, status, queuenumber, pickupdeadline
            FROM public.reservation
            WHERE isbn ILIKE %s
            ORDER BY reservationdate DESC
        """
        params = (f"%{filter_value}%",)
    elif filter_choice == "3":
        filter_value = input("Enter Member ID: ").strip()
        query = """
            SELECT reservationid, memberid, isbn, reservationdate, status, queuenumber, pickupdeadline
            FROM public.reservation
            WHERE CAST(memberid AS TEXT) ILIKE %s
            ORDER BY reservationdate DESC
        """
        params = (f"%{filter_value}%",)
    else:
        query = """
            SELECT reservationid, memberid, isbn, reservationdate, status, queuenumber, pickupdeadline
            FROM public.reservation
            ORDER BY reservationdate DESC
        """
        params = ()

    try:
        cur.execute(query, params)
        records = cur.fetchall()
        if records:
            for record in records:
                reservationid, memberid, isbn, reservationdate, status, queuenumber, pickupdeadline = record
                print(f"ReservationID: {reservationid}, MemberID: {memberid}, ISBN: {isbn}, "
                      f"ReservationDate: {reservationdate}, Status: {status}, QueueNumber: {queuenumber}, "
                      f"PickupDeadline: {pickupdeadline}")
        else:
            print("No reservation records found with the given filter.")
    except Exception as e:
        print("Failed to retrieve reservation records:", e)
    print()

def show_member_borrowed_books(conn, member_id):
    cur = conn.cursor()
    cur.execute("""
        SELECT borrowid, isbn, copyid, borrowdate, duedate
        FROM public.borrow 
        WHERE memberid = %s AND returndate IS NULL
        ORDER BY borrowdate DESC
    """, (member_id,))
    borrowed = cur.fetchall()
    if borrowed:
        print("\nYour currently borrowed books:")
        for row in borrowed:
            borrowid, isbn, copyid, borrowdate, duedate = row
            print(f"BorrowID: {borrowid}, ISBN: {isbn}, CopyID: {copyid}, "
                  f"Borrow Date: {borrowdate}, Due Date: {duedate}")
    else:
        print("\nYou have not borrowed any books.")


def show_member_reservations(conn, member_id):
    cur = conn.cursor()
    cur.execute("""
        SELECT reservationid, isbn, status, reservationdate, queuenumber, pickupdeadline 
        FROM public.reservation 
        WHERE memberid = %s 
          AND status IN ('Active', 'Reserved')
        ORDER BY reservationdate DESC
    """, (member_id,))
    reservations = cur.fetchall()
    if reservations:
        print("\nYour reservations:")
        for row in reservations:
            reservationid, isbn, status, reservationdate, queuenumber, pickupdeadline = row
            print(f"ReservationID: {reservationid}, ISBN: {isbn}, Status: {status}, Reservation Date: {reservationdate}, Queue Number: {queuenumber}, Pickup Deadline: {pickupdeadline}")
    else:
        print("\nYou have not reserved any books.")
def main():
    conn = get_connection()
    while True:
        print("\n=== Welcome to the Library System ===")
        print("1. Login")
        print("2. Exit")
        choice = input("Enter your choice: ").strip()
        if choice == "2":
            print("Exiting program.")
            break
        elif choice == "1":
            role, user_id = login(conn)
            # 如果登录函数返回 None，则回到登录菜单
            if role is None:
                continue
            if role == "employee":
                employee_menu(conn, user_id)
            elif role == "member":
                member_menu(conn, user_id)
        else:
            print("Invalid choice. Please try again.")
    conn.close()


if __name__ == "__main__":
    main()
