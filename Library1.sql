PGDMP      "                }            Library    17.2    17.2 _    u           0    0    ENCODING    ENCODING        SET client_encoding = 'UTF8';
                           false            v           0    0 
   STDSTRINGS 
   STDSTRINGS     (   SET standard_conforming_strings = 'on';
                           false            w           0    0 
   SEARCHPATH 
   SEARCHPATH     8   SELECT pg_catalog.set_config('search_path', '', false);
                           false            x           1262    33314    Library    DATABASE     �   CREATE DATABASE "Library" WITH TEMPLATE = template0 ENCODING = 'UTF8' LOCALE_PROVIDER = libc LOCALE = 'Chinese (Simplified)_China.utf8';
    DROP DATABASE "Library";
                     postgres    false            �            1255    33542    adjust_reservation_queue()    FUNCTION     ,  CREATE FUNCTION public.adjust_reservation_queue() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    available_count INTEGER;
BEGIN
    IF (OLD.status IN ('Active','Reserved'))
       AND (NEW.status IN ('Canceled', 'PickedUp'))
    THEN
        UPDATE public.reservation
        SET queuenumber = queuenumber - 1
        WHERE isbn = OLD.isbn
          AND status = 'Active'
          AND queuenumber > OLD.queuenumber;

    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM public.reservation
        WHERE isbn = OLD.isbn AND status = 'Active'
    ) THEN
        SELECT COUNT(*) INTO available_count
        FROM public.bookcopy
        WHERE isbn = OLD.isbn AND status = 'Available';

        IF available_count > 0 THEN
            UPDATE public.book
            SET status = 'Available', updatedat = CURRENT_TIMESTAMP
            WHERE isbn = OLD.isbn;
        ELSE
            UPDATE public.book
            SET status = 'Borrowed', updatedat = CURRENT_TIMESTAMP
            WHERE isbn = OLD.isbn;
        END IF;
    END IF;

    RETURN NEW;
END;
$$;
 1   DROP FUNCTION public.adjust_reservation_queue();
       public               postgres    false            �            1255    33544    assign_book_copy()    FUNCTION     �  CREATE FUNCTION public.assign_book_copy() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    available_copy INTEGER;
    available_count INTEGER;
BEGIN
    IF NEW.copyid IS NULL THEN
        SELECT copyid INTO available_copy
        FROM public.bookcopy
        WHERE isbn = NEW.isbn AND status = 'Available'
        LIMIT 1;

        IF available_copy IS NULL THEN
            RAISE EXCEPTION 'No available copy for ISBN %', NEW.isbn;
        END IF;

        NEW.copyid = available_copy;

        UPDATE public.bookcopy
        SET status = 'Borrowed', updatedat = CURRENT_TIMESTAMP
        WHERE copyid = available_copy;

        SELECT COUNT(*) INTO available_count
        FROM public.bookcopy
        WHERE isbn = NEW.isbn AND status = 'Available';

        UPDATE public.book
        SET status = CASE WHEN available_count = 0 THEN 'Borrowed' ELSE 'Available' END,
            updatedat = CURRENT_TIMESTAMP
        WHERE isbn = NEW.isbn;
    END IF;

    RETURN NEW;
END;
$$;
 )   DROP FUNCTION public.assign_book_copy();
       public               postgres    false            �            1255    33455    check_book_associations()    FUNCTION     �  CREATE FUNCTION public.check_book_associations() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM Book b
        WHERE NOT EXISTS (SELECT 1 FROM Book_Author WHERE ISBN = b.ISBN)
          AND NOT EXISTS (SELECT 1 FROM Book_Category WHERE ISBN = b.ISBN)
    ) THEN
        RAISE EXCEPTION 'Each book must have at least one author or category!';
    END IF;
    RETURN NULL;
END;
$$;
 0   DROP FUNCTION public.check_book_associations();
       public               postgres    false            �            1255    33545    check_borrow_permission()    FUNCTION     "  CREATE FUNCTION public.check_borrow_permission() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    available_count INTEGER;
    reserved_reservation RECORD;
BEGIN
    IF NEW.copyid IS NOT NULL THEN
        RETURN NEW;
    END IF;

    SELECT COUNT(*) INTO available_count
    FROM public.bookcopy
    WHERE isbn = NEW.isbn AND status = 'Available';

    SELECT *
    INTO reserved_reservation
    FROM public.reservation
    WHERE isbn = NEW.isbn
      AND status = 'Reserved'
      AND pickupdeadline >= CURRENT_TIMESTAMP
    ORDER BY queuenumber ASC, reservationdate ASC
    LIMIT 1;

    IF reserved_reservation IS NOT NULL THEN
        IF reserved_reservation.memberid = NEW.memberid THEN
            RETURN NEW;
        ELSE
            RAISE EXCEPTION 'Only the member at the front of the reservation queue can borrow this book!';
        END IF;
    ELSE
        IF available_count > 0 THEN
            RETURN NEW;
        ELSE
            RAISE EXCEPTION 'No available copy exists for ISBN %', NEW.isbn;
        END IF;
    END IF;
