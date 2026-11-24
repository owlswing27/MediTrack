
import streamlit as st
from supabase import create_client
from abc import ABC, abstractmethod
from datetime import datetime, timezone


# ==========================================
# 1. ABSTRACTION
# ==========================================

class Person(ABC):

    def __init__(self, name, age):
        self.__name = name
        self.__age = age

    @property
    def name(self):
        return self.__name

    @property
    def age(self):
        return self.__age

    @abstractmethod
    def to_database_record(self):
        pass


# ==========================================
# 2. INHERITANCE + ENCAPSULATION
# ==========================================

class Patient(Person):

    def __init__(self, patient_id, name, age,
                 blood_group, condition):

        super().__init__(name, age)

        self.__patient_id = patient_id
        self.__blood_group = blood_group
        self.__condition = condition

    @property
    def patient_id(self):
        return self.__patient_id

    @property
    def condition(self):
        return self.__condition

    def update_condition(self, new_condition):
        if not new_condition.strip():
            raise ValueError("Medical condition cannot be empty.")

        self.__condition = new_condition.strip()

    def to_database_record(self):

        return {
            "patient_id": self.__patient_id,
            "patient_type": "regular",
            "name": self.name,
            "age": self.age,
            "blood_group": self.__blood_group,
            "medical_condition": self.__condition,
            "emergency_level": None
        }


# ==========================================
# 3. INHERITANCE + POLYMORPHISM
# ==========================================

class EmergencyPatient(Patient):

    def __init__(self, patient_id, name, age,
                 blood_group, condition, emergency_level):

        super().__init__(
            patient_id, name, age, blood_group, condition
        )

        self.__emergency_level = emergency_level

    def to_database_record(self):

        record = super().to_database_record()

        record["patient_type"] = "emergency"
        record["emergency_level"] = self.__emergency_level

        return record


# ==========================================
# 4. HEALTH RECORD MANAGEMENT
# ==========================================

class HealthRecordSystem:

    def __init__(self, database_client):
        self.__database = database_client

    def add_patient(self, patient):

        return (
            self.__database
            .table("patients")
            .insert(patient.to_database_record())
            .execute()
        )

    def get_all_patients(self):

        response = (
            self.__database
            .table("patients")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )

        return [
            self._create_patient(row)
            for row in (response.data or [])
        ]

    def search_patient(self, patient_id):

        response = (
            self.__database
            .table("patients")
            .select("*")
            .eq("patient_id", patient_id)
            .limit(1)
            .execute()
        )

        if not response.data:
            return None

        return self._create_patient(response.data[0])

    def update_patient(self, patient_id, new_condition):

        response = (
            self.__database
            .table("patients")
            .update({
                "medical_condition": new_condition,
                "updated_at": datetime.now(timezone.utc).isoformat()
            })
            .eq("patient_id", patient_id)
            .select("patient_id")
            .execute()
        )

        return bool(response.data)

    @staticmethod
    def _create_patient(row):

        if row["patient_type"] == "emergency":

            return EmergencyPatient(
                row["patient_id"],
                row["name"],
                row["age"],
                row["blood_group"],
                row["medical_condition"],
                row["emergency_level"]
            )

        return Patient(
            row["patient_id"],
            row["name"],
            row["age"],
            row["blood_group"],
            row["medical_condition"]
        )


# ==========================================
# 5. STREAMLIT CONFIGURATION
# ==========================================

st.set_page_config(
    page_title="MediTrack",
    page_icon="🩺",
    layout="wide"
)


# ==========================================
# 6. SUPABASE CONNECTION
# ==========================================

def get_database_client():

    if "database_client" not in st.session_state:

        try:
            st.session_state.database_client = create_client(
                st.secrets["SUPABASE_URL"],
                st.secrets["SUPABASE_PUBLISHABLE_KEY"]
            )

        except Exception:
            st.error("Could not connect to the database.")
            st.stop()

    return st.session_state.database_client


# ==========================================
# 7. LOGIN PAGE
# ==========================================

def login_page(database):

    st.title("🩺 MediTrack")
    st.subheader("Health Record Management System")

    st.info("Please sign in to access patient records.")

    with st.form("login_form"):

        email = st.text_input("Administrator Email")

        password = st.text_input(
            "Password",
            type="password"
        )

        submitted = st.form_submit_button(
            "Sign In",
            use_container_width=True
        )

        if submitted:

            try:
                response = database.auth.sign_in_with_password({
                    "email": email.strip(),
                    "password": password
                })

                if response.user is None:
                    st.error("Login unsuccessful.")
                    return

                st.session_state.authenticated = True
                st.session_state.user_email = response.user.email

                st.rerun()

            except Exception:
                st.error("Invalid email or password. Please try again.")


# ==========================================
# 8. APPLICATION
# ==========================================

