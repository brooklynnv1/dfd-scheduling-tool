import os
from datetime import date, timedelta
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Scheduling Tool", layout="wide")

EMPLOYEES_FILE = "employees.csv"
BIWEEKLY_SCHEDULE_FILE = "biweekly_schedule.csv"
REQUESTS_FILE = "ot_requests.csv"
CANDIDATES_FILE = "ot_candidates.csv"
USERS_FILE = "users.csv"


def load_users():
    if os.path.exists(USERS_FILE):
        users = pd.read_csv(USERS_FILE, dtype=str)
    else:
        users = pd.DataFrame(
            [{"Username": "admin", "Password": "admin123", "Role": "Supervisor", "Employee ID": ""}]
        )
        users.to_csv(USERS_FILE, index=False)

    for col in ["Username", "Password", "Role", "Employee ID"]:
        if col not in users.columns:
            users[col] = ""

    return users.fillna("")


def save_users(users):
    users.to_csv(USERS_FILE, index=False)


def create_user(username, password, role, employee_id=""):
    users = load_users()
    username = str(username).strip().lower()

    if username == "" or password == "":
        return False, "Username and password are required."

    if username in users["Username"].astype(str).str.lower().tolist():
        return False, "That username already exists."

    new_user = pd.DataFrame([{
        "Username": username,
        "Password": password,
        "Role": role,
        "Employee ID": str(employee_id).strip(),
    }])

    users = pd.concat([users, new_user], ignore_index=True)
    save_users(users)

    return True, "User created."


def login_user(username, password):
    users = load_users()

    match = users[
        (users["Username"].astype(str).str.lower() == str(username).strip().lower())
        & (users["Password"].astype(str) == str(password))
    ]

    if match.empty:
        return None, None

    return match.iloc[0]["Role"], match.iloc[0]["Employee ID"]


def change_own_password(username, current_password, new_password):
    users = load_users()
    mask = users["Username"].astype(str).str.lower() == str(username).lower()

    if users[mask].empty:
        return False, "User not found."

    stored_password = users.loc[mask, "Password"].iloc[0]

    if str(stored_password) != str(current_password):
        return False, "Current password is incorrect."

    users.loc[mask, "Password"] = new_password
    save_users(users)

    return True, "Password changed."


def reset_user_password(username, new_password):
    users = load_users()
    mask = users["Username"].astype(str).str.lower() == str(username).lower()

    if users[mask].empty:
        return False, "User not found."

    users.loc[mask, "Password"] = new_password
    save_users(users)

    return True, "Password reset."


if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.role = None
    st.session_state.employee_id = None


if not st.session_state.logged_in:
    st.title("Detroit Fire Department Scheduling Tool")
    st.caption("Login required.")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        role, employee_id = login_user(username, password)

        if role:
            st.session_state.logged_in = True
            st.session_state.username = username.strip().lower()
            st.session_state.role = role
            st.session_state.employee_id = employee_id
            st.rerun()
        else:
            st.error("Invalid username or password.")

    st.stop()


st.title("Detroit Fire Department Scheduling Tool")
st.caption("Assign overtime based on classification, seniority, schedule rules, and response status.")
st.write(f"Logged in as: **{st.session_state.username}** ({st.session_state.role})")


employees_base = pd.read_csv(EMPLOYEES_FILE)


def load_biweekly_schedule():
    if os.path.exists(BIWEEKLY_SCHEDULE_FILE):
        schedule = pd.read_csv(BIWEEKLY_SCHEDULE_FILE, dtype=str)
    else:
        schedule = pd.DataFrame(columns=["Date", "Day of Week", "D1", "N1", "D2", "N2"])

    for col in ["Date", "Day of Week", "D1", "N1", "D2", "N2"]:
        if col not in schedule.columns:
            schedule[col] = ""

    schedule = schedule.fillna("")

    schedule["Day of Week"] = pd.to_datetime(
        schedule["Date"], errors="coerce"
    ).dt.day_name()

    schedule["Day of Week"] = schedule["Day of Week"].fillna("")

    return schedule[["Date", "Day of Week", "D1", "N1", "D2", "N2"]]