END;
$$;
 0   DROP FUNCTION public.check_borrow_permission();
       public               postgres    false            �            1255    33501 &   check_late_returns_and_freeze_member()    FUNCTION     �  CREATE FUNCTION public.check_late_returns_and_freeze_member() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    late_count INTEGER;
BEGIN
    IF OLD.returndate IS NULL AND NEW.returndate IS NOT NULL THEN

        IF NEW.returndate > NEW.duedate THEN

            SELECT COUNT(*) INTO late_count
            FROM public.borrow
            WHERE memberid = NEW.memberid
              AND returndate IS NOT NULL
              AND returndate > duedate;

            IF late_count >= 3 THEN
                UPDATE public.member
                SET membershipstatus = 'Frozen'
                WHERE memberid = NEW.memberid;
            END IF;
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
 =   DROP FUNCTION public.check_late_returns_and_freeze_member();
       public               postgres    false            �            1255    33500    process_expired_reservations()    FUNCTION     4  CREATE FUNCTION public.process_expired_reservations() RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE
    expired_rec RECORD;
BEGIN
    FOR expired_rec IN
      SELECT *
      FROM reservation
      WHERE queuenumber = 1
        AND status = 'Active'
        AND pickupdeadline < CURRENT_TIMESTAMP 
    LOOP

      DELETE FROM reservation
      WHERE reservationid = expired_rec.reservationid;
      

      UPDATE reservation
      SET queuenumber = queuenumber - 1
      WHERE isbn = expired_rec.isbn AND queuenumber > 1;
      

      IF NOT EXISTS (
            SELECT 1 FROM reservation 
            WHERE isbn = expired_rec.isbn 
              AND status = 'Active'
         )
      THEN

         UPDATE book SET status = 'Available' WHERE isbn = expired_rec.isbn;
      END IF;
      
    END LOOP;
END;
$$;
 5   DROP FUNCTION public.process_expired_reservations();
       public               postgres    false            �            1255    33553 !   sync_bookcopy_and_update_status()    FUNCTION     �  CREATE FUNCTION public.sync_bookcopy_and_update_status() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    waiting_reservation RECORD;
BEGIN
    SELECT *
    INTO waiting_reservation
    FROM public.reservation
    WHERE isbn = NEW.isbn
      AND status = 'Active'
    ORDER BY queuenumber ASC, reservationdate ASC
    LIMIT 1;

    IF waiting_reservation IS NOT NULL THEN
        UPDATE public.reservation
        SET status = 'Reserved',
            pickupdeadline = CURRENT_TIMESTAMP + INTERVAL '3 days',
            updatedat = CURRENT_TIMESTAMP
        WHERE reservationid = waiting_reservation.reservationid;

        UPDATE public.bookcopy
        SET status = 'Reserved',
            updatedat = CURRENT_TIMESTAMP
        WHERE copyid = NEW.copyid;

        UPDATE public.book
        SET status = 'Reserved',
            updatedat = CURRENT_TIMESTAMP
        WHERE isbn = NEW.isbn;

    ELSE
        UPDATE public.bookcopy
        SET status = 'Available', updatedat = CURRENT_TIMESTAMP
        WHERE copyid = NEW.copyid;

        UPDATE public.book
        SET status = 'Available', updatedat = CURRENT_TIMESTAMP
        WHERE isbn = NEW.isbn;
    END IF;

    RETURN NEW;
