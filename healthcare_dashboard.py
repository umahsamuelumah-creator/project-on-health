"""
Healthcare Staff Management Dashboard
====================================

This script implements a simple desktop application for managing
hospital and healthcare staff.  It is designed to run locally
without any third‑party dependencies using Python’s built‑in
``tkinter`` module for the user interface and ``sqlite3`` for
persistent storage.  The application provides a friendly
dashboard where administrators can:

* Register staff members, assign roles and record certification
  expiry dates.
* Create shift schedules and assign staff to morning, evening or
  night shifts.
* Log safety concerns and track their resolution.
* Manage an inventory of supplies with low‑stock warnings and
  expiry tracking.
* Monitor training and certification status, sending email
  reminders to staff whose credentials are about to expire.
* Collect feedback through simple surveys and view aggregated
  responses.
* Generate basic reports for compliance and management review.

The application emphasises good practice in healthcare workforce
management: thoughtful scheduling to support work‑life balance
【113269060646120†L154-L185】, proactive training programmes to improve
employee satisfaction and patient outcomes【556873922389706†L78-L110】,
real‑time inventory tracking to reduce stockouts【55535749485609†L115-L139】,
and a culture of open, non‑punitive safety reporting【224105111717826†L50-L61】.

You can run this file directly with ``python healthcare_dashboard.py``.
It will create an ``healthcare.db`` SQLite database in the
current directory if one does not already exist.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, date, timedelta
import sqlite3
import smtplib
from email.mime.text import MIMEText


class HealthcareApp:
    """Main application class for the healthcare management dashboard."""

    def __init__(self, master: tk.Tk) -> None:
        self.master = master
        self.master.title("Healthcare Staff Management Dashboard")
        self.master.geometry("1000x700")

        # Connect to (or create) the SQLite database
        self.conn = sqlite3.connect("healthcare.db")
        self.create_tables()

        # Email settings (not persisted for security)
        self.smtp_host: str = ""
        self.smtp_port: int = 587
        self.smtp_user: str = ""
        self.smtp_pass: str = ""

        # Create notebook for tabbed interface
        self.notebook = ttk.Notebook(self.master)
        self.notebook.pack(fill="both", expand=True)

        # Initialise tabs
        self.create_dashboard_tab()
        self.create_staff_tab()
        self.create_schedule_tab()
        self.create_safety_tab()
        self.create_inventory_tab()
        self.create_training_tab()
        self.create_feedback_tab()
        self.create_reports_tab()

        # Populate dashboard summary on startup
        self.refresh_dashboard()

    # Database schema -----------------------------------------------------
    def create_tables(self) -> None:
        """Create required tables if they do not already exist."""
        c = self.conn.cursor()
        # Staff table: stores basic employee information and certifications
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS staff (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                role TEXT,
                certification_name TEXT,
                certification_expiry DATE,
                training_due DATE
            )
            """
        )

        # Shifts table: date, shift type and assigned staff member
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS shifts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shift_date DATE NOT NULL,
                shift_type TEXT NOT NULL,
                staff_id INTEGER,
                FOREIGN KEY (staff_id) REFERENCES staff(id)
            )
            """
        )

        # Safety concerns table: logs incident reports
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS safety (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reported_date DATE NOT NULL,
                staff_id INTEGER,
                description TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Open',
                FOREIGN KEY (staff_id) REFERENCES staff(id)
            )
            """
        )

        # Inventory table: tracks medical or support items
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                min_quantity INTEGER NOT NULL,
                expiry DATE
            )
            """
        )

        # Feedback table: stores survey responses
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                feedback_date DATE NOT NULL,
                staff_id INTEGER,
                topic TEXT,
                rating INTEGER,
                comments TEXT,
                FOREIGN KEY (staff_id) REFERENCES staff(id)
            )
            """
        )

        # Commit schema changes
        self.conn.commit()

    # Dashboard tab --------------------------------------------------------
    def create_dashboard_tab(self) -> None:
        """Create the main dashboard overview tab."""
        self.dashboard_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.dashboard_frame, text="Dashboard")

        # Summary labels (populated later)
        self.summary_vars = {
            'staff_count': tk.StringVar(),
            'upcoming_shifts': tk.StringVar(),
            'pending_safety': tk.StringVar(),
            'low_inventory': tk.StringVar(),
            'cert_due': tk.StringVar(),
            'feedback_count': tk.StringVar(),
        }

        row = 0
        for key, var in self.summary_vars.items():
            label = ttk.Label(
                self.dashboard_frame,
                textvariable=var,
                font=('Arial', 12, 'bold')
            )
            label.grid(row=row, column=0, sticky='w', padx=10, pady=5)
            row += 1

        refresh_btn = ttk.Button(
            self.dashboard_frame,
            text="Refresh Dashboard",
            command=self.refresh_dashboard
        )
        refresh_btn.grid(row=row, column=0, sticky='w', padx=10, pady=10)

    def refresh_dashboard(self) -> None:
        """Compute and display summary information."""
        c = self.conn.cursor()
        # Count staff
        c.execute("SELECT COUNT(*) FROM staff")
        staff_count = c.fetchone()[0]
        # Upcoming shifts within next 7 days
        today = date.today()
        week_ahead = today + timedelta(days=7)
        c.execute(
            "SELECT COUNT(*) FROM shifts WHERE shift_date BETWEEN ? AND ?",
            (today.isoformat(), week_ahead.isoformat()),
        )
        upcoming_shifts = c.fetchone()[0]
        # Open safety concerns
        c.execute("SELECT COUNT(*) FROM safety WHERE status='Open'")
        pending_safety = c.fetchone()[0]
        # Low inventory items or expired
        c.execute(
            "SELECT COUNT(*) FROM inventory WHERE quantity <= min_quantity OR (expiry IS NOT NULL AND expiry <> '' AND expiry < ?)",
            (today.isoformat(),),
        )
        low_inventory = c.fetchone()[0]
        # Certifications due within 60 days or expired
        due_date_limit = today + timedelta(days=60)
        c.execute(
            "SELECT COUNT(*) FROM staff WHERE certification_expiry IS NOT NULL AND certification_expiry <> '' AND certification_expiry <= ?",
            (due_date_limit.isoformat(),),
        )
        cert_due = c.fetchone()[0]
        # Feedback count
        c.execute("SELECT COUNT(*) FROM feedback")
        feedback_count = c.fetchone()[0]

        # Update summary variables
        self.summary_vars['staff_count'].set(f"Total staff: {staff_count}")
        self.summary_vars['upcoming_shifts'].set(
            f"Shifts in next 7 days: {upcoming_shifts}" if upcoming_shifts else "No upcoming shifts"
        )
        self.summary_vars['pending_safety'].set(
            f"Open safety concerns: {pending_safety}" if pending_safety else "No open safety concerns"
        )
        self.summary_vars['low_inventory'].set(
            f"Low/expired inventory items: {low_inventory}" if low_inventory else "Inventory is sufficient"
        )
        self.summary_vars['cert_due'].set(
            f"Certifications due within 60 days: {cert_due}" if cert_due else "No certifications due soon"
        )
        self.summary_vars['feedback_count'].set(
            f"Feedback entries: {feedback_count}"
        )

    # Staff tab ------------------------------------------------------------
    def create_staff_tab(self) -> None:
        """Create the staff management tab."""
        self.staff_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.staff_frame, text="Staff")

        # Form for adding staff
        form_frame = ttk.LabelFrame(self.staff_frame, text="Add / Edit Staff")
        form_frame.grid(row=0, column=0, sticky='nw', padx=10, pady=10)

        ttk.Label(form_frame, text="Name:").grid(row=0, column=0, sticky='e')
        ttk.Label(form_frame, text="Email:").grid(row=1, column=0, sticky='e')
        ttk.Label(form_frame, text="Role:").grid(row=2, column=0, sticky='e')
        ttk.Label(form_frame, text="Certification Name:").grid(row=3, column=0, sticky='e')
        ttk.Label(form_frame, text="Certification Expiry (YYYY-MM-DD):").grid(row=4, column=0, sticky='e')
        ttk.Label(form_frame, text="Training Due (YYYY-MM-DD):").grid(row=5, column=0, sticky='e')

        self.staff_name_var = tk.StringVar()
        self.staff_email_var = tk.StringVar()
        self.staff_role_var = tk.StringVar()
        self.staff_cert_name_var = tk.StringVar()
        self.staff_cert_expiry_var = tk.StringVar()
        self.staff_training_due_var = tk.StringVar()

        ttk.Entry(form_frame, textvariable=self.staff_name_var, width=30).grid(row=0, column=1, pady=2)
        ttk.Entry(form_frame, textvariable=self.staff_email_var, width=30).grid(row=1, column=1, pady=2)
        ttk.Entry(form_frame, textvariable=self.staff_role_var, width=30).grid(row=2, column=1, pady=2)
        ttk.Entry(form_frame, textvariable=self.staff_cert_name_var, width=30).grid(row=3, column=1, pady=2)
        ttk.Entry(form_frame, textvariable=self.staff_cert_expiry_var, width=30).grid(row=4, column=1, pady=2)
        ttk.Entry(form_frame, textvariable=self.staff_training_due_var, width=30).grid(row=5, column=1, pady=2)

        self.selected_staff_id: int | None = None

        save_btn = ttk.Button(form_frame, text="Save Staff", command=self.save_staff)
        save_btn.grid(row=6, column=0, columnspan=2, pady=5)

        clear_btn = ttk.Button(form_frame, text="Clear Form", command=self.clear_staff_form)
        clear_btn.grid(row=7, column=0, columnspan=2, pady=5)

        # Staff table
        table_frame = ttk.Frame(self.staff_frame)
        table_frame.grid(row=0, column=1, sticky='nsew', padx=10, pady=10)
        self.staff_tree = ttk.Treeview(table_frame, columns=("ID", "Name", "Email", "Role", "Cert", "Expiry", "Training", "Status"), show='headings')
        for col in ("ID", "Name", "Email", "Role", "Cert", "Expiry", "Training", "Status"):
            self.staff_tree.heading(col, text=col)
            # Set reasonable widths
            if col == "ID":
                self.staff_tree.column(col, width=40, anchor='center')
            elif col in ("Name", "Email", "Cert"):
                self.staff_tree.column(col, width=150)
            else:
                self.staff_tree.column(col, width=100)
        self.staff_tree.pack(fill='both', expand=True)
        self.staff_tree.bind("<Double-1>", self.on_staff_select)

        # Buttons for actions
        actions_frame = ttk.Frame(self.staff_frame)
        actions_frame.grid(row=1, column=1, sticky='w', padx=10, pady=5)
        del_btn = ttk.Button(actions_frame, text="Delete Selected", command=self.delete_selected_staff)
        del_btn.grid(row=0, column=0, padx=5)
        notify_btn = ttk.Button(actions_frame, text="Notify Due/Expired", command=self.notify_due_certifications)
        notify_btn.grid(row=0, column=1, padx=5)

        self.refresh_staff_table()

    def clear_staff_form(self) -> None:
        """Reset the staff form fields and selection."""
        self.selected_staff_id = None
        self.staff_name_var.set("")
        self.staff_email_var.set("")
        self.staff_role_var.set("")
        self.staff_cert_name_var.set("")
        self.staff_cert_expiry_var.set("")
        self.staff_training_due_var.set("")

    def save_staff(self) -> None:
        """Insert or update a staff member based on form input."""
        name = self.staff_name_var.get().strip()
        email = self.staff_email_var.get().strip()
        role = self.staff_role_var.get().strip()
        cert_name = self.staff_cert_name_var.get().strip()
        cert_expiry = self.staff_cert_expiry_var.get().strip()
        training_due = self.staff_training_due_var.get().strip()

        if not name or not email:
            messagebox.showerror("Error", "Name and Email are required.")
            return

        # Validate date formats
        for label, datestr in [("Certification expiry", cert_expiry), ("Training due", training_due)]:
            if datestr:
                try:
                    datetime.strptime(datestr, "%Y-%m-%d")
                except ValueError:
                    messagebox.showerror("Error", f"{label} must be in YYYY-MM-DD format.")
                    return

        c = self.conn.cursor()
        if self.selected_staff_id:
            # Update existing
            c.execute(
                """
                UPDATE staff
                SET name=?, email=?, role=?, certification_name=?, certification_expiry=?, training_due=?
                WHERE id=?
                """,
                (name, email, role or None, cert_name or None, cert_expiry or None, training_due or None, self.selected_staff_id),
            )
        else:
            c.execute(
                """
                INSERT INTO staff (name, email, role, certification_name, certification_expiry, training_due)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (name, email, role or None, cert_name or None, cert_expiry or None, training_due or None),
            )
        self.conn.commit()
        self.refresh_staff_table()
        self.clear_staff_form()
        self.refresh_dashboard()
        messagebox.showinfo("Success", "Staff information saved.")

    def refresh_staff_table(self) -> None:
        """Reload all staff records into the tree view."""
        for item in self.staff_tree.get_children():
            self.staff_tree.delete(item)
        c = self.conn.cursor()
        c.execute("SELECT id, name, email, role, certification_name, certification_expiry, training_due FROM staff")
        rows = c.fetchall()
        today = date.today()
        for row in rows:
            staff_id, name, email, role, cert_name, cert_expiry, training_due = row
            # Determine certification status
            status = "N/A"
            if cert_expiry:
                try:
                    exp_date = datetime.strptime(cert_expiry, "%Y-%m-%d").date()
                    delta = (exp_date - today).days
                    if delta < 0:
                        status = "Expired"
                    elif delta <= 60:
                        status = "Due soon"
                    else:
                        status = "Valid"
                except Exception:
                    status = "Unknown"
            self.staff_tree.insert("", "end", values=(staff_id, name, email, role or '', cert_name or '', cert_expiry or '', training_due or '', status))

    def on_staff_select(self, event) -> None:
        """Load selected staff member into the form for editing."""
        item_id = self.staff_tree.focus()
        if not item_id:
            return
        values = self.staff_tree.item(item_id, 'values')
        if not values:
            return
        self.selected_staff_id = int(values[0])
        # Fill form
        self.staff_name_var.set(values[1])
        self.staff_email_var.set(values[2])
        self.staff_role_var.set(values[3])
        self.staff_cert_name_var.set(values[4])
        self.staff_cert_expiry_var.set(values[5])
        self.staff_training_due_var.set(values[6])

    def delete_selected_staff(self) -> None:
        """Remove the currently selected staff member."""
        item_id = self.staff_tree.focus()
        if not item_id:
            messagebox.showwarning("Warning", "No staff selected.")
            return
        values = self.staff_tree.item(item_id, 'values')
        staff_id = int(values[0])
        confirm = messagebox.askyesno("Confirm", "Are you sure you want to delete this staff member?")
        if confirm:
            c = self.conn.cursor()
            c.execute("DELETE FROM staff WHERE id=?", (staff_id,))
            self.conn.commit()
            self.refresh_staff_table()
            self.refresh_dashboard()
            messagebox.showinfo("Deleted", "Staff member deleted.")

    def notify_due_certifications(self) -> None:
        """Send email notifications to staff with due or expired certifications."""
        # Collect staff requiring notification
        today = date.today()
        due_limit = today + timedelta(days=60)
        c = self.conn.cursor()
        c.execute(
            "SELECT id, name, email, certification_name, certification_expiry FROM staff WHERE certification_expiry IS NOT NULL AND certification_expiry <> '' AND certification_expiry <= ?",
            (due_limit.isoformat(),),
        )
        staff_list = c.fetchall()
        if not staff_list:
            messagebox.showinfo("No notifications", "No staff have certifications due within 60 days.")
            return

        # Prompt for email settings if not set
        if not self.smtp_host or not self.smtp_user or not self.smtp_pass:
            self.configure_email_settings()
            if not self.smtp_host:
                return  # User cancelled

        # Send notifications
        errors = []
        for staff_id, name, email, cert_name, cert_expiry in staff_list:
            subject = "Certification Renewal Reminder"
            days_remaining = (datetime.strptime(cert_expiry, "%Y-%m-%d").date() - today).days
            if days_remaining < 0:
                message_body = (
                    f"Dear {name},\n\n"
                    f"Your certification '{cert_name}' expired on {cert_expiry}. Please renew immediately to maintain compliance.\n\n"
                    "This is an automated reminder from the healthcare management system."
                )
            else:
                message_body = (
                    f"Dear {name},\n\n"
                    f"Your certification '{cert_name}' will expire on {cert_expiry} (in {days_remaining} days). Please ensure you renew your certification before it expires.\n\n"
                    "This is an automated reminder from the healthcare management system."
                )
            try:
                self.send_email(email, subject, message_body)
            except Exception as e:
                errors.append((email, str(e)))
        if errors:
            error_msg = "Some emails could not be sent:\n" + "\n".join([f"{addr}: {err}" for addr, err in errors])
            messagebox.showerror("Notification result", error_msg)
        else:
            messagebox.showinfo("Notifications sent", f"Sent notifications to {len(staff_list)} staff.")

    # Email support -------------------------------------------------------
    def configure_email_settings(self) -> None:
        """Prompt the user to enter SMTP server settings."""
        settings_win = tk.Toplevel(self.master)
        settings_win.title("Email Settings")
        settings_win.grab_set()

        ttk.Label(settings_win, text="SMTP Host:").grid(row=0, column=0, sticky='e')
        ttk.Label(settings_win, text="Port:").grid(row=1, column=0, sticky='e')
        ttk.Label(settings_win, text="Username:").grid(row=2, column=0, sticky='e')
        ttk.Label(settings_win, text="Password:").grid(row=3, column=0, sticky='e')

        host_var = tk.StringVar(value=self.smtp_host or "smtp.example.com")
        port_var = tk.StringVar(value=str(self.smtp_port or 587))
        user_var = tk.StringVar(value=self.smtp_user)
        pass_var = tk.StringVar(value=self.smtp_pass)

        host_entry = ttk.Entry(settings_win, textvariable=host_var)
        port_entry = ttk.Entry(settings_win, textvariable=port_var)
        user_entry = ttk.Entry(settings_win, textvariable=user_var)
        pass_entry = ttk.Entry(settings_win, textvariable=pass_var, show='*')

        host_entry.grid(row=0, column=1, padx=5, pady=2)
        port_entry.grid(row=1, column=1, padx=5, pady=2)
        user_entry.grid(row=2, column=1, padx=5, pady=2)
        pass_entry.grid(row=3, column=1, padx=5, pady=2)

        def save_settings():
            self.smtp_host = host_var.get().strip()
            try:
                self.smtp_port = int(port_var.get().strip())
            except ValueError:
                messagebox.showerror("Error", "Port must be a number.")
                return
            self.smtp_user = user_var.get().strip()
            self.smtp_pass = pass_var.get().strip()
            settings_win.destroy()

        ttk.Button(settings_win, text="Save", command=save_settings).grid(row=4, column=0, columnspan=2, pady=5)

    def send_email(self, recipient: str, subject: str, body: str) -> None:
        """Send an email using the configured SMTP settings."""
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = self.smtp_user
        msg['To'] = recipient
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls()
            server.login(self.smtp_user, self.smtp_pass)
            server.send_message(msg)

    # Schedule tab --------------------------------------------------------
    def create_schedule_tab(self) -> None:
        """Create the scheduling tab where shifts can be assigned."""
        self.schedule_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.schedule_frame, text="Scheduling")

        # Form for adding a shift
        form = ttk.LabelFrame(self.schedule_frame, text="Add Shift")
        form.grid(row=0, column=0, sticky='nw', padx=10, pady=10)

        ttk.Label(form, text="Date (YYYY-MM-DD):").grid(row=0, column=0, sticky='e')
        ttk.Label(form, text="Shift Type:").grid(row=1, column=0, sticky='e')
        ttk.Label(form, text="Assign Staff:").grid(row=2, column=0, sticky='e')

        self.shift_date_var = tk.StringVar()
        self.shift_type_var = tk.StringVar()
        self.shift_staff_var = tk.StringVar()

        ttk.Entry(form, textvariable=self.shift_date_var, width=20).grid(row=0, column=1, pady=2)
        ttk.Combobox(form, textvariable=self.shift_type_var, values=("Morning", "Evening", "Night"), width=18).grid(row=1, column=1, pady=2)
        # Staff drop-down will be populated later
        self.shift_staff_combo = ttk.Combobox(form, textvariable=self.shift_staff_var, width=18)
        self.shift_staff_combo.grid(row=2, column=1, pady=2)

        ttk.Button(form, text="Add Shift", command=self.add_shift).grid(row=3, column=0, columnspan=2, pady=5)

        # Table to display shifts
        table_frame = ttk.Frame(self.schedule_frame)
        table_frame.grid(row=0, column=1, sticky='nsew', padx=10, pady=10)
        self.shifts_tree = ttk.Treeview(table_frame, columns=("ID", "Date", "Type", "Staff"), show='headings')
        for col, width in zip(("ID", "Date", "Type", "Staff"), (40, 100, 80, 150)):
            self.shifts_tree.heading(col, text=col)
            self.shifts_tree.column(col, width=width)
        self.shifts_tree.pack(fill='both', expand=True)

        actions = ttk.Frame(self.schedule_frame)
        actions.grid(row=1, column=1, sticky='w', padx=10, pady=5)
        del_shift_btn = ttk.Button(actions, text="Delete Selected Shift", command=self.delete_selected_shift)
        del_shift_btn.grid(row=0, column=0, padx=5)
        notify_shift_btn = ttk.Button(actions, text="Email Assigned Staff", command=self.notify_shifts)
        notify_shift_btn.grid(row=0, column=1, padx=5)

        # Populate staff combobox and shift table
        self.refresh_shift_staff_list()
        self.refresh_shifts_table()

    def refresh_shift_staff_list(self) -> None:
        """Update the list of available staff for shift assignment."""
        c = self.conn.cursor()
        c.execute("SELECT id, name FROM staff")
        staff = c.fetchall()
        self.shift_staff_options = [f"{sid}:{name}" for sid, name in staff]
        self.shift_staff_combo['values'] = self.shift_staff_options

    def add_shift(self) -> None:
        """Add a new shift assignment to the database."""
        date_str = self.shift_date_var.get().strip()
        shift_type = self.shift_type_var.get().strip()
        staff_selection = self.shift_staff_var.get().strip()
        if not date_str or not shift_type or not staff_selection:
            messagebox.showerror("Error", "All fields are required.")
            return
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Error", "Date must be in YYYY-MM-DD format.")
            return
        # Parse staff id from selection (format "id:name")
        try:
            staff_id = int(staff_selection.split(":")[0])
        except Exception:
            messagebox.showerror("Error", "Invalid staff selection.")
            return
        c = self.conn.cursor()
        c.execute(
            "INSERT INTO shifts (shift_date, shift_type, staff_id) VALUES (?, ?, ?)",
            (date_str, shift_type, staff_id),
        )
        self.conn.commit()
        self.refresh_shifts_table()
        self.refresh_dashboard()
        messagebox.showinfo("Success", "Shift added.")

    def refresh_shifts_table(self) -> None:
        """Reload the list of scheduled shifts."""
        for item in self.shifts_tree.get_children():
            self.shifts_tree.delete(item)
        c = self.conn.cursor()
        c.execute("SELECT id, shift_date, shift_type, staff_id FROM shifts ORDER BY shift_date")
        rows = c.fetchall()
        for row in rows:
            shift_id, date_str, shift_type, staff_id = row
            # Get staff name
            c.execute("SELECT name FROM staff WHERE id=?", (staff_id,))
            staff_row = c.fetchone()
            staff_name = staff_row[0] if staff_row else ""
            self.shifts_tree.insert("", "end", values=(shift_id, date_str, shift_type, staff_name))

    def delete_selected_shift(self) -> None:
        """Delete the selected shift assignment."""
        item_id = self.shifts_tree.focus()
        if not item_id:
            messagebox.showwarning("Warning", "No shift selected.")
            return
        values = self.shifts_tree.item(item_id, 'values')
        shift_id = int(values[0])
        confirm = messagebox.askyesno("Confirm", "Are you sure you want to delete this shift?")
        if confirm:
            c = self.conn.cursor()
            c.execute("DELETE FROM shifts WHERE id=?", (shift_id,))
            self.conn.commit()
            self.refresh_shifts_table()
            self.refresh_dashboard()
            messagebox.showinfo("Deleted", "Shift deleted.")

    def notify_shifts(self) -> None:
        """Send an email to each staff member with their upcoming shifts."""
        # Prompt for email settings if not set
        if not self.smtp_host or not self.smtp_user or not self.smtp_pass:
            self.configure_email_settings()
            if not self.smtp_host:
                return
        c = self.conn.cursor()
        # Group shifts by staff for next week
        today = date.today()
        week_ahead = today + timedelta(days=7)
        c.execute(
            "SELECT s.staff_id, st.name, st.email, GROUP_CONCAT(shift_date || ' (' || shift_type || ')', '\n')"
            " FROM shifts s JOIN staff st ON s.staff_id = st.id"
            " WHERE s.shift_date BETWEEN ? AND ?"
            " GROUP BY s.staff_id, st.name, st.email",
            (today.isoformat(), week_ahead.isoformat()),
        )
        data = c.fetchall()
        if not data:
            messagebox.showinfo("No upcoming shifts", "There are no upcoming shifts within the next week.")
            return
        errors = []
        for staff_id, name, email, shift_info in data:
            subject = "Your Upcoming Shifts"
            body = f"Dear {name},\n\nHere is your schedule for the next week:\n\n{shift_info}\n\nBest regards,\nHealthcare Support Service"
            try:
                self.send_email(email, subject, body)
            except Exception as e:
                errors.append((email, str(e)))
        if errors:
            err_msg = "Some notifications failed:\n" + "\n".join([f"{addr}: {err}" for addr, err in errors])
            messagebox.showerror("Email errors", err_msg)
        else:
            messagebox.showinfo("Emails sent", f"Sent shift notifications to {len(data)} staff members.")

    # Safety tab ----------------------------------------------------------
    def create_safety_tab(self) -> None:
        """Create the safety concerns tab."""
        self.safety_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.safety_frame, text="Safety")

        # Form to add a safety concern
        form = ttk.LabelFrame(self.safety_frame, text="Report Safety Concern")
        form.grid(row=0, column=0, sticky='nw', padx=10, pady=10)
        ttk.Label(form, text="Date (YYYY-MM-DD):").grid(row=0, column=0, sticky='e')
        ttk.Label(form, text="Staff (optional):").grid(row=1, column=0, sticky='e')
        ttk.Label(form, text="Description:").grid(row=2, column=0, sticky='ne')

        self.safety_date_var = tk.StringVar(value=date.today().isoformat())
        self.safety_staff_var = tk.StringVar()
        self.safety_desc_text = tk.Text(form, width=40, height=4)

        ttk.Entry(form, textvariable=self.safety_date_var, width=20).grid(row=0, column=1, pady=2)
        # Staff drop-down for safety
        self.safety_staff_combo = ttk.Combobox(form, textvariable=self.safety_staff_var, width=22)
        self.safety_staff_combo.grid(row=1, column=1, pady=2)
        self.safety_desc_text.grid(row=2, column=1, pady=2)

        ttk.Button(form, text="Submit", command=self.add_safety_concern).grid(row=3, column=0, columnspan=2, pady=5)

        # Table for safety concerns
        table_frame = ttk.Frame(self.safety_frame)
        table_frame.grid(row=0, column=1, sticky='nsew', padx=10, pady=10)
        self.safety_tree = ttk.Treeview(table_frame, columns=("ID", "Date", "Staff", "Description", "Status"), show='headings')
        for col, width in zip(("ID", "Date", "Staff", "Description", "Status"), (40, 100, 120, 300, 80)):
            self.safety_tree.heading(col, text=col)
            self.safety_tree.column(col, width=width)
        self.safety_tree.pack(fill='both', expand=True)
        self.safety_tree.bind("<Double-1>", self.on_safety_select)

        actions = ttk.Frame(self.safety_frame)
        actions.grid(row=1, column=1, sticky='w', padx=10, pady=5)
        resolve_btn = ttk.Button(actions, text="Mark Resolved", command=self.resolve_safety)
        resolve_btn.grid(row=0, column=0, padx=5)
        report_btn = ttk.Button(actions, text="Export Report", command=self.export_safety_report)
        report_btn.grid(row=0, column=1, padx=5)

        # Populate staff list for safety
        self.refresh_safety_staff_list()
        self.refresh_safety_table()

    def refresh_safety_staff_list(self) -> None:
        c = self.conn.cursor()
        c.execute("SELECT id, name FROM staff")
        staff = c.fetchall()
        options = ["None"] + [f"{sid}:{name}" for sid, name in staff]
        self.safety_staff_combo['values'] = options

    def add_safety_concern(self) -> None:
        """Insert a new safety concern into the database."""
        date_str = self.safety_date_var.get().strip()
        staff_selection = self.safety_staff_var.get().strip()
        description = self.safety_desc_text.get("1.0", "end").strip()
        if not date_str or not description:
            messagebox.showerror("Error", "Date and description are required.")
            return
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Error", "Date must be in YYYY-MM-DD format.")
            return
        staff_id = None
        if staff_selection and staff_selection != "None":
            try:
                staff_id = int(staff_selection.split(":")[0])
            except Exception:
                messagebox.showerror("Error", "Invalid staff selection.")
                return
        c = self.conn.cursor()
        c.execute(
            "INSERT INTO safety (reported_date, staff_id, description) VALUES (?, ?, ?)",
            (date_str, staff_id, description),
        )
        self.conn.commit()
        self.safety_desc_text.delete("1.0", "end")
        self.refresh_safety_table()
        self.refresh_dashboard()
        messagebox.showinfo("Success", "Safety concern recorded.")

    def refresh_safety_table(self) -> None:
        for item in self.safety_tree.get_children():
            self.safety_tree.delete(item)
        c = self.conn.cursor()
        c.execute("SELECT id, reported_date, staff_id, description, status FROM safety ORDER BY reported_date DESC")
        rows = c.fetchall()
        for row in rows:
            sid, date_str, staff_id, desc, status = row
            staff_name = ""
            if staff_id:
                c.execute("SELECT name FROM staff WHERE id=?", (staff_id,))
                result = c.fetchone()
                staff_name = result[0] if result else ""
            self.safety_tree.insert("", "end", values=(sid, date_str, staff_name, desc, status))

    def on_safety_select(self, event) -> None:
        """Toggle status between Open and Resolved on double click."""
        item_id = self.safety_tree.focus()
        if not item_id:
            return
        values = self.safety_tree.item(item_id, 'values')
        if not values:
            return
        sid = int(values[0])
        current_status = values[4]
        new_status = "Resolved" if current_status == "Open" else "Open"
        c = self.conn.cursor()
        c.execute("UPDATE safety SET status=? WHERE id=?", (new_status, sid))
        self.conn.commit()
        self.refresh_safety_table()
        self.refresh_dashboard()

    def resolve_safety(self) -> None:
        """Mark the selected safety concern as resolved."""
        item_id = self.safety_tree.focus()
        if not item_id:
            messagebox.showwarning("Warning", "No safety record selected.")
            return
        values = self.safety_tree.item(item_id, 'values')
        sid = int(values[0])
        c = self.conn.cursor()
        c.execute("UPDATE safety SET status='Resolved' WHERE id=?", (sid,))
        self.conn.commit()
        self.refresh_safety_table()
        self.refresh_dashboard()
        messagebox.showinfo("Updated", "Safety concern resolved.")

    def export_safety_report(self) -> None:
        """Export safety concerns to a CSV file."""
        import csv
        filename = f"safety_report_{date.today().isoformat()}.csv"
        c = self.conn.cursor()
        c.execute("SELECT s.id, s.reported_date, st.name, s.description, s.status FROM safety s LEFT JOIN staff st ON s.staff_id = st.id")
        rows = c.fetchall()
        if not rows:
            messagebox.showinfo("No data", "There are no safety concerns to export.")
            return
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["ID", "Date", "Staff", "Description", "Status"])
                writer.writerows(rows)
            messagebox.showinfo("Exported", f"Safety report exported to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not export report: {e}")

    # Inventory tab -------------------------------------------------------
    def create_inventory_tab(self) -> None:
        """Create the inventory management tab."""
        self.inventory_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.inventory_frame, text="Inventory")

        form = ttk.LabelFrame(self.inventory_frame, text="Add / Update Inventory Item")
        form.grid(row=0, column=0, sticky='nw', padx=10, pady=10)
        ttk.Label(form, text="Item Name:").grid(row=0, column=0, sticky='e')
        ttk.Label(form, text="Quantity:").grid(row=1, column=0, sticky='e')
        ttk.Label(form, text="Minimum Quantity:").grid(row=2, column=0, sticky='e')
        ttk.Label(form, text="Expiry (YYYY-MM-DD, optional):").grid(row=3, column=0, sticky='e')

        self.inv_name_var = tk.StringVar()
        self.inv_qty_var = tk.StringVar()
        self.inv_min_var = tk.StringVar()
        self.inv_expiry_var = tk.StringVar()

        ttk.Entry(form, textvariable=self.inv_name_var, width=30).grid(row=0, column=1, pady=2)
        ttk.Entry(form, textvariable=self.inv_qty_var, width=30).grid(row=1, column=1, pady=2)
        ttk.Entry(form, textvariable=self.inv_min_var, width=30).grid(row=2, column=1, pady=2)
        ttk.Entry(form, textvariable=self.inv_expiry_var, width=30).grid(row=3, column=1, pady=2)

        ttk.Button(form, text="Save Item", command=self.save_inventory_item).grid(row=4, column=0, columnspan=2, pady=5)

        # Table for inventory
        table_frame = ttk.Frame(self.inventory_frame)
        table_frame.grid(row=0, column=1, sticky='nsew', padx=10, pady=10)
        self.inventory_tree = ttk.Treeview(table_frame, columns=("ID", "Name", "Qty", "Min", "Expiry", "Status"), show='headings')
        for col, width in zip(("ID", "Name", "Qty", "Min", "Expiry", "Status"), (40, 160, 60, 60, 100, 100)):
            self.inventory_tree.heading(col, text=col)
            self.inventory_tree.column(col, width=width)
        self.inventory_tree.pack(fill='both', expand=True)
        self.inventory_tree.bind("<Double-1>", self.on_inventory_select)

        actions = ttk.Frame(self.inventory_frame)
        actions.grid(row=1, column=1, sticky='w', padx=10, pady=5)
        del_btn = ttk.Button(actions, text="Delete Selected", command=self.delete_inventory_item)
        del_btn.grid(row=0, column=0, padx=5)

        self.refresh_inventory_table()

    def save_inventory_item(self) -> None:
        """Insert or update an inventory record."""
        name = self.inv_name_var.get().strip()
        qty_str = self.inv_qty_var.get().strip()
        min_str = self.inv_min_var.get().strip()
        expiry_str = self.inv_expiry_var.get().strip()
        if not name or not qty_str or not min_str:
            messagebox.showerror("Error", "Name, quantity and minimum quantity are required.")
            return
        try:
            qty = int(qty_str)
            min_qty = int(min_str)
        except ValueError:
            messagebox.showerror("Error", "Quantity and minimum quantity must be integers.")
            return
        if expiry_str:
            try:
                datetime.strptime(expiry_str, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Error", "Expiry must be in YYYY-MM-DD format.")
                return
        c = self.conn.cursor()
        # Determine if updating existing item (by name)
        c.execute("SELECT id FROM inventory WHERE item_name=?", (name,))
        row = c.fetchone()
        if row:
            inv_id = row[0]
            c.execute(
                "UPDATE inventory SET quantity=?, min_quantity=?, expiry=? WHERE id=?",
                (qty, min_qty, expiry_str or None, inv_id),
            )
        else:
            c.execute(
                "INSERT INTO inventory (item_name, quantity, min_quantity, expiry) VALUES (?, ?, ?, ?)",
                (name, qty, min_qty, expiry_str or None),
            )
        self.conn.commit()
        self.refresh_inventory_table()
        self.refresh_dashboard()
        self.inv_name_var.set("")
        self.inv_qty_var.set("")
        self.inv_min_var.set("")
        self.inv_expiry_var.set("")
        messagebox.showinfo("Success", "Inventory item saved.")

    def refresh_inventory_table(self) -> None:
        for item in self.inventory_tree.get_children():
            self.inventory_tree.delete(item)
        c = self.conn.cursor()
        c.execute("SELECT id, item_name, quantity, min_quantity, expiry FROM inventory")
        rows = c.fetchall()
        today = date.today()
        for row in rows:
            inv_id, name, qty, min_qty, expiry = row
            status = "OK"
            if qty <= min_qty:
                status = "Low Stock"
            if expiry:
                try:
                    exp_date = datetime.strptime(expiry, "%Y-%m-%d").date()
                    if exp_date < today:
                        status = "Expired"
                except Exception:
                    status = "Unknown"
            self.inventory_tree.insert("", "end", values=(inv_id, name, qty, min_qty, expiry or '', status))

    def on_inventory_select(self, event) -> None:
        """Load selected inventory item into the form for editing."""
        item_id = self.inventory_tree.focus()
        if not item_id:
            return
        values = self.inventory_tree.item(item_id, 'values')
        if not values:
            return
        inv_id, name, qty, min_qty, expiry, status = values
        self.inv_name_var.set(name)
        self.inv_qty_var.set(str(qty))
        self.inv_min_var.set(str(min_qty))
        self.inv_expiry_var.set(expiry)

    def delete_inventory_item(self) -> None:
        item_id = self.inventory_tree.focus()
        if not item_id:
            messagebox.showwarning("Warning", "No inventory item selected.")
            return
        values = self.inventory_tree.item(item_id, 'values')
        inv_id = int(values[0])
        confirm = messagebox.askyesno("Confirm", "Are you sure you want to delete this item?")
        if confirm:
            c = self.conn.cursor()
            c.execute("DELETE FROM inventory WHERE id=?", (inv_id,))
            self.conn.commit()
            self.refresh_inventory_table()
            self.refresh_dashboard()
            messagebox.showinfo("Deleted", "Inventory item deleted.")

    # Training tab --------------------------------------------------------
    def create_training_tab(self) -> None:
        """Create the training and certification tracking tab."""
        self.training_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.training_frame, text="Training & Certification")

        # Table showing staff and certification status
        table_frame = ttk.Frame(self.training_frame)
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)
        self.training_tree = ttk.Treeview(table_frame, columns=("ID", "Name", "Certification", "Expiry", "Days", "Status"), show='headings')
        for col, width in zip(("ID", "Name", "Certification", "Expiry", "Days", "Status"), (40, 150, 120, 100, 60, 100)):
            self.training_tree.heading(col, text=col)
            self.training_tree.column(col, width=width)
        self.training_tree.pack(fill='both', expand=True)

        actions = ttk.Frame(self.training_frame)
        actions.pack(anchor='w', padx=10, pady=5)
        refresh_btn = ttk.Button(actions, text="Refresh", command=self.refresh_training_table)
        refresh_btn.grid(row=0, column=0, padx=5)
        notify_btn = ttk.Button(actions, text="Notify Due/Expired", command=self.notify_due_certifications)
        notify_btn.grid(row=0, column=1, padx=5)

        self.refresh_training_table()

    def refresh_training_table(self) -> None:
        """Populate the training table with certification statuses."""
        for item in self.training_tree.get_children():
            self.training_tree.delete(item)
        c = self.conn.cursor()
        c.execute("SELECT id, name, certification_name, certification_expiry FROM staff")
        rows = c.fetchall()
        today = date.today()
        for row in rows:
            staff_id, name, cert_name, cert_expiry = row
            if cert_expiry:
                try:
                    exp_date = datetime.strptime(cert_expiry, "%Y-%m-%d").date()
                    days_remaining = (exp_date - today).days
                    if days_remaining < 0:
                        status = "Expired"
                    elif days_remaining <= 60:
                        status = "Due soon"
                    else:
                        status = "Valid"
                except Exception:
                    days_remaining = ''
                    status = "Unknown"
            else:
                exp_date = None
                days_remaining = ''
                status = "N/A"
            self.training_tree.insert(
                "", "end",
                values=(staff_id, name, cert_name or '', cert_expiry or '', days_remaining, status)
            )

    # Feedback tab --------------------------------------------------------
    def create_feedback_tab(self) -> None:
        """Create the feedback and survey tab."""
        self.feedback_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.feedback_frame, text="Feedback & Survey")

        form = ttk.LabelFrame(self.feedback_frame, text="Submit Feedback")
        form.grid(row=0, column=0, sticky='nw', padx=10, pady=10)
        ttk.Label(form, text="Date (YYYY-MM-DD):").grid(row=0, column=0, sticky='e')
        ttk.Label(form, text="Staff (optional):").grid(row=1, column=0, sticky='e')
        ttk.Label(form, text="Topic:").grid(row=2, column=0, sticky='e')
        ttk.Label(form, text="Rating (1-5):").grid(row=3, column=0, sticky='e')
        ttk.Label(form, text="Comments:").grid(row=4, column=0, sticky='ne')

        self.feedback_date_var = tk.StringVar(value=date.today().isoformat())
        self.feedback_staff_var = tk.StringVar()
        self.feedback_topic_var = tk.StringVar()
        self.feedback_rating_var = tk.StringVar()
        self.feedback_comments = tk.Text(form, width=40, height=4)

        ttk.Entry(form, textvariable=self.feedback_date_var, width=20).grid(row=0, column=1, pady=2)
        self.feedback_staff_combo = ttk.Combobox(form, textvariable=self.feedback_staff_var, width=22)
        self.feedback_staff_combo.grid(row=1, column=1, pady=2)
        ttk.Entry(form, textvariable=self.feedback_topic_var, width=22).grid(row=2, column=1, pady=2)
        ttk.Combobox(form, textvariable=self.feedback_rating_var, values=("1", "2", "3", "4", "5"), width=20).grid(row=3, column=1, pady=2)
        self.feedback_comments.grid(row=4, column=1, pady=2)
        ttk.Button(form, text="Submit", command=self.add_feedback).grid(row=5, column=0, columnspan=2, pady=5)

        # Table for feedback
        table_frame = ttk.Frame(self.feedback_frame)
        table_frame.grid(row=0, column=1, sticky='nsew', padx=10, pady=10)
        self.feedback_tree = ttk.Treeview(table_frame, columns=("ID", "Date", "Staff", "Topic", "Rating", "Comments"), show='headings')
        for col, width in zip(("ID", "Date", "Staff", "Topic", "Rating", "Comments"), (40, 100, 120, 120, 60, 200)):
            self.feedback_tree.heading(col, text=col)
            self.feedback_tree.column(col, width=width)
        self.feedback_tree.pack(fill='both', expand=True)

        self.refresh_feedback_staff_list()
        self.refresh_feedback_table()

    def refresh_feedback_staff_list(self) -> None:
        c = self.conn.cursor()
        c.execute("SELECT id, name FROM staff")
        staff = c.fetchall()
        self.feedback_staff_combo['values'] = ["None"] + [f"{sid}:{name}" for sid, name in staff]

    def add_feedback(self) -> None:
        date_str = self.feedback_date_var.get().strip()
        staff_sel = self.feedback_staff_var.get().strip()
        topic = self.feedback_topic_var.get().strip()
        rating_str = self.feedback_rating_var.get().strip()
        comments = self.feedback_comments.get("1.0", "end").strip()
        if not date_str or not topic or not rating_str:
            messagebox.showerror("Error", "Date, topic and rating are required.")
            return
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Error", "Date must be in YYYY-MM-DD format.")
            return
        try:
            rating = int(rating_str)
            if rating < 1 or rating > 5:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Rating must be an integer between 1 and 5.")
            return
        staff_id = None
        if staff_sel and staff_sel != "None":
            try:
                staff_id = int(staff_sel.split(":")[0])
            except Exception:
                messagebox.showerror("Error", "Invalid staff selection.")
                return
        c = self.conn.cursor()
        c.execute(
            "INSERT INTO feedback (feedback_date, staff_id, topic, rating, comments) VALUES (?, ?, ?, ?, ?)",
            (date_str, staff_id, topic, rating, comments),
        )
        self.conn.commit()
        self.feedback_topic_var.set("")
        self.feedback_rating_var.set("")
        self.feedback_comments.delete("1.0", "end")
        self.refresh_feedback_table()
        self.refresh_dashboard()
        messagebox.showinfo("Success", "Feedback submitted.")

    def refresh_feedback_table(self) -> None:
        for item in self.feedback_tree.get_children():
            self.feedback_tree.delete(item)
        c = self.conn.cursor()
        c.execute("SELECT f.id, f.feedback_date, f.staff_id, f.topic, f.rating, f.comments FROM feedback f ORDER BY f.feedback_date DESC")
        rows = c.fetchall()
        for row in rows:
            fid, fdate, staff_id, topic, rating, comments = row
            staff_name = ""
            if staff_id:
                c.execute("SELECT name FROM staff WHERE id=?", (staff_id,))
                result = c.fetchone()
                staff_name = result[0] if result else ""
            self.feedback_tree.insert("", "end", values=(fid, fdate, staff_name, topic, rating, comments))

    # Reports tab --------------------------------------------------------
    def create_reports_tab(self) -> None:
        """Create the reports tab for summarising data."""
        self.reports_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.reports_frame, text="Reports")
        info_label = ttk.Label(
            self.reports_frame,
            text=(
                "This tab provides quick summaries of data across the system.\n"
                "Use the buttons below to view counts and export CSV reports."
            ),
            wraplength=500
        )
        info_label.pack(anchor='w', padx=10, pady=10)

        buttons_frame = ttk.Frame(self.reports_frame)
        buttons_frame.pack(anchor='w', padx=10, pady=10)
        ttk.Button(buttons_frame, text="Export Staff List", command=self.export_staff_report).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Export Certification Due", command=self.export_due_cert_report).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Export Inventory", command=self.export_inventory_report).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Export Feedback", command=self.export_feedback_report).pack(side='left', padx=5)

    def export_staff_report(self) -> None:
        import csv
        filename = f"staff_list_{date.today().isoformat()}.csv"
        c = self.conn.cursor()
        c.execute("SELECT id, name, email, role, certification_name, certification_expiry, training_due FROM staff")
        rows = c.fetchall()
        if not rows:
            messagebox.showinfo("No data", "No staff records to export.")
            return
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["ID", "Name", "Email", "Role", "Certification", "Expiry", "Training Due"])
                writer.writerows(rows)
            messagebox.showinfo("Exported", f"Staff list exported to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export staff list: {e}")

    def export_due_cert_report(self) -> None:
        import csv
        filename = f"cert_due_{date.today().isoformat()}.csv"
        today = date.today()
        due_limit = today + timedelta(days=60)
        c = self.conn.cursor()
        c.execute(
            "SELECT id, name, email, certification_name, certification_expiry FROM staff WHERE certification_expiry IS NOT NULL AND certification_expiry <> '' AND certification_expiry <= ?",
            (due_limit.isoformat(),),
        )
        rows = c.fetchall()
        if not rows:
            messagebox.showinfo("No data", "No certifications due within 60 days.")
            return
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["ID", "Name", "Email", "Certification", "Expiry"])
                writer.writerows(rows)
            messagebox.showinfo("Exported", f"Certification due report exported to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export report: {e}")

    def export_inventory_report(self) -> None:
        import csv
        filename = f"inventory_{date.today().isoformat()}.csv"
        c = self.conn.cursor()
        c.execute("SELECT id, item_name, quantity, min_quantity, expiry FROM inventory")
        rows = c.fetchall()
        if not rows:
            messagebox.showinfo("No data", "No inventory records to export.")
            return
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["ID", "Item Name", "Quantity", "Min Quantity", "Expiry"])
                writer.writerows(rows)
            messagebox.showinfo("Exported", f"Inventory report exported to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export inventory report: {e}")

    def export_feedback_report(self) -> None:
        import csv
        filename = f"feedback_{date.today().isoformat()}.csv"
        c = self.conn.cursor()
        c.execute("SELECT id, feedback_date, staff_id, topic, rating, comments FROM feedback")
        rows = c.fetchall()
        if not rows:
            messagebox.showinfo("No data", "No feedback records to export.")
            return
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["ID", "Date", "Staff ID", "Topic", "Rating", "Comments"])
                writer.writerows(rows)
            messagebox.showinfo("Exported", f"Feedback report exported to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export feedback report: {e}")


def main() -> None:
    root = tk.Tk()
    app = HealthcareApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()