def generate_14_day_schedule(start_date):
    rows = []

    for i in range(14):
        current_date = start_date + timedelta(days=i)

        rows.append({
            "Date": current_date.strftime("%m/%d/%Y"),
            "Day of Week": current_date.strftime("%A"),
            "D1": "",
            "N1": "",
            "D2": "",
            "N2": "",
        })

    return pd.DataFrame(rows)


def parse_employee_ids(cell_value):
    if pd.isna(cell_value) or str(cell_value).strip() == "":
        return []

    employee_ids = []

    for item in str(cell_value).replace(";", ",").split(","):
        item = item.strip()

        if item.isdigit():
            employee_ids.append(int(item))

    return employee_ids


def get_eligible_crews(day_of_week, ot_shift):
    if ot_shift == "D1":
        if day_of_week == "Sunday":
            return ["D2"]
        return ["D2", "N2"]

    if ot_shift == "N1":
        return ["D2", "N2"]

    if ot_shift == "D2":
        if day_of_week == "Wednesday":
            return ["D1"]
        return ["D1", "N1"]

    if ot_shift == "N2":
        if day_of_week == "Saturday":
            return ["N1"]
        return ["D1", "N1"]

    return []


def load_requests():
    if os.path.exists(REQUESTS_FILE):
        requests = pd.read_csv(REQUESTS_FILE)

        if "Date Created" in requests.columns:
            requests = requests.drop(columns=["Date Created"])

        return requests

    return pd.DataFrame(
        columns=[
            "Request ID",
            "OT Date",
            "Day of Week",
            "OT Shift",
            "Classification Needed",
            "Eligible Crews",
            "Assigned Person",
            "OT Filled?",
        ]
    )


def load_candidates():
    if os.path.exists(CANDIDATES_FILE):
        candidates = pd.read_csv(CANDIDATES_FILE)

        for col in ["OT Date", "OT Shift", "Classification Needed"]:
            if col in candidates.columns:
                candidates = candidates.drop(columns=[col])

        if "Employee ID" not in candidates.columns:
            candidates["Employee ID"] = ""

        return candidates

    return pd.DataFrame(
        columns=[
            "Request ID",
            "Employee ID",
            "Candidate",
            "Seniority Rank",
            "Status",
            "Call Order",
        ]
    )


def get_next_request_id():
    requests = load_requests()

    if requests.empty:
        return "OT-001"

    nums = (
        requests["Request ID"]
        .astype(str)
        .str.replace("OT-", "", regex=False)
        .astype(int)
    )

    return f"OT-{nums.max() + 1:03d}"