END;
$$;
 8   DROP FUNCTION public.sync_bookcopy_and_update_status();
       public               postgres    false            �            1255    33546    update_updatedat_column()    FUNCTION     �   CREATE FUNCTION public.update_updatedat_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updatedat := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;
 0   DROP FUNCTION public.update_updatedat_column();
       public               postgres    false            �            1259    33337    author    TABLE     %  CREATE TABLE public.author (
    authorid integer NOT NULL,
    name character varying(100) NOT NULL,
    employeeid integer NOT NULL,
    createdat timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updatedat timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);
    DROP TABLE public.author;
       public         heap r       postgres    false            �            1259    33336    author_authorid_seq    SEQUENCE     �   CREATE SEQUENCE public.author_authorid_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
 *   DROP SEQUENCE public.author_authorid_seq;
       public               postgres    false    221            y           0    0    author_authorid_seq    SEQUENCE OWNED BY     K   ALTER SEQUENCE public.author_authorid_seq OWNED BY public.author.authorid;
          public               postgres    false    220            �            1259    33324    book    TABLE     i  CREATE TABLE public.book (
    isbn character varying(20) NOT NULL,
    title character varying(255) NOT NULL,
    publishyear integer,
    status character varying(50),
    employeeid integer NOT NULL,
    createdat timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updatedat timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);
    DROP TABLE public.book;
       public         heap r       postgres    false            �            1259    33413    book_author    TABLE     l   CREATE TABLE public.book_author (
    isbn character varying(20) NOT NULL,
    authorid integer NOT NULL
);
    DROP TABLE public.book_author;
       public         heap r       postgres    false            �            1259    33428    book_category    TABLE     p   CREATE TABLE public.book_category (
    isbn character varying(20) NOT NULL,
    categoryid integer NOT NULL
);
 !   DROP TABLE public.book_category;
       public         heap r       postgres    false            �            1259    33511    bookcopy    TABLE     U  CREATE TABLE public.bookcopy (
    copyid integer NOT NULL,
    isbn character varying(20) NOT NULL,
    status character varying(50) DEFAULT 'Available'::character varying NOT NULL,
    createdat timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updatedat timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);
    DROP TABLE public.bookcopy;
       public         heap r       postgres    false            �            1259    33510    bookcopy_copyid_seq    SEQUENCE     �   CREATE SEQUENCE public.bookcopy_copyid_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
 *   DROP SEQUENCE public.bookcopy_copyid_seq;
       public               postgres    false    233            z           0    0    bookcopy_copyid_seq    SEQUENCE OWNED BY     K   ALTER SEQUENCE public.bookcopy_copyid_seq OWNED BY public.bookcopy.copyid;
          public               postgres    false    232            �            1259    33374    borrow    TABLE     �  CREATE TABLE public.borrow (
    borrowid integer NOT NULL,
    memberid integer NOT NULL,
    isbn character varying(20) NOT NULL,
    borrowdate timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    duedate date DEFAULT (CURRENT_DATE + 30) NOT NULL,
    returndate date,
    createdat timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updatedat timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    copyid integer
);
    DROP TABLE public.borrow;
       public         heap r       postgres    false            �            1259    33373    borrow_borrowid_seq    SEQUENCE     �   CREATE SEQUENCE public.borrow_borrowid_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
 *   DROP SEQUENCE public.borrow_borrowid_seq;
       public               postgres    false    227            {           0    0    borrow_borrowid_seq    SEQUENCE OWNED BY     K   ALTER SEQUENCE public.borrow_borrowid_seq OWNED BY public.borrow.borrowid;
          public               postgres    false    226            �            1259    33351    category    TABLE     )  CREATE TABLE public.category (
    categoryid integer NOT NULL,
    name character varying(100) NOT NULL,
    employeeid integer NOT NULL,
    createdat timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updatedat timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);
    DROP TABLE public.category;
       public         heap r       postgres    false            �            1259    33350    category_categoryid_seq    SEQUENCE     �   CREATE SEQUENCE public.category_categoryid_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
 .   DROP SEQUENCE public.category_categoryid_seq;
       public               postgres    false    223            |           0    0    category_categoryid_seq    SEQUENCE OWNED BY     S   ALTER SEQUENCE public.category_categoryid_seq OWNED BY public.category.categoryid;
          public               postgres    false    222            �            1259    33316    employee    TABLE     6  CREATE TABLE public.employee (
    employeeid integer NOT NULL,
    name character varying(100) NOT NULL,
    password character varying(255) NOT NULL,
    createdat timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updatedat timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);
    DROP TABLE public.employee;
       public         heap r       postgres    false            �            1259    33315    employee_employeeid_seq    SEQUENCE     �   CREATE SEQUENCE public.employee_employeeid_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
 .   DROP SEQUENCE public.employee_employeeid_seq;
       public               postgres    false    218            }           0    0    employee_employeeid_seq    SEQUENCE OWNED BY     S   ALTER SEQUENCE public.employee_employeeid_seq OWNED BY public.employee.employeeid;
          public               postgres    false    217            �            1259    33365    member    TABLE     ^  CREATE TABLE public.member (
    memberid integer NOT NULL,
    name character varying(100) NOT NULL,
    membershipstatus character varying(50),
    password character varying(255) NOT NULL,
    createdat timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updatedat timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);
    DROP TABLE public.member;
       public         heap r       postgres    false            �            1259    33364    member_memberid_seq    SEQUENCE     �   CREATE SEQUENCE public.member_memberid_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
 *   DROP SEQUENCE public.member_memberid_seq;
       public               postgres    false    225            ~           0    0    member_memberid_seq    SEQUENCE OWNED BY     K   ALTER SEQUENCE public.member_memberid_seq OWNED BY public.member.memberid;
          public               postgres    false    224            �            1259    33395    reservation    TABLE     �  CREATE TABLE public.reservation (
    reservationid integer NOT NULL,
    memberid integer NOT NULL,
    isbn character varying(20) NOT NULL,
    reservationdate timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    status character varying(50),
    queuenumber integer,
    pickupdeadline timestamp without time zone,
    createdat timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updatedat timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);
    DROP TABLE public.reservation;
       public         heap r       postgres    false            �            1259    33394    reservation_reservationid_seq    SEQUENCE     �   CREATE SEQUENCE public.reservation_reservationid_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
 4   DROP SEQUENCE public.reservation_reservationid_seq;
       public               postgres    false    229                       0    0    reservation_reservationid_seq    SEQUENCE OWNED BY     _   ALTER SEQUENCE public.reservation_reservationid_seq OWNED BY public.reservation.reservationid;
          public               postgres    false    228            �           2604    33340    author authorid    DEFAULT     r   ALTER TABLE ONLY public.author ALTER COLUMN authorid SET DEFAULT nextval('public.author_authorid_seq'::regclass);
 >   ALTER TABLE public.author ALTER COLUMN authorid DROP DEFAULT;
       public               postgres    false    220    221    221            �           2604    33514    bookcopy copyid    DEFAULT     r   ALTER TABLE ONLY public.bookcopy ALTER COLUMN copyid SET DEFAULT nextval('public.bookcopy_copyid_seq'::regclass);
 >   ALTER TABLE public.bookcopy ALTER COLUMN copyid DROP DEFAULT;
       public               postgres    false    233    232    233            �           2604    33377    borrow borrowid    DEFAULT     r   ALTER TABLE ONLY public.borrow ALTER COLUMN borrowid SET DEFAULT nextval('public.borrow_borrowid_seq'::regclass);
 >   ALTER TABLE public.borrow ALTER COLUMN borrowid DROP DEFAULT;
       public               postgres    false    227    226    227            �           2604    33354    category categoryid    DEFAULT     z   ALTER TABLE ONLY public.category ALTER COLUMN categoryid SET DEFAULT nextval('public.category_categoryid_seq'::regclass);
 B   ALTER TABLE public.category ALTER COLUMN categoryid DROP DEFAULT;
       public               postgres    false    222    223    223            �           2604    33319    employee employeeid    DEFAULT     z   ALTER TABLE ONLY public.employee ALTER COLUMN employeeid SET DEFAULT nextval('public.employee_employeeid_seq'::regclass);
 B   ALTER TABLE public.employee ALTER COLUMN employeeid DROP DEFAULT;
       public               postgres    false    218    217    218            �           2604    33368    member memberid    DEFAULT     r   ALTER TABLE ONLY public.member ALTER COLUMN memberid SET DEFAULT nextval('public.member_memberid_seq'::regclass);
 >   ALTER TABLE public.member ALTER COLUMN memberid DROP DEFAULT;
       public               postgres    false    225    224    225            �           2604    33398    reservation reservationid    DEFAULT     �   ALTER TABLE ONLY public.reservation ALTER COLUMN reservationid SET DEFAULT nextval('public.reservation_reservationid_seq'::regclass);
 H   ALTER TABLE public.reservation ALTER COLUMN reservationid DROP DEFAULT;
       public               postgres    false    228    229    229            f          0    33337    author 
   TABLE DATA           R   COPY public.author (authorid, name, employeeid, createdat, updatedat) FROM stdin;
    public               postgres    false    221   a�       d          0    33324    book 
   TABLE DATA           b   COPY public.book (isbn, title, publishyear, status, employeeid, createdat, updatedat) FROM stdin;
    public               postgres    false    219   %�       o          0    33413    book_author 
   TABLE DATA           5   COPY public.book_author (isbn, authorid) FROM stdin;
    public               postgres    false    230   G�       p          0    33428    book_category 
   TABLE DATA           9   COPY public.book_category (isbn, categoryid) FROM stdin;
    public               postgres    false    231   ��       r          0    33511    bookcopy 
   TABLE DATA           N   COPY public.bookcopy (copyid, isbn, status, createdat, updatedat) FROM stdin;
    public               postgres    false    233   ە       l          0    33374    borrow 
   TABLE DATA           y   COPY public.borrow (borrowid, memberid, isbn, borrowdate, duedate, returndate, createdat, updatedat, copyid) FROM stdin;
    public               postgres    false    227   ��       h          0    33351    category 
   TABLE DATA           V   COPY public.category (categoryid, name, employeeid, createdat, updatedat) FROM stdin;
    public               postgres    false    223   '�       c          0    33316    employee 
   TABLE DATA           T   COPY public.employee (employeeid, name, password, createdat, updatedat) FROM stdin;
    public               postgres    false    218   ×       j          0    33365    member 
   TABLE DATA           b   COPY public.member (memberid, name, membershipstatus, password, createdat, updatedat) FROM stdin;
    public               postgres    false    225   p�       n          0    33395    reservation 
   TABLE DATA           �   COPY public.reservation (reservationid, memberid, isbn, reservationdate, status, queuenumber, pickupdeadline, createdat, updatedat) FROM stdin;
    public               postgres    false    229   �       �           0    0    author_authorid_seq    SEQUENCE SET     A   SELECT pg_catalog.setval('public.author_authorid_seq', 8, true);
          public               postgres    false    220            �           0    0    bookcopy_copyid_seq    SEQUENCE SET     B   SELECT pg_catalog.setval('public.bookcopy_copyid_seq', 13, true);
          public               postgres    false    232            �           0    0    borrow_borrowid_seq    SEQUENCE SET     B   SELECT pg_catalog.setval('public.borrow_borrowid_seq', 46, true);
          public               postgres    false    226            �           0    0    category_categoryid_seq    SEQUENCE SET     E   SELECT pg_catalog.setval('public.category_categoryid_seq', 7, true);
          public               postgres    false    222            �           0    0    employee_employeeid_seq    SEQUENCE SET     F   SELECT pg_catalog.setval('public.employee_employeeid_seq', 14, true);
          public               postgres    false    217            �           0    0    member_memberid_seq    SEQUENCE SET     A   SELECT pg_catalog.setval('public.member_memberid_seq', 7, true);
          public               postgres    false    224            �           0    0    reservation_reservationid_seq    SEQUENCE SET     K   SELECT pg_catalog.setval('public.reservation_reservationid_seq', 8, true);
          public               postgres    false    228            �           2606    33344    author author_pkey 
   CONSTRAINT     V   ALTER TABLE ONLY public.author
    ADD CONSTRAINT author_pkey PRIMARY KEY (authorid);
 <   ALTER TABLE ONLY public.author DROP CONSTRAINT author_pkey;
       public                 postgres    false    221            �           2606    33417    book_author book_author_pkey 
   CONSTRAINT     f   ALTER TABLE ONLY public.book_author
    ADD CONSTRAINT book_author_pkey PRIMARY KEY (isbn, authorid);
 F   ALTER TABLE ONLY public.book_author DROP CONSTRAINT book_author_pkey;
       public                 postgres    false    230    230            �           2606    33432     book_category book_category_pkey 
   CONSTRAINT     l   ALTER TABLE ONLY public.book_category
    ADD CONSTRAINT book_category_pkey PRIMARY KEY (isbn, categoryid);
 J   ALTER TABLE ONLY public.book_category DROP CONSTRAINT book_category_pkey;
       public                 postgres    false    231    231            �           2606    33330    book book_pkey 
   CONSTRAINT     N   ALTER TABLE ONLY public.book
    ADD CONSTRAINT book_pkey PRIMARY KEY (isbn);
 8   ALTER TABLE ONLY public.book DROP CONSTRAINT book_pkey;
       public                 postgres    false    219            �           2606    33519    bookcopy bookcopy_pkey 
   CONSTRAINT     X   ALTER TABLE ONLY public.bookcopy
    ADD CONSTRAINT bookcopy_pkey PRIMARY KEY (copyid);
 @   ALTER TABLE ONLY public.bookcopy DROP CONSTRAINT bookcopy_pkey;
       public                 postgres    false    233            �           2606    33381    borrow borrow_pkey 
   CONSTRAINT     V   ALTER TABLE ONLY public.borrow
    ADD CONSTRAINT borrow_pkey PRIMARY KEY (borrowid);
 <   ALTER TABLE ONLY public.borrow DROP CONSTRAINT borrow_pkey;
       public                 postgres    false    227            �           2606    33358    category category_pkey 
   CONSTRAINT     \   ALTER TABLE ONLY public.category
    ADD CONSTRAINT category_pkey PRIMARY KEY (categoryid);
 @   ALTER TABLE ONLY public.category DROP CONSTRAINT category_pkey;
       public                 postgres    false    223            �           2606    33323    employee employee_pkey 
   CONSTRAINT     \   ALTER TABLE ONLY public.employee
    ADD CONSTRAINT employee_pkey PRIMARY KEY (employeeid);
 @   ALTER TABLE ONLY public.employee DROP CONSTRAINT employee_pkey;
       public                 postgres    false    218            �           2606    33372    member member_pkey 
   CONSTRAINT     V   ALTER TABLE ONLY public.member
    ADD CONSTRAINT member_pkey PRIMARY KEY (memberid);
 <   ALTER TABLE ONLY public.member DROP CONSTRAINT member_pkey;
       public                 postgres    false    225            �           2606    33402    reservation reservation_pkey 
   CONSTRAINT     e   ALTER TABLE ONLY public.reservation
    ADD CONSTRAINT reservation_pkey PRIMARY KEY (reservationid);
 F   ALTER TABLE ONLY public.reservation DROP CONSTRAINT reservation_pkey;
       public                 postgres    false    229            �           1259    33392    idx_unique_borrow_member    INDEX     q   CREATE UNIQUE INDEX idx_unique_borrow_member ON public.borrow USING btree (memberid) WHERE (returndate IS NULL);
 ,   DROP INDEX public.idx_unique_borrow_member;
       public                 postgres    false    227    227            �           2620    33547 (   reservation trg_adjust_reservation_queue    TRIGGER     )  CREATE TRIGGER trg_adjust_reservation_queue AFTER UPDATE ON public.reservation FOR EACH ROW WHEN ((((old.status)::text = ANY (ARRAY['Active'::text, 'Reserved'::text])) AND ((new.status)::text = ANY (ARRAY['Canceled'::text, 'PickedUp'::text])))) EXECUTE FUNCTION public.adjust_reservation_queue();
 A   DROP TRIGGER trg_adjust_reservation_queue ON public.reservation;
       public               postgres    false    229    229    246            �           2620    33561 !   borrow trg_assign_book_copy_after    TRIGGER     �   CREATE TRIGGER trg_assign_book_copy_after BEFORE INSERT OR UPDATE ON public.borrow FOR EACH ROW EXECUTE FUNCTION public.assign_book_copy();
 :   DROP TRIGGER trg_assign_book_copy_after ON public.borrow;
       public               postgres    false    227    248            �           2620    33569 %   book trg_check_book_associations_book    TRIGGER     �   CREATE CONSTRAINT TRIGGER trg_check_book_associations_book AFTER INSERT OR DELETE OR UPDATE ON public.book DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.check_book_associations();
 >   DROP TRIGGER trg_check_book_associations_book ON public.book;
       public               postgres    false    219    249            �           2620    33571 3   book_author trg_check_book_associations_book_author    TRIGGER     �   CREATE CONSTRAINT TRIGGER trg_check_book_associations_book_author AFTER INSERT OR DELETE OR UPDATE ON public.book_author DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.check_book_associations();
 L   DROP TRIGGER trg_check_book_associations_book_author ON public.book_author;
       public               postgres    false    230    249            �           2620    33573 7   book_category trg_check_book_associations_book_category    TRIGGER     �   CREATE CONSTRAINT TRIGGER trg_check_book_associations_book_category AFTER INSERT OR DELETE OR UPDATE ON public.book_category DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.check_book_associations();
 P   DROP TRIGGER trg_check_book_associations_book_category ON public.book_category;
       public               postgres    false    249    231            �           2620    33560 )   borrow trg_check_borrow_permission_before    TRIGGER     �   CREATE TRIGGER trg_check_borrow_permission_before BEFORE INSERT OR UPDATE ON public.borrow FOR EACH ROW EXECUTE FUNCTION public.check_borrow_permission();
 B   DROP TRIGGER trg_check_borrow_permission_before ON public.borrow;
       public               postgres    false    227    251            �           2620    33502    borrow trg_check_late_returns    TRIGGER     �   CREATE TRIGGER trg_check_late_returns AFTER UPDATE OF returndate ON public.borrow FOR EACH ROW WHEN (((old.returndate IS NULL) AND (new.returndate IS NOT NULL))) EXECUTE FUNCTION public.check_late_returns_and_freeze_member();
 6   DROP TRIGGER trg_check_late_returns ON public.borrow;
       public               postgres    false    227    227    227    250            �           2620    33562 !   bookcopy trg_sync_bookcopy_status    TRIGGER     �   CREATE TRIGGER trg_sync_bookcopy_status AFTER UPDATE OF status ON public.bookcopy FOR EACH ROW WHEN ((((old.status)::text = 'Borrowed'::text) AND ((new.status)::text = 'Returned'::text))) EXECUTE FUNCTION public.sync_bookcopy_and_update_status();
 :   DROP TRIGGER trg_sync_bookcopy_status ON public.bookcopy;
       public               postgres    false    233    233    233    252            �           2620    33559    bookcopy trg_update_on_add_copy    TRIGGER     �   CREATE TRIGGER trg_update_on_add_copy AFTER INSERT ON public.bookcopy FOR EACH ROW EXECUTE FUNCTION public.sync_bookcopy_and_update_status();
 8   DROP TRIGGER trg_update_on_add_copy ON public.bookcopy;
       public               postgres    false    233    252            �           2620    33558    borrow trg_update_on_return    TRIGGER     �   CREATE TRIGGER trg_update_on_return AFTER UPDATE ON public.borrow FOR EACH ROW WHEN ((new.returndate IS NOT NULL)) EXECUTE FUNCTION public.sync_bookcopy_and_update_status();
 4   DROP TRIGGER trg_update_on_return ON public.borrow;
       public               postgres    false    227    227    252            �           2620    33551    bookcopy trg_update_updatedat    TRIGGER     �   CREATE TRIGGER trg_update_updatedat BEFORE UPDATE ON public.bookcopy FOR EACH ROW EXECUTE FUNCTION public.update_updatedat_column();
 6   DROP TRIGGER trg_update_updatedat ON public.bookcopy;
       public               postgres    false    247    233            �           2606    33345    author fk_author_employee    FK CONSTRAINT     �   ALTER TABLE ONLY public.author
    ADD CONSTRAINT fk_author_employee FOREIGN KEY (employeeid) REFERENCES public.employee(employeeid);
 C   ALTER TABLE ONLY public.author DROP CONSTRAINT fk_author_employee;
       public               postgres    false    221    218    4773            �           2606    33423 !   book_author fk_book_author_author    FK CONSTRAINT     �   ALTER TABLE ONLY public.book_author
    ADD CONSTRAINT fk_book_author_author FOREIGN KEY (authorid) REFERENCES public.author(authorid);
 K   ALTER TABLE ONLY public.book_author DROP CONSTRAINT fk_book_author_author;
       public               postgres    false    230    4777    221            �           2606    33418    book_author fk_book_author_book    FK CONSTRAINT     |   ALTER TABLE ONLY public.book_author
    ADD CONSTRAINT fk_book_author_book FOREIGN KEY (isbn) REFERENCES public.book(isbn);
 I   ALTER TABLE ONLY public.book_author DROP CONSTRAINT fk_book_author_book;
       public               postgres    false    219    230    4775            �           2606    33433 #   book_category fk_book_category_book    FK CONSTRAINT     �   ALTER TABLE ONLY public.book_category
    ADD CONSTRAINT fk_book_category_book FOREIGN KEY (isbn) REFERENCES public.book(isbn);
 M   ALTER TABLE ONLY public.book_category DROP CONSTRAINT fk_book_category_book;
       public               postgres    false    219    4775    231            �           2606    33438 '   book_category fk_book_category_category    FK CONSTRAINT     �   ALTER TABLE ONLY public.book_category
    ADD CONSTRAINT fk_book_category_category FOREIGN KEY (categoryid) REFERENCES public.category(categoryid);
 Q   ALTER TABLE ONLY public.book_category DROP CONSTRAINT fk_book_category_category;
       public               postgres    false    4779    231    223            �           2606    33331    book fk_book_employee    FK CONSTRAINT     �   ALTER TABLE ONLY public.book
    ADD CONSTRAINT fk_book_employee FOREIGN KEY (employeeid) REFERENCES public.employee(employeeid);
 ?   ALTER TABLE ONLY public.book DROP CONSTRAINT fk_book_employee;
       public               postgres    false    218    4773    219            �           2606    33520    bookcopy fk_bookcopy_book    FK CONSTRAINT     v   ALTER TABLE ONLY public.bookcopy
    ADD CONSTRAINT fk_bookcopy_book FOREIGN KEY (isbn) REFERENCES public.book(isbn);
 C   ALTER TABLE ONLY public.bookcopy DROP CONSTRAINT fk_bookcopy_book;
       public               postgres    false    219    233    4775            �           2606    33387    borrow fk_borrow_book    FK CONSTRAINT     r   ALTER TABLE ONLY public.borrow
    ADD CONSTRAINT fk_borrow_book FOREIGN KEY (isbn) REFERENCES public.book(isbn);
 ?   ALTER TABLE ONLY public.borrow DROP CONSTRAINT fk_borrow_book;
       public               postgres    false    219    227    4775            �           2606    33525    borrow fk_borrow_bookcopy    FK CONSTRAINT     ~   ALTER TABLE ONLY public.borrow
    ADD CONSTRAINT fk_borrow_bookcopy FOREIGN KEY (copyid) REFERENCES public.bookcopy(copyid);
 C   ALTER TABLE ONLY public.borrow DROP CONSTRAINT fk_borrow_bookcopy;
       public               postgres    false    227    4792    233            �           2606    33382    borrow fk_borrow_member    FK CONSTRAINT     ~   ALTER TABLE ONLY public.borrow
    ADD CONSTRAINT fk_borrow_member FOREIGN KEY (memberid) REFERENCES public.member(memberid);
 A   ALTER TABLE ONLY public.borrow DROP CONSTRAINT fk_borrow_member;
       public               postgres    false    4781    225    227            �           2606    33359    category fk_category_employee    FK CONSTRAINT     �   ALTER TABLE ONLY public.category
    ADD CONSTRAINT fk_category_employee FOREIGN KEY (employeeid) REFERENCES public.employee(employeeid);
 G   ALTER TABLE ONLY public.category DROP CONSTRAINT fk_category_employee;
       public               postgres    false    218    4773    223            �           2606    33408    reservation fk_reservation_book    FK CONSTRAINT     |   ALTER TABLE ONLY public.reservation
    ADD CONSTRAINT fk_reservation_book FOREIGN KEY (isbn) REFERENCES public.book(isbn);
 I   ALTER TABLE ONLY public.reservation DROP CONSTRAINT fk_reservation_book;
       public               postgres    false    4775    229    219            �           2606    33403 !   reservation fk_reservation_member    FK CONSTRAINT     �   ALTER TABLE ONLY public.reservation
    ADD CONSTRAINT fk_reservation_member FOREIGN KEY (memberid) REFERENCES public.member(memberid);
 K   ALTER TABLE ONLY public.reservation DROP CONSTRAINT fk_reservation_member;
       public               postgres    false    4781    225    229            f   �   x�����0E�ׯx?@C_)h7�@�D]]�������1N.���I�p]���;?� �rRY.��PT��߉R����w/�����FBk��[<�Ն 2�S@ݛ�l\���m�1�٘;ֳ�7��길WĆcL|��F���?�1������h�%i)��%��b7�� 1?y�      d     x����J1�u�)����M�� ���������vpL ����
SR�ͅ�qN��%T�B��:v�O^V�?v�Ua��|�t}��F���G�I{���g�u��R�e��OC�)�-C���Pg�#z)�vB;@�'����1�xI�6���6����!��xm�4�)}b!{�%��q����i=�� �������V�SM���C��"v��������WN������U794���M�e���J9�mh�,5:�U�	�A錩�DUU?��y      o   :   x�]ͱ  ����wq�9��TY��IO�*(�1����,6��Q��q��D� p�      p   :   x�eʱ  ��/��z��:LÝ�خ\47�.��CFq��t&[���p���      r   �   x���;jCA��iހ���K֑�!.��d�y)'E�ׂ�{�b���6�I�������~9oB�G�#�A��[%5����<]��'��Ay2��Ǐ{���9�W��^D[�=QC�l=�d[ yZ:����z�]��wqz`i-��Z�K�{�bm�R#)�i�q�[�]pX�(`�dk',��������3��i{��^�����E      l   a   x�����0k3E��c��!2���#)�(E$K�ݽN���s����TO��9� �,kxQ$�f�ٵ��w�H������^�^�E�Ո�͏-;      h   �   x����� F��)�%��oq3����L�H(]ҷ���}NN�}k
-�$H�B΂&���G�T�A��R�!NW���J��b=A�[n�~��p{bnG����R���ץ���K���8��'��c_�sb�      c   �   x����
�0E痯�����1��"8��%j!)MMQ�{n:�܋p��(�}�@�@��P�P$�����`��T����Y����*�75��ݻn��yz�o��m�Uк�yypϐ =24�FåK|�_h,��d�y��R��Wh      j   �   x��Ͻ� ���p�@�Śn�g�f��r@��P0��x��G��$O��apVz��Y��j�0���bM��]/dϻz�7�ND�.(:�M���*��O���\�Ϧ��b���E�t!��^S*&%�	==�Ӆ��&�b�RB^\?f�      n   I   x���4�4�06434�0140�4202�50"C#+s+3=Ks#KN��̲TNC�?|�pKq��qqq B��     