def main():

    database = get_database_client()

    # Authentication check
    if not st.session_state.get("authenticated", False):
        login_page(database)
        return

    system = HealthRecordSystem(database)

    # Sidebar
    st.sidebar.title("🩺 MediTrack")

    st.sidebar.caption(
        f"Logged in: {st.session_state.user_email}"
    )

    if st.sidebar.button("Log Out", use_container_width=True):

        database.auth.sign_out()

        st.session_state.authenticated = False
        st.session_state.pop("user_email", None)

        st.rerun()

    st.title("Health Record Management")
    st.caption("MediTrack — Patient Management Dashboard")

    # Retrieve patient records
    try:
        patients = system.get_all_patients()

    except Exception:
        st.error("Unable to retrieve patient records.")
        st.stop()

    # ======================================
    # DASHBOARD
    # ======================================

    tab1, tab2, tab3, tab4 = st.tabs([
        "Dashboard",
        "Add Patient",
        "Search / Update",
        "All Records"
    ])

    with tab1:

        regular_count = sum(
            isinstance(patient, Patient)
            and not isinstance(patient, EmergencyPatient)
            for patient in patients
        )

        emergency_count = sum(
            isinstance(patient, EmergencyPatient)
            for patient in patients
        )

        col1, col2, col3 = st.columns(3)

        col1.metric("Total Patients", len(patients))
        col2.metric("Regular Patients", regular_count)
        col3.metric("Emergency Patients", emergency_count)

        st.divider()

        st.subheader("Welcome to MediTrack")

        st.write(
            "Manage patient registration, health records, "
            "searching and updates from one place."
        )

        st.info(
            "This is an academic demonstration. "
            "Use fictional patient information only."
        )

    # ======================================
    # ADD PATIENT
    # ======================================

    with tab2:

        st.subheader("Register New Patient")

        with st.form("add_patient_form"):

            col1, col2 = st.columns(2)

            with col1:

                patient_id = st.text_input("Patient ID")

                name = st.text_input("Patient Name")

                age = st.number_input(
                    "Age",
                    min_value=1,
                    max_value=130,
                    value=25
                )

            with col2:

                blood_group = st.selectbox(
                    "Blood Group",
                    ["A+", "A-", "B+", "B-", "AB+",
                     "AB-", "O+", "O-", "Unknown"]
                )

                patient_type = st.selectbox(
                    "Patient Type",
                    ["Regular", "Emergency"]
                )

                emergency_level = st.selectbox(
                    "Emergency Level",
                    ["Low", "Moderate", "High", "Critical"]
                )

            condition = st.text_area("Medical Condition")

            submitted = st.form_submit_button(
                "Register Patient",
                use_container_width=True
            )

            if submitted:

                if not all([
                    patient_id.strip(),
                    name.strip(),
                    condition.strip()
                ]):

                    st.error("Please complete all required fields.")

                else:

                    try:

                        if patient_type == "Regular":

                            patient = Patient(
                                patient_id.strip(),
                                name.strip(),
                                age,
                                blood_group,
                                condition.strip()
                            )

                        else:

                            patient = EmergencyPatient(
                                patient_id.strip(),
                                name.strip(),
                                age,
                                blood_group,
                                condition.strip(),
                                emergency_level
                            )

                        system.add_patient(patient)

                        st.success("Patient registered successfully!")
                        st.rerun()

                    except Exception as error:

                        if "23505" in str(error):
                            st.error("This Patient ID already exists.")

                        else:
                            st.error(
                                f"Could not register patient "
                                f"({type(error).__name__})."
                            )

    # ======================================
    # SEARCH / UPDATE
    # ======================================

    with tab3:

        st.subheader("Search Patient")

        with st.form("search_form"):

            search_id = st.text_input("Enter Patient ID")

            search_clicked = st.form_submit_button("Search Patient")

        if search_clicked:

            if not search_id.strip():

                st.warning("Enter a Patient ID.")

                st.session_state.pop("searched_patient_id", None)

            else:

                st.session_state.searched_patient_id = search_id.strip()

        if "searched_patient_id" in st.session_state:

            try:
                patient = system.search_patient(
                    st.session_state.searched_patient_id
                )

            except Exception:
                st.error("Could not search patient records.")
                patient = None

            if patient:

                st.success("Patient found!")

                st.json(patient.to_database_record())

                st.divider()

                st.subheader("Update Medical Condition")

                with st.form("update_form"):

                    new_condition = st.text_area(
                        "New Medical Condition",
                        value=patient.condition
                    )

                    update_clicked = st.form_submit_button(
                        "Update Record"
                    )

                    if update_clicked:

                        try:

                            patient.update_condition(new_condition)

                            updated = system.update_patient(
                                patient.patient_id,
                                new_condition.strip()
                            )

                            if updated:
                                st.success("Record updated successfully!")
                                st.rerun()

                            else:
                                st.warning("No record was updated.")

                        except ValueError as error:
                            st.error(str(error))

                        except Exception:
                            st.error("Could not update the patient record.")

            elif not search_clicked:
                st.warning("Patient record not found.")

    # ======================================
    # VIEW ALL RECORDS
    # ======================================

    with tab4:

        st.subheader("All Patient Records")

        if patients:

            records = [
                patient.to_database_record()
                for patient in patients
            ]

            st.dataframe(
                records,
                use_container_width=True,
                hide_index=True
            )

        else:

            st.info("No patient records available.")


# ==========================================
# 9. START APPLICATION
# ==========================================

if __name__ == "__main__":
    main()