def generate_candidates(ot_date, classification, eligible_crews):
    schedule = load_biweekly_schedule()

    request_date = pd.to_datetime(ot_date).strftime("%Y-%m-%d")

    schedule["Date Match"] = pd.to_datetime(
        schedule["Date"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")

    schedule_row = schedule[schedule["Date Match"] == request_date]

    if schedule_row.empty:
        return pd.DataFrame(
            columns=["Employee ID", "Last Name", "Seniority Rank", "Status", "Call Order"]
        )

    schedule_row = schedule_row.iloc[0]

    eligible_employee_ids = []

    for crew in eligible_crews:
        if crew in schedule_row:
            eligible_employee_ids.extend(parse_employee_ids(schedule_row[crew]))

    eligible_employee_ids = list(dict.fromkeys(eligible_employee_ids))

    employees_copy = employees_base.copy()
    employees_copy["Employee ID"] = pd.to_numeric(
        employees_copy["Employee ID"], errors="coerce"
    )
    employees_copy["Seniority Rank"] = pd.to_numeric(
        employees_copy["Seniority Rank"], errors="coerce"
    )

    candidates = employees_copy[
        (employees_copy["Employee ID"].isin(eligible_employee_ids))
        & (employees_copy["Classification"] == classification)
    ].copy()

    candidates = candidates.sort_values("Seniority Rank")
    candidates["Status"] = "Pending"
    candidates["Call Order"] = range(1, len(candidates) + 1)

    return candidates[["Employee ID", "Last Name", "Seniority Rank", "Status", "Call Order"]]


def save_new_request(ot_date, ot_shift, classification):
    request_id = get_next_request_id()
    day_of_week = ot_date.strftime("%A")
    eligible_crews = get_eligible_crews(day_of_week, ot_shift)

    requests = load_requests()

    new_request = {
        "Request ID": request_id,
        "OT Date": ot_date,
        "Day of Week": day_of_week,
        "OT Shift": ot_shift,
        "Classification Needed": classification,
        "Eligible Crews": ", ".join(eligible_crews),
        "Assigned Person": "No one accepted yet",
        "OT Filled?": "No",
    }

    requests = pd.concat([requests, pd.DataFrame([new_request])], ignore_index=True)
    requests.to_csv(REQUESTS_FILE, index=False)

    candidates = generate_candidates(ot_date, classification, eligible_crews)
    candidates = candidates.rename(columns={"Last Name": "Candidate"})
    candidates.insert(0, "Request ID", request_id)

    candidate_history = load_candidates()
    candidate_history = pd.concat([candidate_history, candidates], ignore_index=True)
    candidate_history.to_csv(CANDIDATES_FILE, index=False)

    return request_id


def update_request_assignment(request_id, selected_candidates):
    accepted = selected_candidates[selected_candidates["Status"] == "Accepted"]

    if accepted.empty:
        assigned_person = "No one accepted yet"
        ot_filled = "No"
    else:
        assigned_person = accepted.sort_values("Call Order").iloc[0]["Candidate"]
        ot_filled = "Yes"

    requests = load_requests()
    requests.loc[requests["Request ID"] == request_id, "Assigned Person"] = assigned_person
    requests.loc[requests["Request ID"] == request_id, "OT Filled?"] = ot_filled
    requests.to_csv(REQUESTS_FILE, index=False)


def delete_request(request_id):
    requests = load_requests()
    candidates = load_candidates()

    requests = requests[requests["Request ID"] != request_id]
    candidates = candidates[candidates["Request ID"] != request_id]

    requests.to_csv(REQUESTS_FILE, index=False)
    candidates.to_csv(CANDIDATES_FILE, index=False)


def sort_requests(requests):
    if requests.empty:
        return requests

    requests = requests.copy()
    requests["Sort Order"] = requests["OT Filled?"].map({"No": 0, "Yes": 1})
    requests = requests.sort_values(["Sort Order", "OT Date", "Request ID"])
    return requests.drop(columns=["Sort Order"])


def show_request_metrics(requests):
    open_count = len(requests[requests["OT Filled?"] == "No"]) if not requests.empty else 0
    filled_count = len(requests[requests["OT Filled?"] == "Yes"]) if not requests.empty else 0
    total_count = len(requests)

    col1, col2, col3 = st.columns(3)
    col1.metric("Open OT Requests", open_count)
    col2.metric("Filled OT Requests", filled_count)
    col3.metric("Total Requests", total_count)


if st.session_state.role == "Supervisor":
    supervisor_tab, employee_tab, records_tab, schedule_tab, employee_management_tab, user_tab, settings_tab = st.tabs(
        [
            "Supervisor View",
            "Employee View",
            "Records",
            "Schedule Editor",
            "Employee Management",
            "User Accounts",
            "Settings",
        ]
    )
else:
    employee_tab, schedule_view_tab, settings_tab = st.tabs(
        ["Employee View", "Schedule View", "Settings"]
    )


if st.session_state.role == "Supervisor":
    with supervisor_tab:
        requests = sort_requests(load_requests())
        show_request_metrics(requests)

        st.divider()
        st.subheader("Add Available Overtime")

        with st.form("new_ot_request"):
            col1, col2, col3 = st.columns(3)

            with col1:
                ot_date = st.date_input("OT Date", value=date(2026, 9, 2))

            with col2:
                ot_shift = st.selectbox("OT Shift Request", ["D1", "D2", "N1", "N2"])

            with col3:
                classification = st.selectbox(
                    "Classification Needed",
                    ["Lieutenant", "Sergeant", "Fire Dispatcher"],
                )

            submitted = st.form_submit_button("Create OT Request")

            if submitted:
                new_id = save_new_request(ot_date, ot_shift, classification)
                st.success(f"Created {new_id}")
                st.rerun()

        requests = load_requests()

        if not requests.empty:
            st.divider()
            st.subheader("Delete Overtime")

            delete_choice = st.selectbox(
                "Delete Overtime Option",
                requests["Request ID"].tolist(),
                key="delete_request_select",
            )

            confirm_delete = st.checkbox(
                f"I confirm I want to delete {delete_choice}",
                key="confirm_delete_checkbox",
            )

            if st.button("Delete Selected Overtime"):
                if confirm_delete:
                    delete_request(delete_choice)
                    st.success(f"{delete_choice} deleted.")
                    st.rerun()
                else:
                    st.warning("Please check the confirmation box before deleting.")

        st.divider()
        st.subheader("Current Overtime Requests")

        requests = sort_requests(load_requests())

        if requests.empty:
            st.info("No OT requests have been created yet.")
        else:
            st.dataframe(requests, use_container_width=True)


with employee_tab:
    requests = sort_requests(load_requests())

    if st.session_state.role == "Supervisor":
        show_request_metrics(requests)

    st.divider()
    st.subheader("Respond to an OT Request")

    if requests.empty:
        st.info("No OT requests are available yet.")
    else:
        st.dataframe(requests, use_container_width=True)

        selected_request = st.selectbox(
            "Select OT Request",
            requests["Request ID"].tolist(),
            key="respond_request_select",
        )

        candidates = load_candidates()
        selected_candidates = candidates[
            candidates["Request ID"] == selected_request
        ].copy()

        if selected_candidates.empty:
            st.warning("No candidates found for this request.")
        else:
            selected_candidates = selected_candidates.sort_values("Call Order")

            request_row = requests[requests["Request ID"] == selected_request].iloc[0]
            already_filled = request_row["OT Filled?"] == "Yes"

            pending_candidates = selected_candidates[
                selected_candidates["Status"] == "Pending"
            ]

            st.write("**Eligible for this OT**")
            eligible_names = selected_candidates["Candidate"].tolist()
            st.info(", ".join(eligible_names))

            st.write("**Call List**")

            if already_filled:
                st.success(
                    f"This overtime is already filled by {request_row['Assigned Person']}."
                )
            elif pending_candidates.empty:
                st.warning("No pending candidates remain for this request.")
            else:
                next_row = pending_candidates.iloc[0]
                next_candidate_display = str(next_row["Candidate"]).strip().upper()
                st.info(f"Next person allowed to respond: {next_candidate_display}")

            st.dataframe(selected_candidates, use_container_width=True)

            if already_filled:
                if st.button("Clear Acceptance / Reopen Request"):
                    all_candidates = load_candidates()

                    mask = (
                        (all_candidates["Request ID"] == selected_request)
                        & (all_candidates["Status"] == "Accepted")
                    )

                    all_candidates.loc[mask, "Status"] = "Pending"
                    all_candidates.to_csv(CANDIDATES_FILE, index=False)

                    updated_candidates = all_candidates[
                        all_candidates["Request ID"] == selected_request
                    ].copy()

                    update_request_assignment(selected_request, updated_candidates)

                    st.success(f"{selected_request} reopened.")
                    st.rerun()

            elif not pending_candidates.empty:
                next_row = pending_candidates.iloc[0]
                next_candidate = str(next_row["Candidate"]).strip().lower()
                next_candidate_display = next_candidate.upper()
                logged_in_username = str(st.session_state.username).strip().lower()

                if (
                    st.session_state.role == "Employee"
                    and logged_in_username != next_candidate
                ):
                    st.warning(
                        f"It is currently {next_candidate_display}'s turn to respond. "
                        "You cannot respond to this overtime request yet."
                    )
                else:
                    response = st.selectbox(
                        f"{next_candidate_display}'s response",
                        ["Pending", "Accepted", "Declined"],
                        key=f"response_{selected_request}_{next_candidate_display}",
                    )

                    if st.button("Save Response"):
                        all_candidates = load_candidates()

                        mask = (
                            (all_candidates["Request ID"] == selected_request)
                            & (
                                all_candidates["Candidate"]
                                .astype(str)
                                .str.lower()
                                == next_candidate
                            )
                        )

                        all_candidates.loc[mask, "Status"] = response
                        all_candidates.to_csv(CANDIDATES_FILE, index=False)

                        updated_candidates = all_candidates[
                            all_candidates["Request ID"] == selected_request
                        ].copy()

                        update_request_assignment(selected_request, updated_candidates)

                        st.success(f"Response saved for {next_candidate_display}")
                        st.rerun()


if st.session_state.role != "Supervisor":
    with schedule_view_tab:
        st.subheader("Schedule View")

        schedule_view = load_biweekly_schedule()

        if schedule_view.empty:
            st.info("No schedule has been entered yet.")
        else:
            st.dataframe(schedule_view, use_container_width=True)

        st.divider()

        st.subheader("Employee ID Reference")

        st.dataframe(
            employees_base[["Employee ID", "Last Name", "Classification"]],
            use_container_width=True,
        )


if st.session_state.role == "Supervisor":
    with records_tab:
        requests = sort_requests(load_requests())
        show_request_metrics(requests)

        st.divider()
        st.subheader("Overtime Request Records")

        if requests.empty:
            st.info("No OT request records yet.")
        else:
            st.dataframe(requests, use_container_width=True)

        st.divider()
        st.subheader("Candidate Call History")

        candidates = load_candidates()

        if candidates.empty:
            st.info("No candidate call history yet.")
        else:
            st.dataframe(candidates, use_container_width=True)

    with schedule_tab:
        st.subheader("Schedule Editor")

        st.info(
            "Generate the next 14 days, then type employee numbers under each shift, separated by commas. "
        )

        col1, col2 = st.columns([1, 2])

        with col1:
            schedule_start_date = st.date_input(
                "Start Date for 14-Day Schedule",
                value=date.today(),
                key="schedule_start_date",
            )

        with col2:
            st.write("")
            st.write("")
            if st.button("Generate Next 14 Days"):
                generated_schedule = generate_14_day_schedule(schedule_start_date)
                generated_schedule.to_csv(BIWEEKLY_SCHEDULE_FILE, index=False)
                st.success("Generated next 14 days.")
                st.rerun()

        biweekly_schedule = load_biweekly_schedule()

        biweekly_schedule_editor = st.data_editor(
            biweekly_schedule,
            column_config={
                "Date": st.column_config.TextColumn("Date"),
                "D1": st.column_config.TextColumn("D1"),
                "N1": st.column_config.TextColumn("N1"),
                "D2": st.column_config.TextColumn("D2"),
                "N2": st.column_config.TextColumn("N2"),
            },
            disabled=["Day of Week"],
            num_rows="dynamic",
            use_container_width=True,
        )

        if st.button("Save Schedule"):
            biweekly_schedule_editor = biweekly_schedule_editor.fillna("")

            biweekly_schedule_editor["Day of Week"] = pd.to_datetime(
                biweekly_schedule_editor["Date"], errors="coerce"
            ).dt.day_name()

            biweekly_schedule_editor["Day of Week"] = biweekly_schedule_editor[
                "Day of Week"
            ].fillna("")

            biweekly_schedule_editor.to_csv(BIWEEKLY_SCHEDULE_FILE, index=False)

            st.success("Schedule saved.")
            st.rerun()

    with employee_management_tab:
        st.subheader("Employee Management")

        search_name = st.text_input("Search Employee Name")

        filtered_employees = employees_base.copy()

        if search_name:
            filtered_employees = filtered_employees[
                filtered_employees["Last Name"].str.contains(
                    search_name, case=False, na=False
                )
            ]

        employee_editor = st.data_editor(
            filtered_employees,
            num_rows="dynamic",
            use_container_width=True,
        )

        if st.button("Save Employee Seniority List"):
            if search_name:
                updated_employees = employees_base.copy()

                for _, row in employee_editor.iterrows():
                    employee_id = row["Employee ID"]
                    mask = updated_employees["Employee ID"] == employee_id

                    for col in updated_employees.columns:
                        updated_employees.loc[mask, col] = row[col]

                updated_employees.to_csv(EMPLOYEES_FILE, index=False)
            else:
                employee_editor.to_csv(EMPLOYEES_FILE, index=False)

            st.success("Employee seniority list saved.")
            st.rerun()

    with user_tab:
        st.subheader("Add New User / Employee")

        with st.form("add_user_employee_form"):
            account_type = st.selectbox(
                "Account Type",
                ["Employee", "Supervisor"],
            )

            new_password = st.text_input("Temporary Password", type="password")

            if account_type == "Employee":
                new_employee_id = st.number_input("Employee ID", min_value=1, step=1)
                new_last_name = st.text_input("Last Name").upper()
                new_username = new_last_name.lower()
                new_classification = st.selectbox(
                    "Classification",
                    ["Lieutenant", "Sergeant", "Fire Dispatcher"],
                )

                if new_last_name:
                    st.info(f"Username will be: {new_username}")

            else:
                new_username = st.text_input("Supervisor Username").lower()
                new_employee_id = ""

            add_submitted = st.form_submit_button("Add User")

            if add_submitted:
                if account_type == "Employee":
                    employee_id_int = int(new_employee_id)

                    if new_last_name.strip() == "":
                        st.warning("Please enter the employee last name.")
                    else:
                        if employee_id_int not in employees_base["Employee ID"].tolist():
                            new_employee = pd.DataFrame(
                                [{
                                    "Employee ID": employee_id_int,
                                    "Last Name": new_last_name,
                                    "Classification": new_classification,
                                    "Seniority Rank": "",
                                }]
                            )

                            employees_base = pd.concat(
                                [employees_base, new_employee],
                                ignore_index=True,
                            )

                            employees_base.to_csv(EMPLOYEES_FILE, index=False)

                        created, message = create_user(
                            username=new_username,
                            password=new_password,
                            role="Employee",
                            employee_id=employee_id_int,
                        )

                        if created:
                            st.success(f"Employee account added. Username: {new_username}")
                            st.rerun()
                        else:
                            st.error(message)

                else:
                    created, message = create_user(
                        username=new_username,
                        password=new_password,
                        role="Supervisor",
                        employee_id="",
                    )

                    if created:
                        st.success(f"Supervisor account added. Username: {new_username}")
                        st.rerun()
                    else:
                        st.error(message)

        st.divider()
        st.subheader("Reset Employee Password")

        users = load_users()

        employee_users = users[users["Role"] == "Employee"].copy()

        if employee_users.empty:
            st.info("No employee accounts found.")
        else:
            selected_user = st.selectbox(
                "Select Employee",
                employee_users["Username"].tolist(),
            )

            reset_password_value = st.text_input("New Temporary Password", type="password")

            if st.button("Reset Employee Password"):
                if not reset_password_value:
                    st.warning("Please enter a new password.")
                else:
                    reset, message = reset_user_password(selected_user, reset_password_value)

                    if reset:
                        st.success(message)
                    else:
                        st.error(message)


with settings_tab:
    st.subheader("Settings")

    st.write("**Account Information**")
    st.write(f"Username: {st.session_state.username}")
    st.write(f"Role: {st.session_state.role}")

    st.divider()
    st.subheader("Change Password")

    current_password = st.text_input(
        "Current Password",
        type="password",
        key="current_pw",
    )

    new_password = st.text_input(
        "New Password",
        type="password",
        key="new_pw",
    )

    confirm_new_password = st.text_input(
        "Confirm New Password",
        type="password",
        key="confirm_pw",
    )

    if st.button("Update Password"):
        if not current_password or not new_password:
            st.warning("Please enter your current and new password.")
        elif new_password != confirm_new_password:
            st.warning("New passwords do not match.")
        else:
            changed, message = change_own_password(
                st.session_state.username,
                current_password,
                new_password,
            )

            if changed:
                st.success(message)
            else:
                st.error(message)

    st.divider()

    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.role = None
        st.session_state.employee_id = None
        st.rerun()